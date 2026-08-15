# Persistent Memory MCP implementation status

Last reconciled for the post-v0.3 Context Compiler phase and PR #60. Persistent Memory MCP remains a local-first, personal and localhost-only product.

## Executive summary

The local data-safety foundation is mature: private SQLite storage, owner/project isolation, WAL-safe backup, SHA-256 manifests, read-only health diagnostics, confirmed restore with rollback, versioned backup-first migrations, explicit upgrade tooling, deterministic SQLite connection lifecycle, validated Settings and cross-platform release-artifact testing.

The active engineering phase is no longer basic persistence or recovery. The next product problem is **context delivery quality**: turning durable project memory and repository evidence into a bounded, versioned, provenance-aware packet that an MCP client can use without loading unrelated history.

PR #60 implements the first mandatory step from the new Notion roadmap: Context Packet v1 plus model-aware token accounting. It is deliberately additive over the existing `build_context()` engine so legacy callers keep their behavior while the real optimizer/model-routing path gains a verifiable packet contract.

## Current capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| Product CLI and local onboarding | Complete foundation | `init`, `doctor`, `status`, `health`, `serve` | Ongoing UX refinement |
| SQLite local-first storage | Complete | WAL, foreign keys, versioned migrations | Future numbered migrations as schema evolves |
| Verified backup + manifests | Complete foundation | Backup API, integrity check, SHA-256 sidecars | Optional rotation/signing refinements |
| Health + maintenance readiness | Complete foundation | Read-only checks and verified-backup awareness | Dashboard presentation |
| Confirmed restore | Complete foundation | Two-phase plan/execute, safety backup, rollback | Dashboard integration only |
| Installed upgrade lifecycle | Complete | v0.2.0 → v0.3.0 package regression | Future release migrations |
| Runtime Settings | Complete foundation | validated SQLite-first configuration | Specialized provider settings remain incremental |
| Context ranking/filtering | Complete foundation | intent-aware selection, expiry/trust filtering, compression | Now being wrapped by Context Packet v1 |
| Context Packet v1 | **In review** | Issue #56 / PR #60 | Full exact-head CI + merge |
| Model-aware token accounting | **In review** | optional tiktoken reference + deterministic fallback | Full exact-head CI + merge |
| Progressive repository retrieval | Planned | post-v0.3 roadmap Step 2 | Not started until packet contract merges |
| Git verification | Complete foundation | repository/branch/commit/file verification | Richer revision binding |
| Code intelligence | Partial | symbol extraction + bounded impact graphs | Persistent symbol evolution across revisions |
| Automatic continuation | Partial | sessions/checkpoints/handoff | project resolution + automatic milestone capture |
| Hybrid search/embeddings | Complete foundation | semantic + lexical fallback | broader quality/cost benchmarks |
| Evaluation/provenance suite | Complete foundation | existing agent regressions | context-quality golden scenarios planned |
| Dashboard/Galaxy | Partial foundation | localhost operational views + bounded graph | operational project map is roadmap Step 5 |
| Teams / remote collaboration | Out of scope | explicit product decision | no implementation planned |

## Context Packet v1 contract — PR #60

The new compiler exposes a stable packet through the same interface path used by `load_unified_context` rather than only as a standalone helper.

A packet includes:

- contract version (`1.0`);
- current objective/intent;
- next safe action when an explicit checkpoint/session/task provides one;
- compact provenance sources;
- verification status derived from selected evidence;
- hard token budget and final serialized token count;
- tokenizer identity and model when known;
- exact-vs-estimated mode;
- selected, dropped, compressed and token-cost metrics per context block.

### Compatibility

- `build_context()` keeps the historical contract used by existing callers.
- `ContextOptimizer.optimize_for_interface()` compiles the versioned packet for the real delivery path.
- `ModelRouter` refreshes token accounting after adding final delivery/model annotations so the packet does not report a stale pre-routing count.
- Existing 256-token requests use a compact control profile that preserves mandatory packet fields while removing redundant diagnostic metadata.
- Small-budget routing still fails closed if required control/project data cannot fit the requested hard budget.

## Token-accounting design

Core installations do not require a provider tokenizer.

### Deterministic local fallback

`deterministic-heuristic-v2` is provider-free and deterministic:

- natural prose uses a stable character-class heuristic;
- code/JSON/short payloads remain on a conservative character estimator;
- the legacy identifier `deterministic-char4-v1` remains accepted as a compatibility alias;
- unknown model mappings under `tokenizer="auto"` fall back locally instead of requiring a network service.

### Optional exact reference

The optional package extra is:

```bash
pip install "persistent-memory-mcp[tokenizers]"
```

It uses local `tiktoken` counting when the requested model/encoding can be resolved. It is not a core dependency and is used in CI as a reference measurement for the deterministic fallback.

### Reproducible measurement evidence

PR #60 adds `scripts/evaluate_tokenization.py` and fixed Spanish/source-code fixtures.

Current exact-head measurements against `gpt-4o` / `tiktoken:o200k_base`:

| Fixture | Reference | Deterministic fallback | Absolute error | Error |
|---|---:|---:|---:|---:|
| Spanish prose | 69 | 80 | 11 | **15.94%** |
| Python/source code | 138 | 140 | 2 | **1.45%** |

Configured guardrail: worst fixture error must be **≤ 40%**. Current worst measured error is **15.94%**.

The dedicated packet/tokenizer regression suite currently contains 14 tests and validates the same contract with the optional reference tokenizer on Ubuntu, Windows and macOS.

## Context budget semantics

For normal budgets, Context Packet reserves an explicit safety margin and retains richer diagnostics. For budgets at or below 512 tokens, it switches to a compact metadata representation while preserving:

- version;
- objective;
- sources;
- verification status;
- budget/count/tokenizer;
- per-block selection/drop/compression/token metrics.

The active token counter measures the **final serialized packet**, not only the selected memory items. Low-ranked removable content is dropped until the packet fits. Required control/project metadata is never silently discarded; if it cannot fit, compilation fails instead of returning a misleading count.

## Existing local data-safety contracts

### Backup and manifest

- active SQLite databases are copied with `sqlite3.Connection.backup()`;
- WAL mode is supported;
- same-path/overwrite attempts are rejected;
- completed copies pass integrity validation;
- sidecar manifests provide SHA-256 and bounded structural metadata without memory contents.

### Health

- bounded `quick_check` on every report;
- optional full `integrity_check`;
- foreign-key/index checks;
- DB/WAL/SHM size and free disk reporting;
- latest valid backup awareness;
- no normal output of stored memory values or the absolute active DB path.

### Restore

- read-only plan verifies manifest/checksum/integrity/schema/headroom;
- HMAC confirmation is exact-plan-bound and single-use;
- fresh verified safety backup precedes replacement;
- WAL-aware logical fingerprinting detects meaningful drift;
- atomic replacement and post-validation are mandatory;
- failed validation restores the safety backup automatically.

### Versioned migration

- read-only preview;
- checksum-validated migration history;
- verified pre-migration backup;
- transaction-per-migration execution;
- explicit `memory-mcp-migrate --apply --yes` mutation;
- startup never automigrates an existing stale database;
- historical installed v0.2.0 data-preservation regression runs across supported operating systems.

## Product scope

Persistent Memory MCP is designed around:

- one personal installation;
- local SQLite by default;
- localhost-only dashboard access;
- project and local-owner isolation;
- optional self-managed remote storage adapters without changing product direction.

Not planned:

- workspace invitations;
- team memberships or role hierarchies;
- public remote collaborative dashboards;
- billing/organization administration;
- automatic code execution from stored memory.

## Post-v0.3 completion sequence

1. **Context Packet + token accounting** — PR #60, in review.
2. **Progressive repository retrieval** — planned next after PR #60 merges.
3. **Persistent code provenance/symbol evolution** — planned.
4. **Context-quality regression guardrails** — planned.
5. **Operational project map / Galaxy** — planned after the evidence layers above exist.

## Definition of done for PR #60 / MEM-36

- [x] Versioned Context Packet contract implemented.
- [x] Real optimizer/model-routing path exposes and finalizes the packet.
- [x] Deterministic provider-free tokenizer fallback implemented.
- [x] Optional model-aware reference tokenizer supported.
- [x] Spanish and source-code fixtures added.
- [x] Reproducible exact-vs-fallback metrics generated in CI.
- [x] Per-block selected/dropped/compressed/token metrics implemented.
- [x] 256-token compatibility represented through compact packet metadata.
- [x] Dedicated packet/tokenizer tests pass on the current Ubuntu reference job.
- [ ] Exact final PR head passes the full Ubuntu/Windows/macOS Quality matrix and artifact validation.
- [ ] PR #60 merged.
- [ ] MEM-36 marked complete in Notion.

The next implementation task must not begin before the final PR #60 gate is closed, because progressive retrieval is required to consume the stable packet/token-budget contract rather than invent another parallel accounting path.
