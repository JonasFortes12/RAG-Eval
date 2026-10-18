.PHONY: setup up down corpus ingest test lint all

setup:
	uv sync

up:
	docker compose up -d --wait

down:
	docker compose down

corpus:            # download + freeze the corpus (writes data/corpus_manifest.json)
	uv run python scripts/fetch_corpus.py

ingest:            # chunk + embed + index, logs a run in runs/
	uv run python -m rag.ingest --config configs/baseline.yaml

test:
	uv run pytest -q

lint:
	uv run ruff check .

# Phase 0 exit criterion: reproduces everything from scratch
all: setup up corpus ingest
