"""ingest: verify frozen corpus -> chunk -> embed -> index in Qdrant -> log run."""

from __future__ import annotations

import argparse
import json
import time
import uuid
from pathlib import Path

from rag.chunking import Chunk, chunk_fixed
from rag.config import Config, load_config
from rag.corpus import corpus_digest
from rag.runlog import write_run


def build_chunks(cfg: Config, files: list[str]) -> list[Chunk]:
    raw_dir = Path(cfg.corpus.raw_dir)
    out: list[Chunk] = []
    for rel in files:
        raw = (raw_dir / rel).read_text(encoding="utf-8", errors="replace")
        if cfg.chunking.strategy == "fixed":
            out += chunk_fixed(rel, raw, cfg.chunking.size_words, cfg.chunking.overlap_words)
        else:
            raise NotImplementedError(cfg.chunking.strategy)
    return out


def point_id(c: Chunk) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_URL, f"{c.doc_path}:{c.char_start}:{c.char_end}"))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", required=True)
    ap.add_argument("--recreate", action="store_true", help="drop collection if it exists")
    args = ap.parse_args()

    # heavy imports only when actually running
    from qdrant_client import QdrantClient, models
    from sentence_transformers import SentenceTransformer
    from tqdm import tqdm

    cfg = load_config(args.config)
    manifest = json.loads(Path(cfg.corpus.manifest).read_text())

    # 1. the corpus on disk must be exactly the frozen one
    digest = corpus_digest(Path(cfg.corpus.raw_dir), manifest["files"])
    if digest != manifest["content_digest"]:
        raise SystemExit("Corpus on disk differs from manifest. Run `make corpus`.")

    t0 = time.time()
    chunks = build_chunks(cfg, manifest["files"])
    print(f"{len(manifest['files'])} files -> {len(chunks)} chunks")

    model = SentenceTransformer(cfg.embedding.model)
    client = QdrantClient(url=cfg.index.qdrant_url)
    name = cfg.collection_name()

    if client.collection_exists(name):
        if not args.recreate:
            raise SystemExit(
                f"Collection {name} already exists (same chunking+embedding). "
                "Use --recreate to rebuild."
            )
        client.delete_collection(name)
    client.create_collection(
        name,
        vectors_config=models.VectorParams(size=cfg.embedding.dim, distance=models.Distance.COSINE),
    )

    batch = 64
    for i in tqdm(range(0, len(chunks), batch), desc="indexing"):
        part = chunks[i : i + batch]
        vecs = model.encode([c.text for c in part], normalize_embeddings=cfg.embedding.normalize)
        client.upsert(
            name,
            points=[
                models.PointStruct(
                    id=point_id(c),
                    vector=v.tolist(),
                    payload={
                        "doc_path": c.doc_path,
                        "chunk_index": c.chunk_index,
                        "char_start": c.char_start,
                        "char_end": c.char_end,
                        "title": c.title,
                        "text": c.text,
                    },
                )
                for c, v in zip(part, vecs)
            ],
        )

    run_dir = write_run(
        "ingest",
        cfg,
        {
            "collection": name,
            "corpus_commit": manifest["commit"],
            "corpus_digest": manifest["content_digest"],
            "n_files": len(manifest["files"]),
            "n_chunks": len(chunks),
            "duration_s": round(time.time() - t0, 1),
        },
    )
    print(f"collection={name}  run log: {run_dir}/run.json")


if __name__ == "__main__":
    main()
