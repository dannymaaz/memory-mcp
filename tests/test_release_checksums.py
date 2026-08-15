from __future__ import annotations

from pathlib import Path

import pytest

from scripts.generate_checksums import generate, verify


def test_generate_and_verify_release_checksums(tmp_path: Path) -> None:
    wheel = tmp_path / "persistent_memory_mcp-0.3.0-py3-none-any.whl"
    sdist = tmp_path / "persistent_memory_mcp-0.3.0.tar.gz"
    wheel.write_bytes(b"wheel-content")
    sdist.write_bytes(b"sdist-content")

    manifest = generate(tmp_path)

    assert manifest.name == "SHA256SUMS"
    lines = manifest.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 2
    assert lines[0].endswith(f"  {wheel.name}")
    assert lines[1].endswith(f"  {sdist.name}")
    verify(tmp_path)


def test_checksum_verification_rejects_tampered_artifact(tmp_path: Path) -> None:
    wheel = tmp_path / "persistent_memory_mcp-0.3.0-py3-none-any.whl"
    wheel.write_bytes(b"original")
    generate(tmp_path)
    wheel.write_bytes(b"tampered")

    with pytest.raises(RuntimeError, match="Checksum mismatch"):
        verify(tmp_path)


def test_checksum_verification_rejects_unlisted_new_artifact(tmp_path: Path) -> None:
    wheel = tmp_path / "persistent_memory_mcp-0.3.0-py3-none-any.whl"
    wheel.write_bytes(b"wheel")
    generate(tmp_path)
    (tmp_path / "persistent_memory_mcp-0.3.0.tar.gz").write_bytes(b"sdist")

    with pytest.raises(RuntimeError, match="missing artifacts"):
        verify(tmp_path)
