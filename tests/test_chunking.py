import pytest

from rag.chunking import chunk_fixed, split_front_matter

DOC = "---\ntitle: Pods\nweight: 1\n---\n" + " ".join(f"w{i}" for i in range(500))


def test_front_matter_is_stripped_and_title_extracted():
    title, offset, body = split_front_matter(DOC)
    assert title == "Pods"
    assert body.startswith("w0")
    assert DOC[offset:].startswith("w0")


def test_offsets_point_into_raw_file():
    for c in chunk_fixed("a.md", DOC, 100, 20):
        assert DOC[c.char_start:c.char_end] == c.text


def test_overlap_and_coverage():
    chunks = chunk_fixed("a.md", DOC, 100, 20)
    assert len(chunks) == 6  # step 80 over 500 words
    assert chunks[1].text.split()[:20] == chunks[0].text.split()[-20:]
    assert chunks[-1].text.split()[-1] == "w499"


def test_short_doc_gives_single_chunk():
    assert len(chunk_fixed("a.md", "---\ntitle: x\n---\nhello world", 100, 20)) == 1


def test_invalid_params():
    with pytest.raises(ValueError):
        chunk_fixed("a.md", DOC, 10, 10)
