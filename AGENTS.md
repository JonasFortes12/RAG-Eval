# AGENTS.md

Guide for coding agents working on this repository. Read it before changing anything.

## What this project is

A RAG system over the **Kubernetes documentation** (`kubernetes/website`, `content/en/docs/{concepts,tasks}`),
built primarily to be **measured**, not to be clever. The deliverables are:

1. A config-driven RAG pipeline: `ingest → chunk → index → retrieve → (rerank) → generate → evaluate`.
2. A hand-reviewed evaluation dataset (80–100 questions).
3. Controlled experiments (ablations) reported with bootstrap confidence intervals.
4. A **continuous-validation CI gate** that blocks PRs which regress quality, with the gate itself
   validated (A/A false-alarm rate, detection rate on injected regressions).

The corpus choice is final. Do not switch corpora or add a second one.

## Current status

- **Phase 0 (foundations): in progress.** Corpus fetch/freeze, fixed chunking, dense indexing in
  Qdrant, run logging, unit tests.
- Not yet implemented: retrieval API, generation, FastAPI service, eval metrics/runner, LLM judge,
  experiments, CI workflows, reports. `src/evals/`, `ci/`, `prompts/`, `reports/` are placeholders.

Roadmap and exit criteria:

| Phase | Scope | Exit criterion |
|---|---|---|
| 0 Foundations | repo, Docker Compose, frozen corpus, run logging | one command (`make all`) reproduces ingestion from scratch |
| 1 Baseline RAG | fixed chunks, embeddings, dense search, generation with citations, FastAPI | answers with citations; logs latency and cost per query |
| 2 Eval dataset | 80–100 reviewed questions, dev/test split, judge calibration | dataset frozen, judge agreement measured |
| 3 Experiments | one-variable ablations, then small grid | results table with CIs + justified winning config |
| 4 CI gate | fast (retrieval-only) + full (with judge) levels | gate validated with A/A tests and injected regressions |
| 5 Report | public report, trade-off plots | — |

Work on the current phase. Keep the baseline deliberately simple; sophistication belongs in Phase 3
as an experiment variable, not in the baseline.

## Repository layout

```
configs/      one YAML per experiment (baseline.yaml is the reference)
data/
  raw/k8s/    sparse git checkout of kubernetes/website (gitignored)
  corpus_manifest.json   pinned commit + file list + content digest (COMMITTED)
  eval/       evaluation dataset (JSONL)
src/rag/      config, corpus, chunking, ingest, runlog (pipeline code)
src/evals/    metrics, judge, runner (Phase 2+)
prompts/      prompts versioned as code (Phase 1+)
scripts/      one-off entry points (fetch_corpus.py)
tests/        unit tests + quality regression tests
ci/           gate and report scripts (Phase 4)
runs/         run records, one dir per execution (gitignored)
reports/      results and plots
```

## Commands

```bash
make setup    # uv sync (Python 3.12+)
make up       # start Qdrant (pinned image) via docker compose
make corpus   # fetch + freeze corpus -> data/corpus_manifest.json
make ingest   # chunk + embed + index; writes runs/<ts>-ingest-<hash>/run.json
make test     # uv run pytest -q
make lint     # uv run ruff check .
make all      # setup + up + corpus + ingest
```

Always use `uv run ...`; never `pip install` into the environment. Add dependencies with `uv add`
(or `uv add --dev`). Unit tests must not require Qdrant, network, or model downloads — keep heavy
imports inside `main()`/functions, as `rag/ingest.py` does.

Before finishing a change: `make lint && make test` must pass.

## Non-negotiable invariants

These exist so that runs are comparable and the CI gate means something. Breaking any of them
silently invalidates results.

1. **Everything is config-driven.** New behavior is selected by a YAML field, not by editing code
   paths or hardcoding constants. Add the field to the matching dataclass in `rag/config.py`.
2. **Lineage on every run.** Any execution that produces numbers (ingest, retrieval eval, full eval,
   experiment) must call `rag.runlog.write_run`, which records git SHA (with `-dirty`), full config
   hash, index hash, and config. Add to `extra`: corpus commit/digest, model IDs, prompt version,
   and anything needed to reproduce the result. No run record → result does not exist.
3. **Index hash covers only index contents.** `Config.index_hash()` hashes chunking + embedding
   only; the Qdrant collection name derives from it. When adding a config section, decide
   explicitly whether it changes what is stored in the index:
   - yes (chunking params, embedding model/prefix/normalization, indexed fields) → include in `index_hash`;
   - no (k, reranker, prompt, generator, judge) → exclude, so changing it never forces a re-index.
   Update `tests/test_config.py` accordingly.
4. **Frozen corpus.** Ingest refuses to run if the on-disk digest differs from
   `data/corpus_manifest.json`. Never bypass that check. Moving the corpus to a new commit is a
   deliberate act (`fetch_corpus.py --ref <sha> --update`) and invalidates comparisons with old runs.
5. **Ground truth is (doc, char span), never chunk IDs.** Chunk IDs change whenever chunking
   changes. Every chunker must emit `char_start`/`char_end` offsets into the **raw file** (front
   matter included) such that `raw[char_start:char_end] == text`. Retrieval hits are scored by
   overlap between retrieved spans and labeled evidence spans. Point IDs are derived from
   `(doc_path, char_start, char_end)`.
6. **The test split is sealed.** Questions with `"split": "test"` (~30 %) are only evaluated at the
   end of Phase 3. Do not tune on them, inspect per-question results on them, or include them in
   dev runs unless the task explicitly says so.
7. **Pin versions.** Exact model IDs for embedder, reranker, generator and judge (no "latest"
   aliases); pinned Docker image tags; temperature 0 for generation and judging.
8. **Judge ≠ generator.** The LLM judge must be a different model from the generator (avoids
   self-preference bias). The judge is only usable as a gate after measured agreement with 30
   human-annotated answers.

## Evaluation dataset format

`data/eval/*.jsonl`, one question per line (see `questions.example.jsonl`):

```json
{"id": "q001", "type": "factual", "split": "dev",
 "question": "...",
 "evidence": [{"doc": "content/en/docs/...md", "char_start": 1234, "char_end": 1890}],
 "reference_answer": "...", "answerable": true}
```

- `type`: `factual` (~50 %), `multi_hop` (~20 %), `ambiguous` (~10 %), `unanswerable` (~20 %).
- `doc` is relative to `data/raw/k8s`, matching manifest paths.
- Unanswerable questions have `evidence: []`, `reference_answer: null`, `answerable: false`; they
  measure correct abstention.
- Questions may be LLM-proposed but **every one is human-reviewed**. Agents must not add
  unreviewed questions to the dataset; put drafts in a separate file clearly marked as drafts.

## Metrics

| Layer | Metrics |
|---|---|
| Retrieval | recall@k, MRR, nDCG@k (span-overlap based) |
| Generation | faithfulness to context, answer correctness, correct-abstention rate |
| Operations | latency p50/p95, tokens and cost per query |

Statistics: every comparison uses a **paired bootstrap over questions** and reports a confidence
interval. With ~100 questions small differences are noise — say so instead of declaring winners.
Fix random seeds for bootstrap so reports are reproducible.

## Experiments (Phase 3)

One variable at a time against the baseline, then a small grid of the best options:

- chunking: 256 / 512 / 1024 tokens, with/without overlap, structure-aware (sections)
- embeddings: 2–3 models (bge / e5 families, local via sentence-transformers)
- retrieval: dense vs BM25 vs hybrid
- reranking: none vs cross-encoder (bge-reranker) top-20 → 5
- context k: 3 / 5 / 10

Each experiment is a new file in `configs/` — never mutate `baseline.yaml` to run an experiment.
Note: chunk size is currently measured in **words** (`size_words`) as a token approximation; a
token-based chunker would be a new strategy, not a silent change to `fixed`.

## CI gate (Phase 4)

| Level | Trigger | Runs | Target time |
|---|---|---|---|
| Fast | every PR touching `src/`, `configs/`, `prompts/` | retrieval only, no LLM, deterministic | a few minutes |
| Full | nightly or PR label | whole pipeline with judge, 3 repeats | ≤ ~30 min |

Gate rule: compare the PR against the saved `main` baseline with a paired bootstrap per question;
fail only if the drop is statistically distinguishable **and** larger than a configured threshold
(e.g. recall@5 drop > 3 points). The PR gets a comment with a delta table and the worst-regressed
questions.

Non-determinism controls: temperature 0, cache LLM calls keyed by hash of the full input (model ID +
prompt + params), and a hard cost budget per run that aborts when exceeded.

Gate self-validation (a key deliverable): A/A runs to measure false-alarm rate, and injected
regressions (tiny chunks, degraded prompt, reranker off, truncated corpus) to measure detection
rate. Target statement form: "detects 9/10 regressions of ≥4 points with 2 % false alarms".

## Stack

Python 3.12 + uv · Docker Compose · Qdrant (`qdrant/qdrant:v1.12.4`, dense now, hybrid later) ·
sentence-transformers (`BAAI/bge-small-en-v1.5` baseline, query prefix in config) · cross-encoder
reranker (experiment variable) · generator and judge via API with pinned IDs · Langfuse or MLflow
for run tracking (not yet chosen; `runs/*/run.json` is the source of truth until then) ·
GitHub Actions + pytest.

## Coding conventions

- Ruff, line length 100. `from __future__ import annotations` at the top of modules.
- Frozen dataclasses for config and data records; pure functions for chunking/metrics so they are
  unit-testable without services.
- Short module docstring stating the module's role and the invariant it protects; few comments.
- Every new chunker, metric, or gate rule ships with unit tests (see `tests/test_chunking.py` for
  the offset-roundtrip pattern). Metrics need tests on hand-computed toy cases.
- Fail loudly (`SystemExit` with an actionable message) rather than silently degrading — e.g.
  existing collection without `--recreate`, corpus digest mismatch.

## Things not to do

- Don't commit `data/raw/`, `runs/`, model weights, or API keys. Do commit `data/corpus_manifest.json`.
- Don't label or score by chunk ID.
- Don't look at, tune on, or print per-question results for the test split.
- Don't change the baseline config to make a number go up; add an experiment config.
- Don't compare runs that differ in corpus digest, or report a difference without a CI.
- Don't use the generator model as the judge.
- Don't add LLM calls to the fast CI level or to unit tests.

## Threats to validity (keep in mind; listed in the final report)

LLM-proposed questions are easier to retrieve than real user questions; LLM judges have verbosity
and self-preference bias; a small dataset limits resolution; results hold for this corpus and may
not generalize.
