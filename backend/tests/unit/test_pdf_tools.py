import io

import pymupdf
import pytest
from PIL import Image

from app.documents import pdf_tools
from app.documents.pdf_tools import PdfToolError
from tests.factories import make_pdf


def texts(data: bytes) -> list[str]:
    with pymupdf.open(stream=data, filetype="pdf") as doc:
        return [page.get_text().strip() for page in doc]


THREE = make_pdf(["Page one", "Page two", "Page three"])


@pytest.mark.parametrize(
    ("spec", "expected"),
    [("1", [1]), ("1-3", [1, 2, 3]), ("3, 1", [3, 1]), ("2-", [2, 3]), ("1,1,2", [1, 2]), (" 1 - 2 ", [1, 2])],
)
def test_parse_pages(spec, expected):
    assert pdf_tools.parse_pages(spec, 3) == expected


@pytest.mark.parametrize("spec", ["", "0", "4", "3-1", "a", "1-2-3", "1;2"])
def test_parse_pages_rejects_bad_input(spec):
    with pytest.raises(PdfToolError):
        pdf_tools.parse_pages(spec, 3)


def test_merge_keeps_order():
    merged = pdf_tools.merge([make_pdf(["B"]), make_pdf(["A1", "A2"])])
    assert texts(merged) == ["B", "A1", "A2"]


def test_merge_needs_two_files():
    with pytest.raises(PdfToolError, match="at least two"):
        pdf_tools.merge([THREE])


def test_select_pages_reorders_and_drops():
    assert texts(pdf_tools.select_pages(THREE, [3, 1])) == ["Page three", "Page one"]


def test_split_one_document_per_page():
    parts = pdf_tools.split(THREE, [[1], [2], [3]])
    assert [texts(p) for p in parts] == [["Page one"], ["Page two"], ["Page three"]]


def test_rotate_only_chosen_pages_and_leaves_input_alone():
    rotated = pdf_tools.rotate(THREE, [2], 90)
    with pymupdf.open(stream=rotated, filetype="pdf") as doc:
        assert [p.rotation for p in doc] == [0, 90, 0]
    with pymupdf.open(stream=THREE, filetype="pdf") as original:
        assert [p.rotation for p in original] == [0, 0, 0]
    with pytest.raises(PdfToolError):
        pdf_tools.rotate(THREE, [1], 45)


def test_password_protected_pdf_is_refused():
    doc = pymupdf.open()
    doc.new_page()
    locked = doc.tobytes(encryption=pymupdf.PDF_ENCRYPT_AES_256, user_pw="secret", owner_pw="secret")
    with pytest.raises(PdfToolError, match="password"):
        pdf_tools.page_count(locked)


def test_garbage_is_refused():
    with pytest.raises(PdfToolError, match="can't be read"):
        pdf_tools.page_count(b"%PDF-1.7 not really")


def test_sideways_phone_photo_comes_out_upright():
    # A landscape 400x200 photo whose EXIF tag says "rotate 90°" (how phones store portrait shots).
    image = Image.new("RGB", (400, 200), "white")
    exif = image.getexif()
    exif[0x0112] = 6  # Orientation: rotate 90 CW to display
    buffer = io.BytesIO()
    image.save(buffer, "JPEG", exif=exif)

    pdf = pdf_tools.image_to_pdf(buffer.getvalue())
    with pymupdf.open(stream=pdf, filetype="pdf") as doc:
        assert doc.page_count == 1
        (info,) = doc[0].get_image_info()
        box = pymupdf.Rect(info["bbox"])
        assert box.height > box.width  # placed portrait, i.e. upright


def test_unreadable_image_is_refused():
    with pytest.raises(PdfToolError, match="image"):
        pdf_tools.image_to_pdf(b"\xff\xd8\xff not a jpeg")


def test_thumbnail_is_a_png_of_the_page():
    png = pdf_tools.thumbnail(THREE, 2, width=120)
    assert png.startswith(b"\x89PNG")
    assert Image.open(io.BytesIO(png)).width == 120
    with pytest.raises(PdfToolError):
        pdf_tools.thumbnail(THREE, 9)


def test_page_limit(monkeypatch):
    monkeypatch.setattr(pdf_tools, "MAX_PAGES", 2)
    with pytest.raises(PdfToolError, match="limit 2"):
        pdf_tools.select_pages(THREE, [1, 2, 3])
