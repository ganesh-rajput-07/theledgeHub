import re
from dataclasses import dataclass

from app.rag.retriever import RetrievedChunk

# Matches [1], [2, 3] and [2,3]; adjacent markers like [1][2] match separately.
_MARKER = re.compile(r"\[(\d+(?:\s*,\s*\d+)*)\]")


@dataclass(frozen=True)
class Citation:
    citation_index: int
    chunk: RetrievedChunk


def extract_citations(answer: str, chunks: list[RetrievedChunk]) -> tuple[str, list[Citation]]:
    """Keep only markers that point at a chunk we actually retrieved; strip the rest so the user
    never sees a reference the backend cannot back with evidence."""
    cited: dict[int, Citation] = {}

    def replace(match: re.Match) -> str:
        valid = []
        for raw in match.group(1).split(","):
            number = int(raw)
            if 1 <= number <= len(chunks):
                valid.append(number)
                cited.setdefault(number, Citation(number, chunks[number - 1]))
        return "".join(f"[{n}]" for n in dict.fromkeys(valid))

    cleaned = _MARKER.sub(replace, answer)
    cleaned = re.sub(r"[ \t]+([.,;:!?])", r"\1", cleaned)  # tidy spaces left by removed markers
    cleaned = re.sub(r"[ \t]{2,}", " ", cleaned).strip()
    return cleaned, sorted(cited.values(), key=lambda c: c.citation_index)
