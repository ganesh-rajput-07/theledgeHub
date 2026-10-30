from collections.abc import Callable

from app.ingestion.extractors.base import ExtractedPage, ExtractionError
from app.ingestion.extractors.docx import extract_docx
from app.ingestion.extractors.pdf import extract_pdf
from app.ingestion.extractors.text import extract_text

EXTRACTORS: dict[str, Callable[[bytes], list[ExtractedPage]]] = {
    "application/pdf": extract_pdf,
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document": extract_docx,
    "text/plain": extract_text,
    "text/markdown": extract_text,
}


def extract(data: bytes, mime_type: str) -> list[ExtractedPage]:
    extractor = EXTRACTORS.get(mime_type)
    if extractor is None:
        raise ExtractionError(f"Unsupported file type: {mime_type}")
    return extractor(data)


__all__ = ["EXTRACTORS", "ExtractedPage", "ExtractionError", "extract"]
