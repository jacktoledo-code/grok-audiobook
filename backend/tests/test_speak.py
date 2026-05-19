import httpx
import pytest
import respx
from fastapi.testclient import TestClient

from app import tts as tts_module
from app.main import app


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setattr(tts_module.settings, "xai_api_key", "test-key")
    monkeypatch.setattr(
        tts_module.settings, "grok_tts_url", "https://api.x.ai/v1/tts"
    )
    return TestClient(app)


def test_speak_happy_path(client, monkeypatch):
    async def fake_sleep(_):
        pass

    monkeypatch.setattr(tts_module.asyncio, "sleep", fake_sleep)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.x.ai/v1/tts").mock(
            return_value=httpx.Response(200, content=b"FAKEMP3")
        )
        res = client.post(
            "/api/speak",
            data={"text": "Hello world.", "voice_id": "ara", "language": "en-US"},
        )
    assert res.status_code == 200
    assert res.headers["content-type"] == "audio/mpeg"
    assert res.content == b"FAKEMP3"


def test_speak_empty_text_is_400(client):
    res = client.post("/api/speak", data={"text": "   "})
    assert res.status_code == 400
    assert "empty" in res.json()["detail"].lower()


def test_speak_over_limit_is_400(client):
    long = "a" * 15_001
    res = client.post("/api/speak", data={"text": long})
    assert res.status_code == 400
    assert "15000" in res.json()["detail"] or "Max" in res.json()["detail"]


def test_speak_invalid_voice_is_400(client):
    res = client.post(
        "/api/speak", data={"text": "hi", "voice_id": "nobody"}
    )
    assert res.status_code == 400
    assert "voice_id" in res.json()["detail"].lower()


def test_speak_missing_api_key(monkeypatch):
    monkeypatch.setattr(tts_module.settings, "xai_api_key", "")
    c = TestClient(app)
    res = c.post("/api/speak", data={"text": "hi"})
    assert res.status_code == 503


def test_speak_upstream_failure_is_502(client, monkeypatch):
    async def fake_sleep(_):
        pass

    monkeypatch.setattr(tts_module.asyncio, "sleep", fake_sleep)
    with respx.mock(assert_all_called=True) as mock:
        mock.post("https://api.x.ai/v1/tts").mock(
            return_value=httpx.Response(500, text="boom")
        )
        res = client.post("/api/speak", data={"text": "hi"})
    assert res.status_code == 502
