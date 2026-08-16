# Persistent Memory MCP implementation status

Last reconciled for the post-v0.3 Context Compiler phase and PR #66. Persistent Memory MCP remains a local-first, personal and localhost-only product.

## Executive summary

The local data-safety foundation is mature: private SQLite storage, owner/project isolation, WAL-safe backup, SHA-256 manifests, read-only health diagnostics, confirmed restore with rollback, versioned backup-first migrations, explicit upgrade tooling, deterministic SQLite connection lifecycle, validated Settings and cross-platform release-artifact testing.

The first three post-v0.3 Context Compiler milestones are complete: PR #60 established Context Packet v1 with hard serialized token budgets, PR #62 added progressive map → file → symbol → fragment repository retrieval with bounded cryptographic/Git provenance, and PR #64 added persistent commit-scoped symbol provenance/evolution with stable logical identity and typed evidence.

PR #66 / MEM-39 is the active fourth milestone: **Context Compiler quality regression guardrails**. It introduces a versioned non-sensitive golden corpus, deterministic quality metrics, explicit thresholds, deliberate-regression tests and adversarial provenance/trust scenarios so retrieval, budget or safety regressions block CI instead of silently shipping.

## Current capability matrix

| Capability | Status | Evidence | Remaining gap |
|---|---|---|---|
| Product CLI and local onboarding | Complete foundation | `init`, `doctor`, `status`, `health`, `serve` | Ongoing UX refinement |
| SQLite local-first storage | Complete | WAL, foreign keys, versioned migrations | Future numbered migrations as schema evolves |
| Verified backup + manifests | Complete foundation | Backup API, integrity check, SHA-256 sidecars | Optional rotation/signing refinements |
| Health + maintenance readiness | Complete foundation | Read-only checks and verified-backup awareness | Dashboard presentation |
| Confirmed restore | Complete foundation | Two-phase plan/execute, safety backup, rollback | Dashboard integration only |
| Installed upgrade lifecycle | Complete | v0.2.0 → current schema package regression | Future release migrations |
| Runtime Settings | Complete foundation | validated SQLite-first configuration | Specialized provider settings remain incremental |
| Context ranking/filtering | Complete foundation | intent-aware selection, expiry/trust filtering, compression | Ranking precision can be improved under fixed quality gates |
| Context Packet v1 | **Complete foundation** | PR #60 / Quality #226 | Extend as later evidence types require |
| Model-aware token accounting | **Complete foundation** | deterministic fallback + optional tiktoken reference | Broader benchmark corpus later |
| Progressive repository retrieval | **Complete** | PR #62 / MEM-37 | Ongoing ranking refinement behind CI thresholds |
| Persistent symbol evolution | **Complete** | PR #64 / MEM-38 / Quality #250 | Richer language relationships later |
| Git verification | Complete foundation | repository/branch/commit/file verification | Broader provenance consumers later |
| Code intelligence | **Complete foundation** | Python/TS/JS/SQL extraction + bounded graph + persistent revision history | Richer language parsers/relationships later |
| Context quality regression gates | **In review** | Issue #65 / PR #66 / MEM-39 | Exact final-head gate + merge |
| Automatic continuation | Partial | sessions/checkpoints/handoff | project resolution + automatic milestone capture |
| Hybrid search/embeddings | Complete foundation | semantic + lexical fallback | broader quality/cost benchmarks |
| Evaluation/provenance suite | **In review** | agent, token, retrieval, symbol-evolution, quality and adversarial regressions | finalize MEM-39 delivery gate |
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

## Progressive repository retrieval — complete

PR #62 exposes `retrieve_repository_context` through the real MCP runtime.

The retrieval service:

1. maps supported repository paths with `git ls-files` without loading every file;
2. ranks a bounded candidate set using path evidence and local bounded `git grep` signals;
3. parses only candidate files with the existing Python/TypeScript/JavaScript/SQL parsers;
4. expands bounded graph neighbors;
5. reads only selected line fragments.

Every fragment carries repository-relative path, line range, content SHA-256, file SHA-256 and Git commit/ref provenance. Traversal/root escape is rejected, configured ignore patterns apply, recognized secrets are redacted, code is never executed, and file/symbol/neighbor/byte/page/token limits are explicit.

Reproducible evaluation:

| Metric | Result |
|---|---:|
| Supported files mapped | **80** |
| Candidate files parsed | **6** |
| Parse fraction | **7.5%** |
| Selected fragments | **2** |
| Fragment bytes | **284 B** |
| Target fragment/file ratio | **5.6%** |
| Final retrieval tokens | **1,305 / 1,400** |

## Persistent symbol provenance and evolution — complete

PR #64 / MEM-38 advanced local SQLite to schema v2 with:

- `code_symbol_snapshot_runs` — one capture per owner/project/repository/commit;
- `code_symbol_snapshots` — bounded symbol identity/provenance without source bodies;
- `code_symbol_changes` — classified predecessor/current relationships;
- `code_symbol_links` — typed evidence to files, commits, tests and validated project memory.

Migration `0002` uses the existing migration contract: read-only preview, checksum verification, verified pre-migration backup and transactional apply. Fresh databases bootstrap migration history `[1, 2]`. The historical installed v0.2.0 upgrade regression requires both migrations and proves existing task data survives.

`SymbolEvolutionService.capture()` is owner/project/repository scoped, requires clean Git HEAD, is idempotent per captured commit, compares to the nearest persisted Git ancestor, stores bounded/redacted signatures and hashes instead of source bodies, and classifies `added`, `modified`, `moved`, `renamed`, `deleted` and `unchanged` symbols.

Logical identity is fail-safe: exact identity/body matches are preferred and a rename may use normalized bounded signature evidence only when unique on both old/new sides. Ambiguous candidates are never merged speculatively. Deterministic `rowid DESC` tie-breaking prevents same-second SQLite timestamp collisions from selecting stale snapshots.

`get_symbol_history` distinguishes `verified`, `stale`, `contradicted`, `missing_source` and `unverified` evidence. File/commit/test links may be inferred from verified code evidence; decision/task links require explicit same-owner/project validation. Evidence invalidation preserves history.

Reproducible evaluation covers Python, TypeScript, JavaScript and SQL and validated **1 renamed, 1 moved and 2 modified** symbols with rename identity preserved. Quality #250 passed the exact PR #64 HEAD across Ubuntu/Windows/macOS, Python 3.11–3.13, release artifacts, installed v0.2.0 upgrade and dependency audit. PR #64 is merged and MEM-38 is complete.

## Context Compiler quality regression guardrails — PR #66 / MEM-39

### Versioned corpus and evaluator

PR #66 adds:

- `tests/fixtures/context_quality_corpus.json` — non-sensitive versioned coding tasks with expected files/symbols;
- `tests/fixtures/context_quality_thresholds.json` — explicit reviewable thresholds and evaluator version;
- `scripts/evaluate_context_quality.py` — deterministic local evaluator over the real progressive retrieval path;
- `persistent_memory_mcp/quality_guardrails.py` — threshold comparison logic reusable by tests;
- `tests/test_quality_guardrails.py` — proves deliberate metric degradation fails the gate;
- `scripts/evaluate_context_adversarial.py` — fail-safe symbol provenance/dirty-Git adversarial evaluation.

No remote service, telemetry or repository fixture code execution is required.

### Metrics and baseline

The v1 corpus measures:

- file recall@5 and precision@5;
- symbol recall@8 and precision@8;
- hard token-fit rate;
- savings versus deterministic tokenization of the supported repository corpus;
- provenance completeness for expected evidence;
- maximum task latency;
- hard safety pass rate.

Initial deterministic baseline from the first validated reference run:

| Metric | Observed | Required threshold |
|---|---:|---:|
| File recall@5 | **1.000** | ≥ **1.000** |
| File precision@5 | **0.200** | ≥ **0.200** |
| Symbol recall@8 | **1.000** | ≥ **1.000** |
| Symbol precision@8 | **0.125** | ≥ **0.125** |
| Token-fit rate | **1.000** | ≥ **1.000** |
| Token savings | **0.7722** | ≥ **0.400** |
| Provenance coverage | **1.000** | ≥ **1.000** |
| Safety pass rate | **1.000** | ≥ **1.000** |
| Maximum task latency | **~149 ms** | ≤ **20,000 ms** |

The precision floor intentionally protects the current ranking baseline; it is not presented as an optimal precision target. Future ranking changes may raise precision while recall, budget, provenance and safety remain non-regressible.

### Adversarial requirements

The quality gate includes hard boolean scenarios that cannot be averaged away:

- expired memory is excluded from compiled context;
- prompt-injection/untrusted memory is excluded by default;
- dirty relevant repository changes invalidate an existing retrieval cursor;
- rename preserves the logical symbol identity when the unique bounded evidence contract allows it;
- rename is classified explicitly;
- contradicted evidence remains retained and visibly contradicted;
- dirty Git state marks previously current symbol evidence `stale`.

The cross-platform reference Quality jobs execute both `evaluate_context_quality.py` and `evaluate_context_adversarial.py` on Ubuntu, Windows and macOS. A regression in these safety/provenance checks returns a non-zero exit code and blocks CI.

### Current delivery state

- [x] versioned corpus and thresholds;
- [x] deterministic local evaluator using the production retrieval path;
- [x] fixture/evaluator/tokenizer/model identity recorded;
- [x] recall, precision, token fit, savings, provenance and latency metrics;
- [x] hard safety pass rate;
- [x] deliberate-regression test proves thresholds fail closed;
- [x] expired/untrusted and dirty-cursor adversarial scenarios;
- [x] rename/contradiction/dirty-Git symbol adversarial scenarios;
- [x] quality and adversarial gates wired into cross-platform reference CI;
- [ ] README, ROADMAP, IMPLEMENTATION_STATUS, public evaluation documentation and Notion fully reconciled;
- [ ] exact final PR #66 HEAD passes complete Quality after documentation sync;
- [ ] PR #66 merged and MEM-39 marked complete.

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
2. ✅ **Progressive repository retrieval** — PR #62 / MEM-37 complete.
3. ✅ **Persistent code provenance/symbol evolution** — PR #64 / MEM-38 complete; Quality #250 green.
4. 🟡 **Context-quality regression guardrails** — PR #66 / MEM-39 in review.
5. ⬜ **Operational project map / Galaxy** after MEM-39 closes.

## Definition of done for PR #66 / MEM-39

- [x] Versioned non-sensitive coding-task corpus exists.
- [x] Metrics and explicit thresholds are deterministic and locally reproducible.
- [x] The evaluator uses the real retrieval/token/provenance contracts.
- [x] Deliberate quality regression is proven to fail threshold evaluation.
- [x] Expired and untrusted memory cases fail closed.
- [x] Dirty repository retrieval state invalidates stale cursors.
- [x] Rename identity, contradiction preservation and dirty-Git stale evidence are adversarial gates.
- [x] Cross-platform reference CI invokes quality and adversarial evaluators.
- [ ] Public and repository documentation synchronized with baseline and thresholds.
- [ ] Exact final PR HEAD passes Ubuntu/Windows/macOS Quality and release-artifact validation.
- [ ] PR #66 merged and MEM-39 marked complete in Notion.

After MEM-39 closes, Step 5 can use verified quality/provenance signals to evolve Galaxy into an operational project map instead of building another unmeasured visualization layer.
