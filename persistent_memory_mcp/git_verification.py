"""Git-grounded verification and staleness classification for memory records."""

from __future__ import annotations

import hashlib
import os
import subprocess
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable, Literal

VerificationStatus = Literal[
    "verified",
    "stale",
    "contradicted",
    "missing_source",
    "unverified",
]


@dataclass(frozen=True)
class GitSnapshot:
    """Current repository facts used to verify remembered provenance."""

    repository: str
    branch: str | None
    commit_sha: str
    remote_url: str | None
    dirty: bool


@dataclass(frozen=True)
class VerificationResult:
    """Structured verification result attached to a memory record."""

    status: VerificationStatus
    checked_at: str
    last_verified_commit: str | None
    evidence: tuple[str, ...] = field(default_factory=tuple)
    contradictions: tuple[str, ...] = field(default_factory=tuple)
    refreshed_provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def _run_git(repo_path: str | os.PathLike[str], *args: str) -> str:
    completed = subprocess.run(
        ["git", "-C", os.fspath(repo_path), *args],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    )
    return completed.stdout.strip()


def _try_git(repo_path: str | os.PathLike[str], *args: str) -> str | None:
    try:
        return _run_git(repo_path, *args)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return None


def repository_snapshot(repo_path: str | os.PathLike[str]) -> GitSnapshot:
    """Read authoritative repository, branch and commit facts from Git."""
    root = _run_git(repo_path, "rev-parse", "--show-toplevel")
    commit_sha = _run_git(root, "rev-parse", "HEAD")
    branch = _try_git(root, "symbolic-ref", "--quiet", "--short", "HEAD")
    remote_url = _try_git(root, "config", "--get", "remote.origin.url")
    dirty = bool(_run_git(root, "status", "--porcelain"))
    return GitSnapshot(
        repository=str(Path(root).resolve()),
        branch=branch or None,
        commit_sha=commit_sha,
        remote_url=remote_url or None,
        dirty=dirty,
    )


def file_sha256(repo_path: str | os.PathLike[str], file_path: str) -> str | None:
    """Return a repository-relative file digest, or None when the file is absent."""
    root = Path(repo_path).resolve()
    candidate = (root / file_path).resolve()
    try:
        candidate.relative_to(root)
    except ValueError:
        return None
    if not candidate.is_file():
        return None
    digest = hashlib.sha256()
    with candidate.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def commit_exists(repo_path: str | os.PathLike[str], commit_sha: str) -> bool:
    return _try_git(repo_path, "cat-file", "-e", f"{commit_sha}^{{commit}}") is not None


def branch_exists(repo_path: str | os.PathLike[str], branch: str) -> bool:
    local = _try_git(repo_path, "show-ref", "--verify", f"refs/heads/{branch}")
    remote = _try_git(repo_path, "show-ref", "--verify", f"refs/remotes/origin/{branch}")
    return local is not None or remote is not None


def commit_is_ancestor(repo_path: str | os.PathLike[str], commit_sha: str, ref: str = "HEAD") -> bool:
    try:
        subprocess.run(
            ["git", "-C", os.fspath(repo_path), "merge-base", "--is-ancestor", commit_sha, ref],
            check=True,
            capture_output=True,
            timeout=10,
        )
        return True
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return False


def _provenance(memory: dict[str, Any]) -> dict[str, Any]:
    metadata = memory.get("metadata") if isinstance(memory.get("metadata"), dict) else {}
    provenance = memory.get("provenance") if isinstance(memory.get("provenance"), dict) else {}
    repository_state = (
        metadata.get("repository_state")
        if isinstance(metadata.get("repository_state"), dict)
        else {}
    )
    return {**repository_state, **provenance, **memory}


def verify_memory(
    memory: dict[str, Any],
    *,
    repo_path: str | os.PathLike[str] | None = None,
    now: datetime | None = None,
) -> VerificationResult:
    """Verify remembered Git facts against the active repository.

    Status precedence is deliberate: missing evidence, direct contradiction,
    stale-but-historical evidence, verified evidence, then unverified.
    """
    source = _provenance(memory)
    repository = repo_path or source.get("repo_path") or source.get("repository_path")
    checked_at = (now or datetime.now(UTC)).astimezone(UTC).isoformat()
    if not repository:
        return VerificationResult(
            status="unverified",
            checked_at=checked_at,
            last_verified_commit=None,
            evidence=("No repository path was supplied.",),
        )

    try:
        snapshot = repository_snapshot(repository)
    except (OSError, subprocess.CalledProcessError, subprocess.TimeoutExpired):
        return VerificationResult(
            status="missing_source",
            checked_at=checked_at,
            last_verified_commit=None,
            evidence=(f"Repository is unavailable: {repository}",),
        )

    evidence: list[str] = [f"Repository HEAD is {snapshot.commit_sha}."]
    contradictions: list[str] = []
    stale_reasons: list[str] = []
    checked_any = False

    expected_remote = source.get("remote_url") or source.get("repository_url")
    if expected_remote:
        checked_any = True
        if snapshot.remote_url and snapshot.remote_url != expected_remote:
            contradictions.append(
                f"Remembered remote {expected_remote!r} differs from active remote {snapshot.remote_url!r}."
            )
        else:
            evidence.append("Repository remote matches remembered provenance.")

    expected_commit = source.get("commit_sha") or source.get("git_commit")
    if expected_commit:
        checked_any = True
        if not commit_exists(snapshot.repository, str(expected_commit)):
            stale_reasons.append(f"Remembered commit {expected_commit} no longer exists locally.")
        elif snapshot.commit_sha == expected_commit:
            evidence.append("Remembered commit matches repository HEAD.")
        elif commit_is_ancestor(snapshot.repository, str(expected_commit)):
            stale_reasons.append(
                f"Repository advanced from remembered commit {expected_commit} to {snapshot.commit_sha}."
            )
        else:
            contradictions.append(
                f"Remembered commit {expected_commit} is not an ancestor of active HEAD {snapshot.commit_sha}."
            )

    expected_branch = source.get("branch") or source.get("git_branch")
    if expected_branch:
        checked_any = True
        if snapshot.branch == expected_branch:
            evidence.append("Remembered branch matches the active branch.")
        elif not branch_exists(snapshot.repository, str(expected_branch)):
            stale_reasons.append(f"Remembered branch {expected_branch!r} was deleted or is unavailable.")
        else:
            stale_reasons.append(
                f"Remembered branch {expected_branch!r} is not active; current branch is {snapshot.branch!r}."
            )

    expected_file = source.get("file_path") or source.get("path")
    expected_digest = source.get("file_sha256") or source.get("content_sha256")
    if expected_file:
        checked_any = True
        actual_digest = file_sha256(snapshot.repository, str(expected_file))
        if actual_digest is None:
            stale_reasons.append(f"Referenced file {expected_file!r} is missing.")
        elif expected_digest and actual_digest != expected_digest:
            contradictions.append(f"Referenced file {expected_file!r} changed since it was remembered.")
        else:
            evidence.append(f"Referenced file {expected_file!r} exists and matches available evidence.")

    production_commit = source.get("production_commit") or source.get("deployed_commit")
    if production_commit:
        checked_any = True
        if production_commit != snapshot.commit_sha:
            stale_reasons.append(
                f"Production commit {production_commit} differs from repository HEAD {snapshot.commit_sha}."
            )
        else:
            evidence.append("Production commit matches repository HEAD.")

    refreshed = {
        "repository_path": snapshot.repository,
        "branch": snapshot.branch,
        "commit_sha": snapshot.commit_sha,
        "remote_url": snapshot.remote_url,
        "repository_dirty": snapshot.dirty,
        "last_verified_at": checked_at,
        "last_verified_commit": snapshot.commit_sha,
    }

    if contradictions:
        status: VerificationStatus = "contradicted"
    elif stale_reasons:
        status = "stale"
        evidence.extend(stale_reasons)
    elif checked_any:
        status = "verified"
    else:
        status = "unverified"
        evidence.append("Repository exists, but the memory contains no Git evidence to verify.")

    return VerificationResult(
        status=status,
        checked_at=checked_at,
        last_verified_commit=snapshot.commit_sha,
        evidence=tuple(evidence),
        contradictions=tuple(contradictions),
        refreshed_provenance=refreshed,
    )


def prefer_repository_state(memory: dict[str, Any], verification: VerificationResult) -> dict[str, Any]:
    """Return a non-destructive view where verified repository facts win conflicts."""
    result = dict(memory)
    metadata = dict(result.get("metadata") or {})
    history = list(metadata.get("verification_history") or [])
    previous = metadata.get("repository_state")
    if previous:
        history.append(previous)
    metadata["repository_state"] = dict(verification.refreshed_provenance)
    metadata["verification_status"] = verification.status
    metadata["verification_evidence"] = list(verification.evidence)
    metadata["verification_contradictions"] = list(verification.contradictions)
    metadata["verification_history"] = history[-20:]
    result["metadata"] = metadata
    return result


def build_verified_search_tool(server_module: Any) -> Callable[..., dict[str, Any]]:
    """Wrap semantic search so returned memories include live Git verification."""
    original_search = server_module.search_semantic_memory

    def search_semantic_memory(
        query: str,
        project_id: str | None = None,
        owner_id: str | None = None,
        query_embedding: list[float] | None = None,
        limit: int = 5,
        source_types: list[str] | None = None,
        minimum_score: float = 0.05,
        repo_path: str | None = None,
        verify_git: bool = True,
    ) -> dict[str, Any]:
        result = original_search(
            query=query,
            project_id=project_id,
            owner_id=owner_id,
            query_embedding=query_embedding,
            limit=limit,
            source_types=source_types,
            minimum_score=minimum_score,
        )
        if "error" in result or not verify_git:
            return result
        matches = []
        counts: dict[str, int] = {}
        for match in result.get("matches", []):
            verification = verify_memory(match, repo_path=repo_path)
            grounded = prefer_repository_state(match, verification)
            grounded["verification"] = verification.to_dict()
            matches.append(grounded)
            counts[verification.status] = counts.get(verification.status, 0) + 1
        result["matches"] = matches
        result["verification_counts"] = counts
        result["repository_grounded"] = True
        return result

    search_semantic_memory.__name__ = "search_semantic_memory"
    search_semantic_memory.__doc__ = "Busca memoria y verifica su evidencia contra el repositorio Git activo."
    return search_semantic_memory


def _replace_registered_tool(server: Any, name: str, function: Callable[..., Any]) -> bool:
    replaced = False
    tools = getattr(server, "_tools", None)
    if isinstance(tools, dict) and name in tools:
        tools[name] = function
        replaced = True
    manager = getattr(server, "_tool_manager", None)
    managed_tools = getattr(manager, "_tools", None)
    if isinstance(managed_tools, dict) and name in managed_tools:
        tool = managed_tools[name]
        if hasattr(tool, "fn"):
            tool.fn = function
        elif hasattr(tool, "function"):
            tool.function = function
        else:
            managed_tools[name] = function
        replaced = True
    return replaced


def install_git_verification(server_module: Any) -> Callable[..., dict[str, Any]]:
    """Install repository verification after hybrid search has been installed."""
    if getattr(server_module, "_git_verification_installed", False):
        return server_module.search_semantic_memory
    tool = build_verified_search_tool(server_module)
    server_module.search_semantic_memory = tool
    _replace_registered_tool(server_module.server, "search_semantic_memory", tool)
    server_module._git_verification_installed = True
    return tool
