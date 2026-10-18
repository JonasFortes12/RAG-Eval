# rag-eval

RAG over the Kubernetes docs, built to be **evaluated**, then guarded by a
continuous-validation pipeline (CI gate on retrieval/answer quality).

## Quickstart (Phase 0)

```bash
make setup     # uv sync
make up        # Qdrant via docker compose
make corpus    # fetch + freeze corpus -> data/corpus_manifest.json (commit this file)
make ingest    # chunk + embed + index; writes runs/<...>/run.json
make test
```

`make all` reproduces everything from scratch (Phase 0 exit criterion).

## Principles

- **Config-driven**: one YAML per experiment; collection name derives from the hash of
  chunking+embedding, so different indexes never collide.
- **Lineage**: every run logs git SHA, config hash, corpus commit+digest, model IDs.
- **Labels survive re-chunking**: eval ground truth is (doc, char span), never chunk IDs.
- **Frozen corpus**: ingest refuses to run if files differ from the manifest digest.

## Roadmap

0 foundations -> 1 baseline RAG -> 2 eval dataset -> 3 experiments -> 4 CI gate -> 5 report
