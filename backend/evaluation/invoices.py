# ruff: noqa: S311  (seeded test-data generator, not security-sensitive)
"""Synthetic Indian GST invoices with ground truth, for benchmarking local extraction models.

    python -m evaluation.invoices [--count 30] [--out evaluation/invoices_data]

Writes `invoice_XX.pdf` plus `truth.json`. Seeded, so every run produces the same files. Three layouts;
every third invoice is a rasterised, slightly rotated and noisy "scan" (needs OCR). A few invoices are
deliberate traps: exact duplicates, a wrong total, and a wrong GST amount. `truth.json` records which.
"""

import argparse
import io
import json
import random
import string
from datetime import date, timedelta
from pathlib import Path

import pymupdf
from PIL import Image, ImageFilter

VENDORS = [
    ("Shree Ganesh Textiles", "Surat", "24"), ("Mehta Dyeing & Printing Mills", "Surat", "24"),
    ("Patel Packaging Industries", "Ahmedabad", "24"), ("Kumar Steel Traders", "Mumbai", "27"),
    ("Sunrise Chemicals Pvt Ltd", "Vadodara", "24"), ("Jain Diamond Exports", "Surat", "24"),
    ("Rao Logistics Services", "Bengaluru", "29"), ("Singh Office Supplies", "Delhi", "07"),
    ("Desai Machine Tools LLP", "Rajkot", "24"), ("Nair Electricals", "Kochi", "32"),
]
BUYERS = [("Bhavsar & Co. Chartered Accountants", "24"), ("Tapi Fabrics Pvt Ltd", "24"), ("Orbit Retail LLP", "27")]
ITEMS = [
    ("Polyester fabric 60GSM", 5407, 18), ("Reactive dye - blue", 3204, 18), ("Corrugated box 5-ply", 4819, 12),
    ("MS flat bar 40x6mm", 7214, 18), ("Caustic soda flakes", 2815, 18), ("A4 copier paper 75GSM", 4802, 12),
    ("Freight - road transport", 9965, 5), ("CNC tool holder", 8466, 18), ("LED panel light 15W", 9405, 12),
    ("Annual maintenance charges", 9987, 18),
]
FIELDS = ["vendor_name", "vendor_gstin", "buyer_name", "buyer_gstin", "invoice_number", "invoice_date",
          "subtotal", "tax_total", "total"]
_CHARS = string.digits + string.ascii_uppercase


def gstin(state: str, rng: random.Random) -> str:
    """15 characters with the real checksum, so validators accept it."""
    body = state + "".join(rng.choices(string.ascii_uppercase, k=5)) + "".join(rng.choices(string.digits, k=4))
    body += rng.choice(string.ascii_uppercase) + "1Z"
    total = 0
    for i, ch in enumerate(body):
        value = _CHARS.index(ch) * (1 if i % 2 == 0 else 2)
        total += value // 36 + value % 36
    return body + _CHARS[(36 - total % 36) % 36]


def money(v: float) -> str:
    whole, frac = f"{v:.2f}".split(".")
    head, tail = whole[:-3], whole[-3:]
    while len(head) > 2:  # Indian digit grouping: 12,34,567.00
        tail, head = head[-2:] + "," + tail, head[:-2]
    return f"{head + ',' if head else ''}{tail}.{frac}"


def make_invoice(n: int, rng: random.Random) -> dict:
    vendor, city, state = rng.choice(VENDORS)
    buyer, buyer_state = rng.choice(BUYERS)
    lines = []
    for desc, hsn, rate in rng.sample(ITEMS, rng.randint(1, 4)):
        qty, price = rng.randint(1, 200), round(rng.uniform(40, 2500), 2)
        lines.append({"description": desc, "hsn": hsn, "qty": qty, "price": price, "gst_rate": rate,
                      "amount": round(qty * price, 2)})
    intra = state == buyer_state
    subtotal = round(sum(line["amount"] for line in lines), 2)
    tax = round(sum(line["amount"] * line["gst_rate"] / 100 for line in lines), 2)
    day = date(2026, 4, 1) + timedelta(days=rng.randint(0, 200))
    return {
        "vendor_name": vendor, "vendor_city": city, "vendor_gstin": gstin(state, rng),
        "buyer_name": buyer, "buyer_gstin": gstin(buyer_state, rng),
        "invoice_number": rng.choice(["INV/26-27/{:04d}", "SG-{:05d}", "{:06d}"]).format(rng.randint(1, 9999)),
        "invoice_date": day.isoformat(), "lines": lines, "intra_state": intra,
        "subtotal": subtotal, "tax_total": tax, "total": round(subtotal + tax, 2), "trap": None,
        "id": n,
    }


def draw(inv: dict, layout: int) -> pymupdf.Document:
    doc = pymupdf.open()
    page = doc.new_page(width=595, height=842)
    y = 50
    day = date.fromisoformat(inv["invoice_date"])
    shown_date = [day.strftime("%d/%m/%Y"), day.strftime("%d-%b-%Y"), day.strftime("%d.%m.%y")][layout]

    def text(x, yy, s, size=10, bold=False):
        page.insert_text((x, yy), s, fontsize=size, fontname="hebo" if bold else "helv")

    text(40 if layout != 1 else 300, y, inv["vendor_name"], 16, True)
    text(40 if layout != 1 else 300, y + 16, f"{inv['vendor_city']}   GSTIN: {inv['vendor_gstin']}")
    text(40, y + 60, "TAX INVOICE" if layout != 2 else "Invoice", 13, True)
    label = ["Invoice No", "Inv. No.", "Bill #"][layout]
    text(40, y + 80, f"{label}: {inv['invoice_number']}")
    text(300, y + 80, f"{['Date', 'Dated', 'Invoice Date'][layout]}: {shown_date}")
    text(40, y + 105, "Bill To:", 10, True)
    text(40, y + 120, inv["buyer_name"])
    text(40, y + 134, f"GSTIN: {inv['buyer_gstin']}")
    y += 170
    headers = ("#", "Description (HSN)", "Qty", "Rate", "GST%", "Amount")
    for x, h in zip((40, 80, 300, 350, 420, 500), headers, strict=True):
        text(x, y, h, 9, True)
    y += 16
    for i, line in enumerate(inv["lines"], 1):
        row = (str(i), f"{line['description']} ({line['hsn']})", str(line["qty"]), money(line["price"]),
               f"{line['gst_rate']}%", money(line["amount"]))
        for x, cell in zip((40, 80, 300, 350, 420, 500), row, strict=True):
            text(x, y, cell, 9)
        y += 15
    y += 15
    text(350, y, f"Sub Total: {money(inv['subtotal'])}")
    if inv["intra_state"]:
        text(350, y + 14, f"CGST: {money(inv['tax_total'] / 2)}")
        text(350, y + 28, f"SGST: {money(inv['tax_total'] / 2)}")
    else:
        text(350, y + 14, f"IGST: {money(inv['tax_total'])}")
    text(350, y + 48, f"Grand Total: Rs. {money(inv['total'])}", 11, True)
    text(40, 800, "This is a computer generated invoice. Synthetic test data.", 8)
    return doc


def scan(doc: pymupdf.Document, rng: random.Random) -> pymupdf.Document:
    """Flatten to an image with skew, blur and speckle, as a phone/flatbed scan would look."""
    pix = doc[0].get_pixmap(dpi=150)
    img = Image.open(io.BytesIO(pix.tobytes("png"))).convert("L")
    img = img.rotate(rng.uniform(-1.5, 1.5), expand=True, fillcolor=255).filter(ImageFilter.GaussianBlur(0.7))
    px = img.load()
    for _ in range(img.width * img.height // 400):
        px[rng.randrange(img.width), rng.randrange(img.height)] = rng.randint(0, 120)
    buf = io.BytesIO()
    img.save(buf, "PNG")
    out = pymupdf.open()
    out.new_page(width=595, height=842).insert_image(pymupdf.Rect(0, 0, 595, 842), stream=buf.getvalue())
    return out


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--count", type=int, default=30)
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "invoices_data")
    args = parser.parse_args()
    rng = random.Random(7)
    args.out.mkdir(parents=True, exist_ok=True)

    invoices = [make_invoice(n, rng) for n in range(1, args.count + 1)]
    # Traps (kept after the clean ones so numbering stays stable): duplicate, wrong total, wrong GST.
    invoices[-1] = {**invoices[0], "id": args.count, "trap": f"duplicate_of_{invoices[0]['id']}"}
    invoices[-2]["total"] = round(invoices[-2]["total"] + rng.choice([100, 1000, 10]), 2)
    invoices[-2]["trap"] = "wrong_total"
    invoices[-3]["tax_total"] = round(invoices[-3]["tax_total"] * 1.5, 2)
    invoices[-3]["total"] = round(invoices[-3]["subtotal"] + invoices[-3]["tax_total"], 2)
    invoices[-3]["trap"] = "wrong_gst"

    truth = []
    for inv in invoices:
        doc = draw(inv, inv["id"] % 3)
        scanned = inv["id"] % 3 == 0
        if scanned:
            doc = scan(doc, rng)
        name = f"invoice_{inv['id']:02d}.pdf"
        doc.save(args.out / name)
        truth.append({"file": name, "scanned": scanned, "trap": inv["trap"],
                      **{k: inv[k] for k in FIELDS}, "lines": inv["lines"]})
    (args.out / "truth.json").write_text(json.dumps(truth, indent=2))
    print(f"{len(truth)} invoices -> {args.out} ({sum(t['scanned'] for t in truth)} scanned)")


if __name__ == "__main__":
    main()
