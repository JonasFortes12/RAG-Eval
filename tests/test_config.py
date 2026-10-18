import dataclasses

from rag.config import load_config


def test_index_hash_ignores_non_index_fields():
    cfg = load_config("configs/baseline.yaml")
    other = dataclasses.replace(cfg, name="other")
    assert cfg.index_hash() == other.index_hash()
    assert cfg.full_hash() != other.full_hash()


def test_index_hash_changes_with_chunking():
    cfg = load_config("configs/baseline.yaml")
    other = dataclasses.replace(
        cfg, chunking=dataclasses.replace(cfg.chunking, size_words=300))
    assert cfg.index_hash() != other.index_hash()
    assert cfg.collection_name() != other.collection_name()
