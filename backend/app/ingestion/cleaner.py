import re
import unicodedata


def clean_text(text: str) -> str:
    """Normalize extracted text while keeping paragraph breaks (blank lines)."""
    text = unicodedata.normalize("NFKC", text.replace("\x00", ""))
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"(\w)-\n(\w)", r"\1\2", text)  # re-join words hyphenated at line ends
    text = re.sub(r"[ \t\f\v]+", " ", text)
    text = re.sub(r" *\n *", "\n", text)
    text = re.sub(r"(?<!\n)\n(?!\n)", " ", text)  # single newline = visual line wrap
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()
