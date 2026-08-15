"""Validate built Persistent Memory MCP release artifacts outside the source checkout."""

from __future__ import annotations

import json
import os
import subprocess
import sys
import tarfile
import tempfile
import venv
import zipfile
from pathlib import Path

ENV_KEYS = {
    "MEMORY_BACKEND",
    "MEMORY_STORAGE_BACKEND",
    "OWNER_ID",
    "SQLITE_PATH",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "DATABASE_URL",
}


def _run(command: list[str], *, cwd: Path, env: dict[str, str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=True,
    )


def _venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def _venv_entrypoint(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "memory-mcp.exe"
    return root / "bin" / "memory-mcp"


def _validate_archive_assets(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.glob("persistent_memory_mcp-*.whl"))
    sdists = sorted(dist_dir.glob("persistent_memory_mcp-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError(
            f"Expected one wheel and one sdist, found wheels={len(wheels)} sdists={len(sdists)}"
        )
    wheel = wheels[0]
    sdist = sdists[0]

    with zipfile.ZipFile(wheel) as archive:
        names = set(archive.namelist())
        required_assets = {
            "persistent_memory_mcp/sqlite_schema.sql",
            "persistent_memory_mcp/__init__.py",
            "persistent_memory_mcp/runtime.py",
        }
        missing = sorted(required_assets - names)
        if missing:
            raise RuntimeError(f"Wheel is missing required package assets: {missing}")

    with tarfile.open(sdist, mode="r:gz") as archive:
        names = tuple(archive.getnames())
        required_suffixes = (
            "/persistent_memory_mcp/sqlite_schema.sql",
            "/persistent_memory_mcp/runtime.py",
            "/pyproject.toml",
            "/README.md",
        )
        missing = [suffix for suffix in required_suffixes if not any(name.endswith(suffix) for name in names)]
        if missing:
            raise RuntimeError(f"Sdist is missing required package assets: {missing}")

    return wheel


def validate(dist_dir: Path) -> None:
    dist_dir = dist_dir.resolve()
    wheel = _validate_archive_assets(dist_dir)

    with tempfile.TemporaryDirectory(prefix="memory-mcp-artifact-") as temp_name:
        root = Path(temp_name).resolve()
        venv_dir = root / "venv"
        work_dir = root / "work"
        work_dir.mkdir()
        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        python = _venv_python(venv_dir)
        entrypoint = _venv_entrypoint(venv_dir)

        clean_env = os.environ.copy()
        clean_env.pop("PYTHONPATH", None)
        for key in ENV_KEYS:
            clean_env.pop(key, None)

        _run(
            [str(python), "-m", "pip", "install", "--disable-pip-version-check", str(wheel)],
            cwd=work_dir,
            env=clean_env,
        )
        if not entrypoint.exists():
            raise RuntimeError(f"Installed wheel did not create the memory-mcp entrypoint: {entrypoint}")

        dependency_check = _run(
            [
                str(python),
                "-c",
                "from importlib.metadata import requires; "
                "r=requires('persistent-memory-mcp') or []; "
                "assert not any('supabase' in x.lower() or 'psycopg2' in x.lower() for x in r), r",
            ],
            cwd=work_dir,
            env=clean_env,
        )
        if dependency_check.returncode != 0:  # pragma: no cover - check=True is the primary guard
            raise RuntimeError(dependency_check.stdout)

        env_path = work_dir / ".env"
        sqlite_path = work_dir / "memory.db"
        config_dir = work_dir / "configs"
        _run(
            [
                str(entrypoint),
                "init",
                "--env",
                str(env_path),
                "--output-dir",
                str(config_dir),
                "--clients",
                "codex",
                "--backend",
                "sqlite",
                "--sqlite-path",
                str(sqlite_path),
                "--owner-id",
                "artifact-validation",
            ],
            cwd=work_dir,
            env=clean_env,
        )
        if not sqlite_path.exists():
            raise RuntimeError("Clean wheel install did not initialize the SQLite database")
        if not (config_dir / "codex-config.toml").exists():
            raise RuntimeError("Clean wheel install did not generate the expected client configuration")

        _run([str(entrypoint), "doctor", "--env", str(env_path)], cwd=work_dir, env=clean_env)
        status = _run(
            [str(entrypoint), "status", "--env", str(env_path)], cwd=work_dir, env=clean_env
        )
        status_payload = json.loads(status.stdout)
        if status_payload.get("backend") != "sqlite" or status_payload.get("configured") is not True:
            raise RuntimeError(f"Unexpected status payload from clean wheel install: {status_payload}")

        health = _run(
            [str(entrypoint), "health", "--env", str(env_path)], cwd=work_dir, env=clean_env
        )
        health_payload = json.loads(health.stdout)
        if health_payload.get("status") != "healthy":
            raise RuntimeError(f"Unexpected health payload from clean wheel install: {health_payload}")

        import_check = _run(
            [
                str(python),
                "-c",
                "import persistent_memory_mcp, pathlib; "
                "p=pathlib.Path(persistent_memory_mcp.__file__).resolve(); "
                f"assert not str(p).startswith({str(Path.cwd().resolve())!r}), p",
            ],
            cwd=work_dir,
            env=clean_env,
        )
        if import_check.returncode != 0:  # pragma: no cover
            raise RuntimeError(import_check.stdout)


if __name__ == "__main__":
    target = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    validate(target)
    print("Release artifact validation passed")
