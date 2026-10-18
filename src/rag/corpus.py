"""Corpus freezing: a content digest over (path, sha256(content)) of all files."""
from __future__ import annotations

import hashlib
from pathlib import Path


def corpus_digest(raw_dir: Path, files: list[str]) -> str:
    h = hashlib.sha256()
    for rel in sorted(files):
        h.update(rel.encode())
        h.update(hashlib.sha256((raw_dir / rel).read_bytes()).digest())
    return h.hexdigest()
