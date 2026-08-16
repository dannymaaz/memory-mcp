# Operational project map and risk-oriented Galaxy

Persistent Memory MCP exposes a bounded, read-only operational projection over the local project memory and the persisted Git/symbol evidence introduced by the Context Compiler roadmap.

The operational map is designed to answer questions such as:

- Which local projects need attention?
- Which files and symbols changed in the latest persisted snapshot?
- Which tasks or decisions have verified symbol evidence?
- Which evidence is stale, contradicted, missing or unverified?
- Which project areas are high-risk without loading full source or memory bodies?

It is **not** a second repository scanner, a remote monitoring service or an execution surface. It composes already persisted local data and remains localhost-only.

## Data model

`OperationalMapService` reads existing SQLite records and produces compact nodes and edges.

Supported hierarchy and evidence relationships include:

```text
project
  └─ repository
      └─ file
          └─ symbol
              ├─ task
              ├─ decision
              ├─ file/test evidence
              └─ deployment evidence

project
  ├─ warning
  ├─ task
  └─ decision
```

Relationships are emitted only from existing project records or persisted `code_symbol_*` evidence. The map does not invent a verified relationship when no persisted evidence exists.

## Verification and risk states

Operational nodes may expose these persisted verification states:

- `verified`
- `stale`
- `contradicted`
- `missing_source`
- `unverified`

Risk is a compact projection used for sorting and visualization:

- `critical`
- `high`
- `medium`
- `low`
- `none`

Examples:

- contradicted evidence maps to critical risk;
- stale or missing-source evidence maps to high risk;
- unverified evidence maps to medium risk;
- a blocked task raises the relevant project/task risk;
- an active high/critical warning raises project risk.

Risk is operational prioritization metadata; it does not replace the underlying verification state.

## Current-change semantics

`changed_only=true` means **changed in the latest persisted snapshot run for each repository**. It does not mean “changed at any point in history.”

The changed-area projection starts from currently changed files/symbols and keeps only:

- their direct evidence/operational neighbors;
- the file/repository/project hierarchy required to understand them.

It deliberately avoids fan-out from the project node into unrelated tasks or decisions.

## Bounded payload contract

Default request bounds are implemented by `OperationalMapLimits` and have hard maximums:

| Limit | Default | Hard maximum |
|---|---:|---:|
| Projects | 50 | 100 |
| Repositories per project | 12 | 20 |
| Nodes | 250 | 500 |
| Edges | 750 | 1,500 |
| Records per memory kind | 50 | 200 |

Ordering is deterministic. The response reports its active limits and whether the graph was truncated.

Operational node payloads intentionally omit full source/memory bodies such as:

- source signatures/bodies;
- decision details;
- task details;
- warning message bodies as separate fields;
- session/checkpoint bodies;
- absolute repository roots.

Short display labels are bounded and passed through the existing secret redaction logic. The response also reports any redaction categories applied.

## Owner isolation

Operational endpoints are owner-scoped.

Owner resolution is fail-closed:

1. use the explicitly configured dashboard owner (`--owner-id` or `OWNER_ID`) when present;
2. otherwise infer the owner only when the local database contains exactly one project owner;
3. with no inferable owner or multiple owners, return a client error rather than mixing project data.

A project outside the active owner scope is rejected.

## Local HTTP surface

The existing legacy Dashboard/Galaxy endpoints remain available. MEM-40 adds a separate operational surface:

```text
GET /api/operational/projects
GET /api/operational/graph?project_id=<id>
GET /api/operational/export.json?project_id=<id>
GET /galaxy/operational?project_id=<id>
```

Useful query parameters:

- `limit`
- `verification=verified|stale|contradicted|missing_source|unverified`
- `risk=none|low|medium|high|critical`
- `changed_only=true|false` for a project graph

`changed_only` requires a `project_id`.

The server remains loopback-only. The operational endpoints inherit the existing no-store, `nosniff`, frame-deny and CSP headers. They do not provide mutation, deployment or code-execution actions.

## Operational Galaxy

`/galaxy/operational` reuses the dependency-free Galaxy renderer while adding operational-only controls:

- risk filter;
- verification-state filter;
- changed-only filter;
- visible critical/high/medium risk treatment;
- stale/contradicted visual states;
- compact counts for changed nodes, missing evidence and risk/verification state;
- SVG/PNG export names separated from the legacy knowledge Galaxy.

The legacy `/galaxy` behavior remains compatible. Operational controls are hidden when rendering a legacy knowledge graph.

## Reproducible bounds and latency evaluation

`scripts/evaluate_operational_map.py` builds a local non-sensitive SQLite fixture with:

- 20 projects in the active owner scope plus a foreign-owner project;
- 120 symbols across 12 files in the focus project;
- 20 tasks;
- 24 currently changed symbols concentrated in a bounded affected area.

The CI fixture uses:

- max projects: 20;
- max nodes: 180;
- max edges: 400;
- max records per kind: 50;
- maximum overview time: 5,000 ms;
- maximum graph time: 5,000 ms.

The validated cross-platform runs keep the same structural output:

| Metric | Observed |
|---|---:|
| Overview projects | **20** |
| Full graph nodes | **154** |
| Full graph edges | **173** |
| Changed-area nodes | **55** |
| Changed-area edges | **74** |

Reference latency examples:

| Platform | Overview | Full graph | Changed-area graph |
|---|---:|---:|---:|
| Ubuntu | **3.04 ms** | **6.26 ms** | **4.35 ms** |
| Windows | **4.99 ms** | **8.08 ms** | **5.36 ms** |
| macOS | **5.65 ms** | **8.56 ms** | **4.15 ms** |

These are regression-fixture observations, not production latency guarantees. CI uses the deliberately wider 5-second ceiling to catch pathological growth without making normal hosted-runner variance flaky.

Every reference run also requires:

- owner isolation;
- node/edge/project bounds;
- read-only output;
- secret redaction;
- no absolute repository root leakage;
- no full body/source fields;
- current-change filtering that actually reduces the graph.

## Local reproduction

From a development checkout:

```bash
python scripts/evaluate_operational_map.py
```

The evaluation is provider-free and does not execute repository fixture code.

## Scope

The operational map is intentionally:

- local-first;
- SQLite-backed;
- read-only;
- localhost-only;
- owner/project isolated;
- bounded and deterministic;
- based on persisted evidence state.

It does **not** independently re-run live Git verification on every dashboard request. If live repository state changes, the normal capture/verification flows must update persisted evidence; the operational map projects the evidence state already stored by those flows.
