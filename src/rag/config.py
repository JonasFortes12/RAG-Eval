"""YAML config -> typed dataclasses, plus stable hashes for lineage."""
from __future__ import annotations

import hashlib
import json
from dataclasses import asdict, dataclass
from pathlib import Path

import yaml


@dataclass(frozen=True)
class CorpusCfg:
    manifest: str
    raw_dir: str


@dataclass(frozen=True)
class ChunkingCfg:
    strategy: str
    size_words: int
    overlap_words: int


@dataclass(frozen=True)
class EmbeddingCfg:
    model: str
    dim: int
    normalize: bool
    query_prefix: str = ""


@dataclass(frozen=True)
class IndexCfg:
    qdrant_url: str
    collection_prefix: str


@dataclass(frozen=True)
class Config:
    name: str
    corpus: CorpusCfg
    chunking: ChunkingCfg
    embedding: EmbeddingCfg
    index: IndexCfg

    def to_dict(self) -> dict:
        return asdict(self)

    def full_hash(self) -> str:
        return _hash(self.to_dict())

    def index_hash(self) -> str:
        """Only what changes the *index contents*: chunking + embedding.
        Changing e.g. k or the prompt must not trigger a re-index."""
        return _hash({"chunking": asdict(self.chunking), "embedding": asdict(self.embedding)})

    def collection_name(self) -> str:
        return f"{self.index.collection_prefix}_{self.index_hash()[:8]}"


def _hash(obj: dict) -> str:
    blob = json.dumps(obj, sort_keys=True).encode()
    return hashlib.sha256(blob).hexdigest()


def load_config(path: str | Path) -> Config:
    raw = yaml.safe_load(Path(path).read_text())
    return Config(
        name=raw["name"],
        corpus=CorpusCfg(**raw["corpus"]),
        chunking=ChunkingCfg(**raw["chunking"]),
        embedding=EmbeddingCfg(**raw["embedding"]),
        index=IndexCfg(**raw["index"]),
    )
