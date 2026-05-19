from app.parsers import parse_book
from app.parsers.md import markdown_to_plain, parse_md


def test_strips_common_markdown():
    md = (
        "This is **bold** and *italic* and `inline code`.\n"
        "A [link](http://example.com) keeps only the text.\n"
        "An ![image](http://x/y.png) is removed.\n"
        "~~strike~~ is gone.\n"
    )
    plain = markdown_to_plain(md)
    assert "**" not in plain and "bold" in plain
    assert "italic" in plain and "*italic*" not in plain
    assert "inline code" in plain and "`" not in plain
    assert "link" in plain and "http://example.com" not in plain
    assert "image" not in plain and "y.png" not in plain
    assert "strike" in plain and "~~" not in plain


def test_deep_headings_become_plain_text_level1_preserved():
    md = "# Chapter 1\n\n## Subheading\n\nBody.\n"
    plain = markdown_to_plain(md)
    # Level-1 heading kept for chapter detection.
    assert "# Chapter 1" in plain
    # Level-2 heading stripped to plain text.
    assert "Subheading" in plain
    assert "## Subheading" not in plain


def test_lists_blockquotes_and_hr_cleaned():
    md = "---\n\n- one\n- two\n\n1. first\n\n> quoted line\n"
    plain = markdown_to_plain(md)
    assert "- one" not in plain and "one" in plain
    assert "1. first" not in plain and "first" in plain
    assert "> " not in plain and "quoted line" in plain
    assert "---" not in plain


def test_code_fence_dropped_entirely():
    md = "Before.\n\n```python\nprint('hi')\n```\n\nAfter.\n"
    plain = markdown_to_plain(md)
    assert "Before." in plain and "After." in plain
    assert "print" not in plain
    assert "```" not in plain


def test_parse_md_detects_chapters_and_headers():
    md = (
        "Title: Meu Livro\n"
        "Author: Jane\n"
        "\n"
        "# Capítulo 1\n"
        "Era uma vez um gato **preguiçoso**.\n"
        "\n"
        "# Capítulo 2\n"
        "Ele bebeu [café](http://cafe.example).\n"
    )
    book = parse_md(md, filename="livro.md")
    assert book.title == "Meu Livro"
    assert book.author == "Jane"
    assert [c.title for c in book.chapters] == ["Capítulo 1", "Capítulo 2"]
    assert "preguiçoso" in book.chapters[0].text
    assert "**" not in book.chapters[0].text
    assert "café" in book.chapters[1].text
    assert "http" not in book.chapters[1].text


def test_dispatch_routes_md_extension():
    data = b"# Only Chapter\nHello **world**."
    book = parse_book(data, filename="x.md")
    assert book.chapters[0].title == "Only Chapter"
    assert "world" in book.chapters[0].text
    assert "**" not in book.chapters[0].text


def test_dispatch_routes_markdown_extension():
    data = b"# Chap\nHi."
    book = parse_book(data, filename="x.markdown")
    assert book.chapters[0].title == "Chap"
