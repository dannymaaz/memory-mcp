# Automatic Continuation Contract

Persistent Memory MCP uses a compact **Continuation Contract v1** to make project handoff and resumption deterministic across MCP-compatible development clients without storing unbounded source content.

## Purpose

The contract answers the minimum set of questions required to continue safely:

- what is the current objective;
- what was completed;
- what remains;
- what is blocked;
- which files are relevant;
- what tests or validation evidence were recorded;
- what the next safe action is;
- which Git commit/branch the checkpoint relates to and whether the working tree was dirty.

It is stored inside the metadata of the checkpoint that `end_session` already creates. The integration enriches that existing checkpoint rather than creating a second continuation record or a new database table.

## Contract shape

```json
{
  "version": "1.0",
  "objective": "Finish the authentication refactor",
  "completed": "Repository-bound resolver implemented",
  "pending": ["Run full CI", "Update docs"],
  "blockers": [],
  "files": ["src/server.py", "tests/test_server.py"],
  "tests": [{"name": "pytest", "status": "passed"}],
  "next_action": "Run the cross-platform regression suite",
  "git": {
    "branch": "main",
    "commit": "<commit>",
    "dirty": false,
    "changed_files": [],
    "remote": "github.com/owner/repository",
    "root_fingerprint": "<bounded fingerprint>"
  }
}
```

The historical `resume_project` fields remain available. A compatible response additionally exposes `continuation_version` and `continuation` so existing clients do not need to migrate immediately.

## Automatic lifecycle behavior

Runtime installation is intentionally ordered:

1. install the Continuation Contract wrapper;
2. install the automatic Session Lifecycle wrapper.

Session Lifecycle therefore captures the continuation-aware `end_session` implementation. The same checkpoint path is used for:

- an explicit/normal session close;
- cross-interface handoff;
- idle-timeout expiry.

A handoff or timeout does not create a second checkpoint format.

## Repository-bound project resolution

Before falling back to historical slug-based project creation, the resolver checks existing projects for the same owner using strong repository evidence:

1. normalized Git remote identity;
2. normalized local repository root.

Remote matches are weighted more strongly than local-root matches so moving or renaming a local checkout does not create a duplicate project when the canonical remote is unchanged.

If multiple projects have the same strongest binding score, resolution **fails closed** instead of guessing.

Explicit `project_id` resolution retains its historical behavior and remains subject to the existing owner/project security integrations.

## Privacy and bounds

Continuation payloads are deliberately small and defensive:

- strings are bounded;
- list-like fields are capped at 20 entries;
- structured list entries expose only compact fields such as path/name/status/result/summary;
- existing recursive secret redaction is applied;
- remote URL credentials, query strings and fragments are removed before comparison or persistence;
- SCP and HTTPS Git remotes normalize to the same credential-free host/path identity;
- the absolute local repository root is not emitted in the contract;
- only a short SHA-256-derived root fingerprint is emitted;
- source file bodies are never included;
- repository code is never executed.

The persisted project record may continue to contain the local repository path required by existing local product behavior; the Continuation Contract itself does not expose that path.

## Failure behavior

The integration fails closed when:

- no active session can be resolved for a close;
- more than one owner-scoped project has the strongest repository binding;
- the wrapped session operation returns an error.

No automatic destructive operation is introduced.

## Regression coverage

`tests/test_continuation_contract.py` validates:

- bounded/redacted snapshots;
- owner-scoped repository binding;
- local-folder rename without duplicate project creation;
- ambiguous binding rejection;
- enrichment of the existing checkpoint rather than duplicate creation;
- backward-compatible resume output;
- cross-client handoff through the continuation-aware close path;
- idle-expiry through the continuation-aware close path.

`tests/test_continuation_remote_security.py` validates credential-free remote normalization and ensures the snapshot never emits remote credentials or the absolute repository root.

The feature is also covered by the repository-wide Ubuntu/Windows/macOS × Python 3.11–3.13 Quality matrix and release-artifact upgrade checks.