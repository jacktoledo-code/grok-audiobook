from app.parsers import UnsupportedFormatError, parse_book
from app.parsers.txt import parse_txt


def test_txt_with_header_and_chapters():
    text = (
        "Title: Meu Livro\n"
        "Author: Fulana de Tal\n"
        "\n"
        "# Capítulo 1\n"
        "Era uma vez um gato preguiçoso.\n"
        "\n"
        "# Capítulo 2\n"
        "Ele acordou e bebeu café.\n"
    )
    book = parse_txt(text, filename="meu-livro.txt")
    assert book.title == "Meu Livro"
    assert book.author == "Fulana de Tal"
    assert [c.title for c in book.chapters] == ["Capítulo 1", "Capítulo 2"]
    assert "gato" in book.chapters[0].text
    assert "café" in book.chapters[1].text


def test_txt_without_markers_uses_filename():
    book = parse_txt("Just some body text.", filename="plain.txt")
    assert book.title == "plain"
    assert book.author == ""
    assert len(book.chapters) == 1
    assert book.chapters[0].title == "plain"


def test_txt_preamble_becomes_intro_chapter():
    text = "Preamble paragraph.\n\n# Capítulo 1\nBody.\n"
    book = parse_txt(text, filename="b.txt")
    assert [c.title for c in book.chapters] == ["Introdução", "Capítulo 1"]


def test_unsupported_extension_raises():
    try:
        parse_book(b"data", filename="thing.pdf")
    except UnsupportedFormatError as exc:
        assert "pdf" in str(exc).lower()
    else:
        raise AssertionError("expected UnsupportedFormatError")


def test_dispatch_to_txt_parser():
    data = b"Title: X\nAuthor: Y\n\n# One\nHello world."
    book = parse_book(data, filename="x.txt")
    assert book.title == "X"
    assert book.author == "Y"
    assert book.chapters[0].title == "One"
