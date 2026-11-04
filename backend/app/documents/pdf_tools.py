"""PDF page tools for the in-app workflow: merge, keep/extract pages, split, rotate, photo -> PDF, thumbnails.

Pure functions on bytes (no database), built on PyMuPDF. They never modify their input: callers store the
result as a new document, so originals stay untouched.
"""

import io
import re

import pymupdf

MAX_PAGES = 500  # per resulting document: keeps processing time and memory bounded
MAX_MERGE_DOCUMENTS = 50
IMAGE_TYPES = {".jpg": "image/jpeg", ".jpeg": "image/jpeg", ".png": "image/png"}
_A4 = pymupdf.paper_rect("a4")


class PdfToolError(ValueError):
    """A request the tools can't fulfil, with a message a user can act on."""


def _open(data: bytes) -> pymupdf.Document:
    try:
        doc = pymupdf.open(stream=data, filetype="pdf")
    except Exception as exc:
        raise PdfToolError("This file can't be read as a PDF") from exc
    if doc.needs_pass:
        doc.close()
        raise PdfToolError("This PDF is password protected")
    return doc


def _save(doc: pymupdf.Document) -> bytes:
    if doc.page_count == 0:
        raise PdfToolError("The result would have no pages")
    if doc.page_count > MAX_PAGES:
        raise PdfToolError(f"The result would have {doc.page_count} pages (limit {MAX_PAGES})")
    return doc.tobytes(garbage=3, deflate=True)


def page_count(data: bytes) -> int:
    with _open(data) as doc:
        return doc.page_count


def parse_pages(spec: str, total: int) -> list[int]:
    """'1-3, 5, 8-' -> [1, 2, 3, 5, 8, ..., total] (1-based, in the order given, no duplicates)."""
    if not spec or not spec.strip():
        raise PdfToolError("Choose at least one page")
    pages: list[int] = []
    for part in spec.replace(" ", "").split(","):
        match = re.fullmatch(r"(\d+)(?:-(\d*))?", part)
        if not match:
            raise PdfToolError(f"'{part}' is not a page or range (use e.g. 1-3, 5)")
        start = int(match.group(1))
        end = start if match.group(2) is None else (int(match.group(2)) if match.group(2) else total)
        if start < 1 or end > total or start > end:
            raise PdfToolError(f"Pages {part} are outside this document (it has {total} pages)")
        pages.extend(p for p in range(start, end + 1) if p not in pages)
    return pages


def merge(files: list[bytes]) -> bytes:
    """All pages of every PDF, in the given order."""
    if len(files) < 2:
        raise PdfToolError("Choose at least two PDFs to merge")
    if len(files) > MAX_MERGE_DOCUMENTS:
        raise PdfToolError(f"Merge at most {MAX_MERGE_DOCUMENTS} documents at once")
    with pymupdf.open() as out:
        for data in files:
            with _open(data) as src:
                if out.page_count + src.page_count > MAX_PAGES:
                    raise PdfToolError(f"The merged PDF would have more than {MAX_PAGES} pages")
                out.insert_pdf(src)
        return _save(out)


def select_pages(data: bytes, pages: list[int]) -> bytes:
    """A new PDF with only these pages (1-based), in this order. Also how pages are "deleted"."""
    with _open(data) as src:
        with pymupdf.open() as out:
            for page in pages:
                out.insert_pdf(src, from_page=page - 1, to_page=page - 1)
            return _save(out)


def split(data: bytes, groups: list[list[int]]) -> list[bytes]:
    """One new PDF per group of pages, e.g. [[1], [2], [3]] for one document per page."""
    if not groups:
        raise PdfToolError("Nothing to split")
    return [select_pages(data, group) for group in groups]


def rotate(data: bytes, pages: list[int], degrees: int) -> bytes:
    """A copy with the chosen pages turned clockwise by 90, 180 or 270 degrees."""
    if degrees not in (90, 180, 270):
        raise PdfToolError("Rotate by 90, 180 or 270 degrees")
    with _open(data) as doc:
        for page in pages:
            target = doc[page - 1]
            target.set_rotation((target.rotation + degrees) % 360)
        return _save(doc)


def image_to_pdf(data: bytes) -> bytes:
    """A phone photo or scan as a one-page A4 PDF. The camera's orientation tag is applied first, so photos
    taken sideways come out upright (PyMuPDF alone ignores it), and very large photos are scaled down."""
    from PIL import Image, ImageOps, UnidentifiedImageError

    try:
        with Image.open(io.BytesIO(data)) as image:
            upright = ImageOps.exif_transpose(image).convert("RGB")
    except (UnidentifiedImageError, OSError) as exc:
        raise PdfToolError("This image can't be read") from exc
    upright.thumbnail((3000, 3000))  # plenty for OCR at A4, keeps files small
    buffer = io.BytesIO()
    upright.save(buffer, "JPEG", quality=88)

    with pymupdf.open() as out:
        page = out.new_page(width=_A4.width, height=_A4.height)
        margin = 18  # points (about 6 mm) of white border around the photo
        area = pymupdf.Rect(margin, margin, page.rect.width - margin, page.rect.height - margin)
        page.insert_image(area, stream=buffer.getvalue(), keep_proportion=True)
        return _save(out)


def thumbnail(data: bytes, page: int, width: int = 240) -> bytes:
    """PNG preview of one page (1-based), for choosing pages in the UI."""
    with _open(data) as doc:
        if not 1 <= page <= doc.page_count:
            raise PdfToolError(f"Page {page} doesn't exist (the document has {doc.page_count} pages)")
        target = doc[page - 1]
        zoom = width / max(target.rect.width, 1)
        return target.get_pixmap(matrix=pymupdf.Matrix(zoom, zoom), alpha=False).tobytes("png")
