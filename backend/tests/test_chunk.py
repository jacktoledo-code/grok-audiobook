from app.chunk import count_chars, estimate_cost_usd, split_text


def test_empty_text_returns_empty():
    assert split_text("") == []


def test_text_under_limit_is_single_chunk():
    text = "Hello world. " * 10
    assert split_text(text, max_chars=200) == [text.strip()]


def test_paragraph_split_respects_limit():
    para_a = "Lorem ipsum " * 30  # ~360 chars
    para_b = "Dolor sit amet. " * 30
    text = f"{para_a.strip()}\n\n{para_b.strip()}"
    chunks = split_text(text, max_chars=400)
    assert all(len(c) <= 400 for c in chunks)
    assert len(chunks) >= 2


def test_long_paragraph_falls_back_to_sentences():
    sentence = "This is a sentence of moderate length. "
    text = sentence * 20  # one giant paragraph
    chunks = split_text(text, max_chars=120)
    assert all(len(c) <= 120 for c in chunks)
    # Every chunk should consist of whole sentences (end with '.').
    for c in chunks:
        assert c.strip().endswith(".")


def test_hard_slice_on_massive_word():
    text = "a" * 500
    chunks = split_text(text, max_chars=100)
    assert all(len(c) <= 100 for c in chunks)
    assert "".join(chunks) == text


def test_speech_tag_span_is_kept_atomic():
    inner = "x" * 50
    text = f"Prefix. <whisper>{inner}</whisper> Suffix. " + "y " * 200
    chunks = split_text(text, max_chars=120)
    # The whisper span must appear intact inside exactly one chunk.
    hits = [c for c in chunks if "<whisper>" in c]
    assert len(hits) == 1
    assert f"<whisper>{inner}</whisper>" in hits[0]


def test_count_chars_is_raw_length():
    assert count_chars("olá mundo") == len("olá mundo")


def test_estimate_cost():
    # 1,000,000 chars at $4.20/M
    assert estimate_cost_usd(1_000_000, 4.20) == 4.20
    # 333,000 chars ≈ $1.3986
    assert abs(estimate_cost_usd(333_000, 4.20) - 1.3986) < 1e-4
