"""Verify that built release artifacts consistently identify as v0.3.0."""

from __future__ import annotations

import re
import sys
import tarfile
import zipfile
from pathlib import Path

EXPECTED_VERSION = "0.3.0"
PACKAGE_PREFIX = "persistent_memory_mcp"


def validate(directory: Path) -> None:
    directory = directory.resolve()
    wheels = sorted(directory.glob(f"{PACKAGE_PREFIX}-*.whl"))
    sdists = sorted(directory.glob(f"{PACKAGE_PREFIX}-*.tar.gz"))
    if len(wheels) != 1 or len(sdists) != 1:
        raise RuntimeError(
            f"Expected one wheel and one sdist, found wheels={len(wheels)} sdists={len(sdists)}"
        )

    wheel = wheels[0]
    sdist = sdists[0]
    expected_stem = f"{PACKAGE_PREFIX}-{EXPECTED_VERSION}"
    if not wheel.name.startswith(expected_stem + "-"):
        raise RuntimeError(f"Wheel filename does not identify v{EXPECTED_VERSION}: {wheel.name}")
    if sdist.name != f"{expected_stem}.tar.gz":
        raise RuntimeError(f"Sdist filename does not identify v{EXPECTED_VERSION}: {sdist.name}")

    with zipfile.ZipFile(wheel) as archive:
        metadata_names = [name for name in archive.namelist() if name.endswith(".dist-info/METADATA")]
        if len(metadata_names) != 1:
            raise RuntimeError(f"Expected exactly one wheel METADATA file: {metadata_names}")
        metadata = archive.read(metadata_names[0]).decode("utf-8")
    version_match = re.search(r"^Version:\s*(.+)$", metadata, flags=re.MULTILINE)
    if version_match is None or version_match.group(1).strip() != EXPECTED_VERSION:
        raise RuntimeError("Wheel METADATA version does not match 0.3.0")

    with tarfile.open(sdist, mode="r:gz") as archive:
        root_names = {name.split("/", 1)[0] for name in archive.getnames() if name}
    if root_names != {expected_stem}:
        raise RuntimeError(f"Unexpected sdist root directory: {sorted(root_names)}")


if __name__ == "__main__":
    validate(Path(sys.argv[1] if len(sys.argv) > 1 else "dist"))
    print(f"Release artifact version {EXPECTED_VERSION} validated")
