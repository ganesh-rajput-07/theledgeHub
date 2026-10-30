import logging
from functools import lru_cache

import pymupdf

from app.core.config import get_settings

MIN_LINE_CONFIDENCE = 0.5


@lru_cache
def _engine():
    # Imported lazily: loading the ONNX models takes a moment and most PDFs never need OCR.
    from rapidocr import RapidOCR

    engine = RapidOCR(
        params={
            # The 0/180-degree line classifier flips correct lines on clean scans and garbles them.
            "Global.use_cls": False,
            "Global.log_level": "warning",
            # Detection cost grows with pixel count; cap the long side. Recognition still reads
            # text crops from the full-resolution render, so accuracy is kept.
            "Det.limit_type": "max",
            "Det.limit_side_len": get_settings().ocr_max_side_len,
            "EngineConfig.onnxruntime.enable_cpu_mem_arena": True,
        }
    )
    logging.getLogger("RapidOCR").setLevel(logging.WARNING)
    return engine


def ocr_page(page: pymupdf.Page, dpi: int) -> str:
    """Render a page to an image and read its text, dropping low-confidence lines."""
    image = page.get_pixmap(dpi=dpi, alpha=False).tobytes("png")
    result = _engine()(image)
    lines = zip(result.txts or (), result.scores or (), strict=False)
    return "\n".join(text for text, score in lines if score >= MIN_LINE_CONFIDENCE)
