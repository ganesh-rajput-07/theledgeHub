import re
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from functools import lru_cache

from app.ingestion.extractors.base import ExtractedPage

TokenCounter = Callable[[str], int]

_SENTENCE_END = re.compile(r"(?<=[.!?])\s+")


@dataclass
class Chunk:
    chunk_index: int
    content: str
    page_number: int | None
    token_count: int
    metadata: dict = field(default_factory=dict)


@lru_cache
def get_token_counter(model_name: str) -> TokenCounter:
    """Count tokens with the embedding model's own tokenizer, so chunk sizes match what it sees."""
    from transformers import AutoTokenizer

    tokenizer = AutoTokenizer.from_pretrained(model_name)
    tokenizer.model_max_length = 1_000_000  # we only count; silences the "sequence too long" warning
    return lambda text: len(tokenizer(text, add_special_tokens=False)["input_ids"])


def _split_units(text: str) -> list[str]:
    units = []
    for paragraph in text.split("\n\n"):
        units.extend(s.strip() for s in _SENTENCE_END.split(paragraph) if s.strip())
    return units


def _split_long_unit(unit: str, count_tokens: TokenCounter, max_tokens: int) -> list[str]:
    """Break a sentence that alone exceeds max_tokens into word-boundary pieces."""
    pieces, current = [], []
    for word in unit.split():
        if current and count_tokens(" ".join([*current, word])) > max_tokens:
            pieces.append(" ".join(current))
            current = []
        current.append(word)
    if current:
        pieces.append(" ".join(current))
    return pieces


def chunk_pages(
    pages: Iterable[ExtractedPage],
    count_tokens: TokenCounter,
    chunk_size: int,
    chunk_overlap: int,
) -> list[Chunk]:
    """Pack sentences into chunks of at most chunk_size tokens, carrying trailing sentences
    (up to chunk_overlap tokens) into the next chunk. Chunks never span pages, so every chunk
    maps to exactly one citable page."""
    if not 0 <= chunk_overlap < chunk_size:
        raise ValueError("chunk_overlap must be >= 0 and smaller than chunk_size")

    chunks: list[Chunk] = []

    def emit(units: list[tuple[str, int]], page: ExtractedPage) -> None:
        content = " ".join(text for text, _ in units)
        chunks.append(
            Chunk(
                chunk_index=len(chunks),
                content=content,
                page_number=page.page_number,
                token_count=count_tokens(content),
                metadata={"ocr": True} if page.ocr else {},
            )
        )

    for page in pages:
        units: list[tuple[str, int]] = []
        for unit in _split_units(page.text):
            tokens = count_tokens(unit)
            if tokens > chunk_size:
                units.extend((p, count_tokens(p)) for p in _split_long_unit(unit, count_tokens, chunk_size))
            else:
                units.append((unit, tokens))

        current: list[tuple[str, int]] = []
        current_tokens = 0
        for unit, tokens in units:
            if current and current_tokens + tokens > chunk_size:
                emit(current, page)
                overlap: list[tuple[str, int]] = []
                overlap_tokens = 0
                for prev in reversed(current):
                    if overlap_tokens + prev[1] > chunk_overlap:
                        break
                    overlap.insert(0, prev)
                    overlap_tokens += prev[1]
                current, current_tokens = overlap, overlap_tokens
                while current and current_tokens + tokens > chunk_size:
                    current_tokens -= current.pop(0)[1]
            current.append((unit, tokens))
            current_tokens += tokens
        # The loop always appends a new unit after emitting, so this is never a pure-overlap repeat.
        if current:
            emit(current, page)
    return chunks
