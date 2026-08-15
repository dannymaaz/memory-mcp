# Persistent Memory MCP implementation status

Last reconciled for the post-v0.3 Context Compiler phase and PR #62. Persistent Memory MCP remains a local-first, personal and localhost-only product.

## Executive summary

The local data-safety foundation is mature: private SQLite storage, owner/project isolation, WAL-safe backup, SHA-256 manifests, read-only health diagnostics, confirmed restore with rollback, versioned backup-first migrations, explicit upgrade tooling, deterministic SQLite connection lifecycle, validated Settings and cross-platform release-artifact testing.

The first post-v0.3 Context Compiler milestone is complete. PR #60 established Context Packet v1, model-aware/local token accounting and a hard serialized output budget without breaking existing `build_context()` callers.

PR #62 implements the second mandatory milestone: **progressive repository retrieval**. Instead of opening the repository broadly, the MCP path maps supported files first, ranks a bounded candidate set, parses symbols only from those candidate files, expands bounded graph neighbors and finally reads exact line fragments with cryptographic/Git provenance. The same token-accounting contract used by Context Packet measures the final retrieval payload.

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
| Context ranking/filtering | Complete foundation | intent-aware selection, expiry/trust filtering, compression | Quality guardrails remain planned |
| Context Packet v1 | **Complete foundation** | PR #60 / Quality #226 | Extend as later evidence types require |
| Model-aware token accounting | **Complete foundation** | deterministic fallback + optional tiktoken reference | Broader benchmark corpus later |
| Progressive repository retrieval | **In review** | Issue #61 / PR #62 | Exact final-head CI + merge |
| Git verification | Complete foundation | repository/branch/commit/file verification | Persistent revision-aware symbol history |
| Code intelligence | Partial | Python/TS/JS/SQL symbol extraction + bounded graph | Persistent symbol evolution across revisions |
| Automatic continuation | Partial | sessions/checkpoints/handoff | project resolution + automatic milestone capture |
| Hybrid search/embeddings | Complete foundation | semantic + lexical fallback | broader quality/cost benchmarks |
| Evaluation/provenance suite | Complete foundation | existing agent regressions | context-quality golden scenarios planned |
| Dashboard/Galaxy | Partial foundation | localhost operational views + bounded graph | operational project map is roadmap Step 5 |
| Teams / remote collaboration | Out of scope | explicit product decision | no implementation planned |

## Context Packet v1 — complete foundation

PR #60 exposes a versioned packet through the real `ContextOptimizer → ModelRouter` delivery path.

The packet includes:

- contract version (`1.0`);
- current objective/intent;
- next safe action when explicitly available;
- compact provenance and verification state;
- hard token budget and final serialized token count;
- tokenizer/model identity and exact-vs-estimated mode;
- selected, dropped, compressed and token-cost metrics per context block.

Compatibility guarantees:

- `build_context()` keeps its historical caller contract;
- 256-token requests remain supported with compact control metadata;
- the active counter measures the complete serialized response after final routing annotations;
- unknown model/tokenizer mappings can fall back locally without a provider network call.

Validated fallback measurements against `gpt-4o` / `tiktoken:o200k_base`:

| Fixture | Reference | Deterministic fallback | Error |
|---|---:|---:|---:|
| Spanish prose | 69 | 80 | **15.94%** |
| Python/source code | 138 | 140 | **1.45%** |

Quality #226 passed the complete Ubuntu/Windows/macOS × Python 3.11–3.13 matrix, reference-tokenizer jobs, release artifacts and dependency audit.

## Progressive repository retrieval — PR #62

### Real runtime integration

`persistent_memory_mcp.runtime` installs `retrieve_repository_context` after Git verification and existing code intelligence. It therefore runs through the normal MCP server rather than being an offline helper.

### Progressive stages

1. **Repository map:** `git ls-files --cached --others --exclude-standard` identifies supported, non-ignored paths without loading all file contents into Python.
2. **Candidate files:** deterministic ranking combines path/name/language evidence with bounded local `git grep` content signals.
3. **Symbols:** only candidate files are parsed, reusing existing Python and regex-based TypeScript/JavaScript/SQL code-intelligence parsers.
4. **Graph neighbors:** known code edges expand only to configured depth/count limits.
5. **Fragments:** only selected symbols cause source-file reads; emitted evidence is a bounded line range instead of a whole-file dump.

### Provenance

Every emitted fragment contains:

- repository-relative path;
- symbol identifier/name/kind;
- start and end line;
- emitted-content SHA-256;
- whole-file SHA-256;
- repository Git commit;
- branch/ref;
- dirty-working-tree state.

### Safety and isolation

- absolute and traversal paths are rejected;
- resolved paths must remain below the verified repository root;
- missing/deleted candidates are skipped safely;
- `RuntimeSettings.ignore_patterns` and existing code-intelligence exclusions are enforced;
- recognized secrets are redacted from emitted fragments;
- repository code is read but never executed;
- files larger than the configured per-file cap are not parsed/read as fragments;
- total fragment bytes, files, symbols, neighbors, lines, pages and tokens are explicitly bounded.

### Deterministic pagination

The cursor contains only a bounded version/offset/fingerprint payload. Its fingerprint is derived from:

- Git commit;
- normalized query;
- ranked candidate paths;
- SHA-256 of ranked candidate files.

This means a cursor is rejected after a new relevant commit **or a relevant uncommitted candidate-file change**. It cannot silently continue against changed evidence.

### Token-budget integration

Progressive retrieval calls the same `resolve_token_counter()` / `measure_tokens()` contract used by Context Packet. The final serialized retrieval result is measured, and lower-priority payload sections are trimmed if necessary. If mandatory retrieval-control metadata alone cannot fit, the operation fails closed.

### Reproducible evaluation

`scripts/evaluate_repository_retrieval.py` creates an 80-file deterministic repository and asks for one exact symbol.

Current PR #62 evidence:

| Metric | Result |
|---|---:|
| Supported files mapped | **80** |
| Candidate files parsed | **6** |
| Parse fraction | **7.5%** |
| Selected fragments | **2** |
| Fragment bytes emitted | **284 B** |
| Target file lines | **125** |
| Target fragment lines | **7** |
| Target fragment/file ratio | **5.6%** |
| Final retrieval tokens | **1,305 / 1,400** |

The intended `services/security.py` file is both the top file candidate and source of the target fragment. The evaluation is wired into the Ubuntu/Windows/macOS reference jobs.

### Regression coverage

PR #62 covers:

- Python exact-symbol fragments and secret redaction;
- TypeScript function retrieval;
- JavaScript function retrieval;
- SQL table retrieval;
- bounded scanning in a repository with many unrelated files;
- exact symbol discovery even when the filename does not contain the symbol name;
- committed-state cursor invalidation;
- dirty-working-tree cursor invalidation without a commit;
- traversal/root-escape rejection;
- invalid limit rejection;
- total byte and final token budgets.

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
- automatic code execution from stored memory or repository retrieval.

## Post-v0.3 completion sequence

1. ✅ **Context Packet + token accounting** — PR #60 / MEM-36 complete.
2. 🟡 **Progressive repository retrieval** — PR #62 / MEM-37 in review.
3. ⬜ **Persistent code provenance/symbol evolution** — next after PR #62.
4. ⬜ **Context-quality regression guardrails**.
5. ⬜ **Operational project map / Galaxy** after the evidence layers above exist.

## Definition of done for PR #62 / MEM-37

- [x] Real MCP runtime tool implemented.
- [x] Map → file → symbol → fragment retrieval is progressive and bounded.
- [x] Existing Python/TypeScript/JavaScript/SQL parsers are reused rather than duplicated.
- [x] Path traversal/root escape/ignore-policy controls implemented.
- [x] Fragment path/lines/content hash/file hash/commit/ref provenance implemented.
- [x] Secret redaction applied to emitted fragments.
- [x] Deterministic ordering and bounded cursor pagination implemented.
- [x] Cursor detects committed and relevant uncommitted candidate changes.
- [x] Context Packet token-counter contract measures the final retrieval payload.
- [x] Reproducible 80-file retrieval evaluation added to CI.
- [x] Python/TS/JS/SQL, symbol-only, traversal, cursor and byte/token boundary regressions added.
- [x] README, ROADMAP, IMPLEMENTATION_STATUS and Notion synchronized in the branch.
- [ ] Exact final PR head passes the complete Ubuntu/Windows/macOS Quality matrix and artifact validation.
- [ ] PR #62 merged.
- [ ] MEM-37 marked complete in Notion.

Step 3 must not begin until this final gate is closed: persistent symbol evolution should build on the stable fragment/provenance contract rather than introduce another repository evidence path.
