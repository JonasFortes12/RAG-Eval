"""Chunking that keeps character offsets into the RAW file.

Offsets matter: the eval dataset labels ground truth as (doc, char span), so
it survives any change in chunking strategy (see Phase 2).
"""
from __future__ import annotations

import re
from dataclasses import dataclass

_FRONT_MATTER = re.compile(r"\A---\s*\n.*?\n---\s*\n", re.DOTALL)
_TITLE = re.compile(r"^title:\s*[\"']?(.+?)[\"']?\s*$", re.MULTILINE)
_WORD = re.compile(r"\S+")


@dataclass(frozen=True)
class Chunk:
    doc_path: str
    chunk_index: int
    char_start: int  # offsets relative to the raw file (front matter included)
    char_end: int
    text: str
    title: str


def split_front_matter(raw: str) -> tuple[str, int, str]:
    """Return (title, body_offset, body)."""
    m = _FRONT_MATTER.match(raw)
    if not m:
        return "", 0, raw
    t = _TITLE.search(m.group(0))
    return (t.group(1) if t else ""), m.end(), raw[m.end():]


def chunk_fixed(doc_path: str, raw: str, size_words: int, overlap_words: int) -> list[Chunk]:
    if size_words <= 0 or not 0 <= overlap_words < size_words:
        raise ValueError("need size_words > 0 and 0 <= overlap_words < size_words")

    title, body_offset, body = split_front_matter(raw)
    words = list(_WORD.finditer(body))
    step = size_words - overlap_words
    chunks: list[Chunk] = []
    for i, start in enumerate(range(0, max(len(words), 1), step)):
        window = words[start:start + size_words]
        if not window:
            break
        s, e = window[0].start(), window[-1].end()
        chunks.append(
            Chunk(
                doc_path=doc_path,
                chunk_index=i,
                char_start=body_offset + s,
                char_end=body_offset + e,
                text=body[s:e],
                title=title,
            )
        )
        if start + size_words >= len(words):
            break
    return chunks
