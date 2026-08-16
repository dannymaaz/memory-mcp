# Context Compiler quality evaluation

Persistent Memory MCP evaluates Context Compiler behavior locally and deterministically before retrieval changes can ship.

This document describes the public contract introduced by MEM-39 / PR #66. The evaluator does not call remote model providers, does not execute repository fixture code and does not include private user content or secrets.

## Why this exists

Token savings alone are not enough. A smaller context packet is useful only when it still retrieves the right files and symbols, fits the requested token budget and carries verifiable provenance.

The quality gate therefore checks retrieval quality, budget behavior and fail-safe provenance together.

## Versioned fixtures

The regression corpus lives in:

- `tests/fixtures/context_quality_corpus.json`
- `tests/fixtures/context_quality_thresholds.json`

Every evaluation reports:

- fixture version;
- evaluator version;
- threshold version;
- tokenizer identity;
- model identity when one is used.

The default CI evaluation uses the deterministic local tokenizer and no remote model.

## Metrics

The v1 evaluator reports:

- file recall@5;
- file precision@5;
- symbol recall@8;
- symbol precision@8;
- hard token-fit rate;
- token savings versus loading the supported repository corpus;
- provenance coverage for expected evidence;
- maximum task latency;
- safety pass rate.

The evaluator runs through the production `ProgressiveRepositoryRetriever` path instead of a benchmark-only retrieval implementation.

## Initial baseline and thresholds

| Metric | Initial observed baseline | CI threshold |
|---|---:|---:|
| File recall@5 | **1.000** | ≥ **1.000** |
| File precision@5 | **0.200** | ≥ **0.200** |
| Symbol recall@8 | **1.000** | ≥ **1.000** |
| Symbol precision@8 | **0.125** | ≥ **0.125** |
| Token-fit rate | **1.000** | ≥ **1.000** |
| Token savings | **0.7722** | ≥ **0.400** |
| Provenance coverage | **1.000** | ≥ **1.000** |
| Safety pass rate | **1.000** | ≥ **1.000** |
| Maximum task latency | **~149 ms** on the first reference run | ≤ **20,000 ms** |

The precision values are baseline protection floors, not claims of optimal ranking. Ranking work may improve them. Recall, hard budget, provenance and safety are not allowed to regress silently.

## Hard adversarial checks

Safety and provenance checks are boolean gates. They are not averaged away by otherwise strong retrieval scores.

The current suite requires all of the following:

- expired memory is excluded from compiled context;
- prompt-injection/untrusted memory is excluded by default;
- a dirty relevant repository change invalidates a previously issued retrieval cursor;
- a uniquely supported rename preserves logical symbol identity;
- the rename is classified explicitly;
- explicitly contradicted evidence remains retained and visibly contradicted;
- a dirty repository marks previously current symbol evidence as stale.

## Regression behavior

`persistent_memory_mcp.quality_guardrails.evaluate_quality_thresholds()` evaluates a metrics document against the versioned threshold document. Unit tests deliberately degrade recall, token fit, savings, provenance, safety and latency and require the result to fail.

The command-line evaluators return a non-zero exit code when their gate fails:

```bash
python scripts/evaluate_context_quality.py
python scripts/evaluate_context_adversarial.py
```

Both are executed in the reference Quality jobs on Ubuntu, Windows and macOS.

## Local reproduction

From a development checkout:

```bash
pip install -e ".[tokenizers]"
python scripts/evaluate_context_quality.py
python scripts/evaluate_context_adversarial.py
```

No provider credentials are required.

## Scope and interpretation

This suite measures deterministic local Context Compiler contracts. It does not claim to measure the quality of every possible LLM answer. Its purpose is narrower and enforceable: prevent known retrieval, token-budget, trust and provenance behavior from becoming worse without an explicit reviewed threshold change.
