from itertools import pairwise

import pytest

from app.ingestion.chunker import chunk_pages
from app.ingestion.extractors.base import ExtractedPage


def count_words(text: str) -> int:
    return len(text.split())


def sentences(n: int, words_each: int = 5) -> str:
    return " ".join(f"Sentence{i} " + " ".join(["word"] * (words_each - 2)) + " end." for i in range(n))


def test_short_page_becomes_one_chunk():
    chunks = chunk_pages([ExtractedPage(1, "One short sentence.")], count_words, 50, 10)
    assert len(chunks) == 1
    assert chunks[0].page_number == 1
    assert chunks[0].content == "One short sentence."


def test_chunks_respect_size_and_overlap():
    chunks = chunk_pages([ExtractedPage(1, sentences(20))], count_words, chunk_size=20, chunk_overlap=5)
    assert len(chunks) > 1
    assert all(c.token_count <= 20 for c in chunks)
    for previous, current in pairwise(chunks):
        last_sentence = previous.content.split(". ")[-1]
        assert current.content.startswith(last_sentence.rstrip("."))


def test_chunks_never_span_pages_and_indexes_are_sequential():
    pages = [ExtractedPage(1, sentences(6)), ExtractedPage(2, sentences(6)), ExtractedPage(3, "")]
    chunks = chunk_pages(pages, count_words, chunk_size=15, chunk_overlap=5)
    assert {c.page_number for c in chunks} == {1, 2}
    assert [c.chunk_index for c in chunks] == list(range(len(chunks)))


def test_oversized_sentence_is_split_on_words():
    chunks = chunk_pages([ExtractedPage(None, " ".join(["word"] * 45))], count_words, 20, 0)
    assert [c.token_count for c in chunks] == [20, 20, 5]


def test_rejects_overlap_not_smaller_than_size():
    with pytest.raises(ValueError):
        chunk_pages([], count_words, chunk_size=10, chunk_overlap=10)
