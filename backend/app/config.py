from __future__ import annotations

from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

COST_PER_MILLION_CHARS = 4.20
MAX_TTS_CHARS = 15_000
DEFAULT_VOICE = "ara"
DEFAULT_LANGUAGE = "pt-BR"
ALLOWED_VOICES = frozenset({"ara", "eve", "rex", "sal", "leo"})
ALLOWED_MODES = frozenset({"chapter", "single"})


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    xai_api_key: str = Field(default="", alias="XAI_API_KEY")
    grok_tts_url: str = Field(
        default="https://api.x.ai/v1/tts", alias="GROK_TTS_URL"
    )
    allowed_origins: str = Field(default="", alias="ALLOWED_ORIGINS")
    max_upload_mb: int = Field(default=10, alias="MAX_UPLOAD_MB")
    outputs_dir: Path = Field(default=Path("outputs"), alias="OUTPUTS_DIR")

    @property
    def max_upload_bytes(self) -> int:
        return self.max_upload_mb * 1024 * 1024

    @property
    def cors_origins(self) -> list[str]:
        return [o.strip() for o in self.allowed_origins.split(",") if o.strip()]


settings = Settings()
