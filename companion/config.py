"""Central configuration.

Values come from environment variables, optionally loaded from a `.env` file
in the project root (a tiny parser is built in, so no extra dependency).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
STATIC_DIR = ROOT_DIR / "static"


def _load_dotenv(path: Path) -> None:
    """Load KEY=VALUE lines into os.environ without overriding existing values."""
    if not path.is_file():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))


@dataclass(frozen=True)
class Settings:
    # LLM
    llm_backend: str = "ollama"
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "qwen2.5:7b"
    openai_base_url: str = ""
    openai_api_key: str = ""
    openai_model: str = ""
    llm_temperature: float = 0.7
    llm_max_tokens: int = 200

    # Speech to text
    whisper_model: str = "small"
    whisper_device: str = "auto"
    whisper_compute: str = "int8"

    # Text to speech
    tts_rate: str = "+0%"

    # App
    default_language: str = "en"
    max_history_turns: int = 12
    host: str = "127.0.0.1"
    port: int = 8000

    @classmethod
    def from_env(cls) -> "Settings":
        _load_dotenv(ROOT_DIR / ".env")
        env = os.environ.get
        return cls(
            llm_backend=env("LLM_BACKEND", cls.llm_backend).lower(),
            ollama_host=env("OLLAMA_HOST", cls.ollama_host),
            ollama_model=env("OLLAMA_MODEL", cls.ollama_model),
            openai_base_url=env("OPENAI_BASE_URL", cls.openai_base_url),
            openai_api_key=env("OPENAI_API_KEY", cls.openai_api_key),
            openai_model=env("OPENAI_MODEL", cls.openai_model),
            llm_temperature=float(env("LLM_TEMPERATURE", cls.llm_temperature)),
            llm_max_tokens=int(env("LLM_MAX_TOKENS", cls.llm_max_tokens)),
            whisper_model=env("WHISPER_MODEL", cls.whisper_model),
            whisper_device=env("WHISPER_DEVICE", cls.whisper_device),
            whisper_compute=env("WHISPER_COMPUTE", cls.whisper_compute),
            tts_rate=env("TTS_RATE", cls.tts_rate),
            default_language=env("DEFAULT_LANGUAGE", cls.default_language),
            max_history_turns=int(env("MAX_HISTORY_TURNS", cls.max_history_turns)),
            host=env("HOST", cls.host),
            port=int(env("PORT", cls.port)),
        )
