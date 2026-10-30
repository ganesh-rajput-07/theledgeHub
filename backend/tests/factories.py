import io

import docx
import pymupdf


def make_pdf(pages: list[str], fontsize: float = 8) -> bytes:
    doc = pymupdf.open()
    for text in pages:
        page = doc.new_page()
        if text:
            overflow = page.insert_textbox(pymupdf.Rect(36, 36, 576, 806), text, fontsize=fontsize)
            assert overflow >= 0, "test text does not fit on one PDF page"
    data = doc.tobytes()
    doc.close()
    return data


def make_docx(paragraphs: list[str]) -> bytes:
    document = docx.Document()
    for text in paragraphs:
        document.add_paragraph(text)
    buffer = io.BytesIO()
    document.save(buffer)
    return buffer.getvalue()


def make_scanned_pdf(pages: list[str]) -> bytes:
    """Image-only PDF: each page is a picture of text with no text layer, like a scanner produces."""
    scan = pymupdf.open()
    for page_bytes in (make_pdf([text], fontsize=14) for text in pages):
        with pymupdf.open(stream=page_bytes, filetype="pdf") as rendered:
            png = rendered[0].get_pixmap(dpi=150).tobytes("png")
        page = scan.new_page()
        page.insert_image(page.rect, stream=png)
    data = scan.tobytes()
    scan.close()
    return data
