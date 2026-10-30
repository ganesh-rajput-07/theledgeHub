from dataclasses import dataclass


@dataclass(frozen=True)
class ExtractedPage:
    """Text of one page. page_number is None for formats without fixed pages (DOCX, TXT, MD)."""

    page_number: int | None
    text: str
    ocr: bool = False


class ExtractionError(Exception):
    pass
