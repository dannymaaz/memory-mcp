"""Validate a real package upgrade from the known v0.2.0 repository baseline."""

from __future__ import annotations

import json
import os
import sqlite3
import subprocess
import sys
import tempfile
import venv
import zipfile
from pathlib import Path

LEGACY_COMMIT = "e502f747fe86cf411070f55610a9cbd9ae242053"
ENV_KEYS = {
    "MEMORY_BACKEND",
    "MEMORY_STORAGE_BACKEND",
    "OWNER_ID",
    "SQLITE_PATH",
    "SUPABASE_URL",
    "SUPABASE_KEY",
    "DATABASE_URL",
}


def _run(
    command: list[str],
    *,
    cwd: Path,
    env: dict[str, str],
    expected: int = 0,
) -> subprocess.CompletedProcess[str]:
    result = subprocess.run(
        command,
        cwd=cwd,
        env=env,
        text=True,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        check=False,
    )
    if result.returncode != expected:
        raise RuntimeError(
            "Upgrade validation command returned "
            f"{result.returncode}, expected {expected}: {' '.join(command)}\n{result.stdout}"
        )
    return result


def _venv_python(root: Path) -> Path:
    if os.name == "nt":
        return root / "Scripts" / "python.exe"
    return root / "bin" / "python"


def _entrypoint(root: Path, name: str) -> Path:
    if os.name == "nt":
        return root / "Scripts" / f"{name}.exe"
    return root / "bin" / name


def _candidate_wheel(dist_dir: Path) -> Path:
    wheels = sorted(dist_dir.resolve().glob("persistent_memory_mcp-*.whl"))
    if len(wheels) != 1:
        raise RuntimeError(f"Expected exactly one candidate wheel, found {len(wheels)}")
    return wheels[0]


def _export_legacy_source(repo_root: Path, destination: Path, env: dict[str, str]) -> None:
    archive = destination.parent / "legacy-v020.zip"
    _run(
        [
            "git",
            "archive",
            "--format=zip",
            f"--output={archive}",
            LEGACY_COMMIT,
        ],
        cwd=repo_root,
        env=env,
    )
    with zipfile.ZipFile(archive) as bundle:
        bundle.extractall(destination)


def _insert_legacy_data(python: Path, database: Path, cwd: Path, env: dict[str, str]) -> None:
    code = (
        "import sqlite3, sys; "
        "db=sys.argv[1]; c=sqlite3.connect(db); "
        "w=c.execute(\"insert into workspaces(owner_id,slug,name) values('upgrade-owner','default','Default') returning id\").fetchone()[0]; "
        "p=c.execute(\"insert into projects(owner_id,workspace_id,slug,name) values('upgrade-owner',?,'upgrade','Upgrade') returning id\",(w,)).fetchone()[0]; "
        "c.execute(\"insert into tasks(project_id,owner_id,title,details) values(?,'upgrade-owner','survive-upgrade','created by installed 0.2.0')\",(p,)); "
        "c.commit(); assert c.execute('pragma user_version').fetchone()[0]==0; c.close()"
    )
    _run([str(python), "-c", code, str(database)], cwd=cwd, env=env)


def _verify_upgraded_data(database: Path) -> None:
    connection = sqlite3.connect(database)
    try:
        version = int(connection.execute("pragma user_version").fetchone()[0])
        history = connection.execute(
            "select version from schema_migrations order by version"
        ).fetchall()
        task = connection.execute(
            "select title, details from tasks where title='survive-upgrade'"
        ).fetchone()
    finally:
        connection.close()
    if version != 1 or history != [(1,)]:
        raise RuntimeError(
            f"Candidate migration did not establish current schema: version={version}, history={history}"
        )
    if task != ("survive-upgrade", "created by installed 0.2.0"):
        raise RuntimeError(f"Legacy task data was not preserved: {task}")


def validate(dist_dir: Path, repo_root: Path) -> None:
    candidate = _candidate_wheel(dist_dir)
    repo_root = repo_root.resolve()

    with tempfile.TemporaryDirectory(prefix="memory-mcp-v020-upgrade-") as temp_name:
        root = Path(temp_name).resolve()
        legacy_source = root / "legacy-source"
        legacy_dist = root / "legacy-dist"
        venv_dir = root / "venv"
        work_dir = root / "work"
        legacy_source.mkdir()
        legacy_dist.mkdir()
        work_dir.mkdir()

        clean_env = os.environ.copy()
        clean_env.pop("PYTHONPATH", None)
        for key in ENV_KEYS:
            clean_env.pop(key, None)

        _export_legacy_source(repo_root, legacy_source, clean_env)
        _run(
            [
                sys.executable,
                "-m",
                "build",
                "--wheel",
                "--outdir",
                str(legacy_dist),
                str(legacy_source),
            ],
            cwd=repo_root,
            env=clean_env,
        )
        legacy_wheels = sorted(legacy_dist.glob("persistent_memory_mcp-0.2.0-*.whl"))
        if len(legacy_wheels) != 1:
            raise RuntimeError(f"Could not build the pinned v0.2.0 wheel: {legacy_wheels}")

        venv.EnvBuilder(with_pip=True, clear=True).create(venv_dir)
        python = _venv_python(venv_dir)
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                str(legacy_wheels[0]),
            ],
            cwd=work_dir,
            env=clean_env,
        )
        legacy_entrypoint = _entrypoint(venv_dir, "memory-mcp")
        if not legacy_entrypoint.exists():
            raise RuntimeError("Pinned v0.2.0 wheel did not install memory-mcp")

        database = work_dir / "memory.db"
        env_path = work_dir / ".env"
        config_dir = work_dir / "configs"
        _run(
            [
                str(legacy_entrypoint),
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
                str(database),
                "--owner-id",
                "upgrade-owner",
            ],
            cwd=work_dir,
            env=clean_env,
        )
        _insert_legacy_data(python, database, work_dir, clean_env)

        # The candidate still carries pre-release package metadata until the final
        # version bump, so force reinstall is intentional here. The database and
        # generated configuration remain those created by the installed v0.2.0 wheel.
        _run(
            [
                str(python),
                "-m",
                "pip",
                "install",
                "--disable-pip-version-check",
                "--force-reinstall",
                str(candidate),
            ],
            cwd=work_dir,
            env=clean_env,
        )

        migration_entrypoint = _entrypoint(venv_dir, "memory-mcp-migrate")
        if not migration_entrypoint.exists():
            raise RuntimeError("Candidate wheel did not install memory-mcp-migrate")

        preview = _run(
            [str(migration_entrypoint), "--env", str(env_path)],
            cwd=work_dir,
            env=clean_env,
        )
        preview_payload = json.loads(preview.stdout)
        pending = (preview_payload.get("plan") or {}).get("pending") or []
        if [item.get("version") for item in pending] != [1]:
            raise RuntimeError(f"Expected v0.2.0 database to require migration 1: {preview_payload}")

        guard_code = (
            "from persistent_memory_mcp.runtime import _assert_migration_ready; "
            "from persistent_memory_mcp.settings import RuntimeSettings; "
            "import sys; "
            "s=RuntimeSettings(backend='sqlite',sqlite_path=sys.argv[1]); "
            "\ntry: _assert_migration_ready(s)\n"
            "except RuntimeError: raise SystemExit(0)\n"
            "raise SystemExit(9)"
        )
        _run(
            [str(python), "-c", guard_code, str(database)],
            cwd=work_dir,
            env=clean_env,
        )

        applied = _run(
            [str(migration_entrypoint), "--env", str(env_path), "--apply", "--yes"],
            cwd=work_dir,
            env=clean_env,
        )
        applied_payload = json.loads(applied.stdout)
        if applied_payload.get("status") != "ok" or not applied_payload.get("backup"):
            raise RuntimeError(f"Candidate migration did not create verified backup: {applied_payload}")

        _verify_upgraded_data(database)
        _run(
            [
                str(python),
                "-c",
                "from persistent_memory_mcp.runtime import _assert_migration_ready; "
                "from persistent_memory_mcp.settings import RuntimeSettings; import sys; "
                "_assert_migration_ready(RuntimeSettings(backend='sqlite',sqlite_path=sys.argv[1]))",
                str(database),
            ],
            cwd=work_dir,
            env=clean_env,
        )


if __name__ == "__main__":
    dist = Path(sys.argv[1] if len(sys.argv) > 1 else "dist")
    repo = Path(sys.argv[2] if len(sys.argv) > 2 else ".")
    validate(dist, repo)
    print("v0.2.0 package upgrade validation passed")
