import pymupdf

from app.core.config import get_settings
from app.ingestion.extractors.base import ExtractedPage, ExtractionError
from app.ingestion.ocr import ocr_page


def _needs_ocr(page: pymupdf.Page, text: str, min_chars: int) -> bool:
    # Scanned pages carry their content as images; blank pages have neither text nor images.
    return len(text.strip()) < min_chars and bool(page.get_images())


def extract_pdf(data: bytes) -> list[ExtractedPage]:
    settings = get_settings()
    try:
        with pymupdf.open(stream=data, filetype="pdf") as doc:
            if doc.needs_pass:
                raise ExtractionError("PDF is password protected")
            pages = []
            for index, page in enumerate(doc):
                text = page.get_text("text", sort=True)
                if settings.ocr_enabled and _needs_ocr(page, text, settings.ocr_min_text_chars):
                    pages.append(ExtractedPage(index + 1, ocr_page(page, settings.ocr_dpi), ocr=True))
                else:
                    pages.append(ExtractedPage(index + 1, text))
            return pages
    except ExtractionError:
        raise
    except Exception as exc:
        raise ExtractionError(f"Could not read PDF: {exc}") from exc
