from app.chunk import estimate_cost_usd
from app.models import Book, Chapter


def test_total_chars_sums_chapters():
    book = Book(
        title="t",
        author="a",
        chapters=[Chapter(title="c1", text="abc"), Chapter(title="c2", text="defgh")],
    )
    assert book.total_chars == 8


def test_estimate_matches_prd_example():
    # PRD: 60k-word book ≈ 330k–360k chars → ~$1.40–$1.60
    low = estimate_cost_usd(330_000)
    high = estimate_cost_usd(360_000)
    assert 1.38 <= low <= 1.41
    assert 1.51 <= high <= 1.52
