from app.ingestion.extractors.base import ExtractedPage, ExtractionError


def extract_text(data: bytes) -> list[ExtractedPage]:
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError as exc:
        raise ExtractionError("Text file is not valid UTF-8") from exc
    return [ExtractedPage(page_number=None, text=text)]
