"""Generate or verify SHA-256 checksums for built release artifacts."""

from __future__ import annotations

import argparse
import hashlib
from pathlib import Path

_MANIFEST_NAME = "SHA256SUMS"


def _artifacts(directory: Path) -> list[Path]:
    files = [
        path
        for path in directory.iterdir()
        if path.is_file()
        and path.name != _MANIFEST_NAME
        and (path.name.endswith(".whl") or path.name.endswith(".tar.gz"))
    ]
    return sorted(files, key=lambda path: path.name)


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate(directory: Path) -> Path:
    directory = directory.resolve()
    artifacts = _artifacts(directory)
    if not artifacts:
        raise RuntimeError(f"No wheel or sdist artifacts found in {directory}")
    manifest = directory / _MANIFEST_NAME
    content = "".join(f"{_sha256(path)}  {path.name}\n" for path in artifacts)
    manifest.write_text(content, encoding="utf-8")
    return manifest


def verify(directory: Path) -> None:
    directory = directory.resolve()
    manifest = directory / _MANIFEST_NAME
    if not manifest.is_file():
        raise RuntimeError(f"Checksum manifest does not exist: {manifest}")

    expected_files = {path.name for path in _artifacts(directory)}
    observed_files: set[str] = set()
    for raw_line in manifest.read_text(encoding="utf-8").splitlines():
        if not raw_line.strip():
            continue
        try:
            digest, filename = raw_line.split("  ", 1)
        except ValueError as exc:
            raise RuntimeError(f"Malformed checksum line: {raw_line!r}") from exc
        filename = filename.strip()
        artifact = directory / filename
        if filename in observed_files:
            raise RuntimeError(f"Duplicate checksum entry: {filename}")
        if filename not in expected_files:
            raise RuntimeError(f"Unexpected checksum entry: {filename}")
        if not artifact.is_file():
            raise RuntimeError(f"Artifact referenced by checksum is missing: {filename}")
        actual = _sha256(artifact)
        if actual != digest.lower():
            raise RuntimeError(
                f"Checksum mismatch for {filename}: expected {digest.lower()}, got {actual}"
            )
        observed_files.add(filename)

    missing = sorted(expected_files - observed_files)
    if missing:
        raise RuntimeError(f"Checksum manifest is missing artifacts: {missing}")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", nargs="?", default="dist")
    parser.add_argument("--verify", action="store_true")
    return parser


def main() -> int:
    args = build_parser().parse_args()
    directory = Path(args.directory)
    if args.verify:
        verify(directory)
        print(f"Verified {directory.resolve() / _MANIFEST_NAME}")
    else:
        manifest = generate(directory)
        print(manifest)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
