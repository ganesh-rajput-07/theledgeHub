from app.ingestion.cleaner import clean_text


def test_joins_wrapped_lines_and_keeps_paragraphs():
    raw = "We provide software development\nand consulting.\n\n\n\nChapter 2"
    assert clean_text(raw) == "We provide software development and consulting.\n\nChapter 2"


def test_rejoins_hyphenated_words_and_collapses_spaces():
    assert clean_text("devel-\nopment   of\t\tproducts") == "development of products"


def test_strips_null_bytes_and_normalizes_unicode():
    assert clean_text("ﬁnance\x00 report") == "finance report"
