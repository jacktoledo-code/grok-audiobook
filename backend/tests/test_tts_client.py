import httpx
import pytest
import respx

from app import tts
from app.tts import TTSError, synthesize


@pytest.fixture(autouse=True)
def _set_api_key(monkeypatch):
    monkeypatch.setattr(tts.settings, "xai_api_key", "test-key")
    monkeypatch.setattr(tts.settings, "grok_tts_url", "https://api.x.ai/v1/tts")


@pytest.mark.asyncio
async def test_synthesize_returns_bytes_on_200():
    async with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.x.ai/v1/tts").mock(
            return_value=httpx.Response(200, content=b"MP3DATA")
        )
        async with httpx.AsyncClient() as client:
            out = await synthesize(
                "hello", voice_id="ara", language="pt-BR", client=client
            )
    assert out == b"MP3DATA"


@pytest.mark.asyncio
async def test_synthesize_retries_then_succeeds(monkeypatch):
    sleep_calls = []

    async def fake_sleep(s):
        sleep_calls.append(s)

    monkeypatch.setattr(tts.asyncio, "sleep", fake_sleep)
    async with respx.mock(assert_all_called=True) as mock:
        route = mock.post("https://api.x.ai/v1/tts")
        route.side_effect = [
            httpx.Response(429),
            httpx.Response(503),
            httpx.Response(200, content=b"OK"),
        ]
        async with httpx.AsyncClient() as client:
            out = await synthesize(
                "hi", voice_id="ara", language="pt-BR", client=client
            )
    assert out == b"OK"
    assert len(sleep_calls) == 2


@pytest.mark.asyncio
async def test_synthesize_raises_on_4xx(monkeypatch):
    async def fake_sleep(s):
        pass

    monkeypatch.setattr(tts.asyncio, "sleep", fake_sleep)
    async with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.x.ai/v1/tts").mock(
            return_value=httpx.Response(400, json={"error": "bad"})
        )
        async with httpx.AsyncClient() as client:
            with pytest.raises(TTSError) as exc:
                await synthesize(
                    "hi", voice_id="ara", language="pt-BR", client=client
                )
    assert "400" in str(exc.value)


@pytest.mark.asyncio
async def test_synthesize_raises_without_api_key(monkeypatch):
    monkeypatch.setattr(tts.settings, "xai_api_key", "")
    async with httpx.AsyncClient() as client:
        with pytest.raises(TTSError):
            await synthesize("hi", voice_id="ara", language="pt-BR", client=client)
