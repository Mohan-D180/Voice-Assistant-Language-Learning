"""Text to speech.

EdgeTTS gives natural neural voices in all registered languages for free
(it needs an internet connection). To go fully offline, add another class with
the same `synthesize` method (for example Piper) and return it from the factory
in `pipeline.build_default_pipeline`.
"""
from __future__ import annotations

from typing import Protocol


class TextToSpeech(Protocol):
    async def synthesize(self, text: str, voice: str) -> bytes:
        """Return audio bytes (mp3) for `text` spoken with `voice`."""
        ...


class EdgeTTS:
    def __init__(self, rate: str = "+0%"):
        self.rate = rate

    async def synthesize(self, text: str, voice: str) -> bytes:
        import edge_tts

        audio = bytearray()
        async for chunk in edge_tts.Communicate(text, voice, rate=self.rate).stream():
            if chunk["type"] == "audio":
                audio += chunk["data"]
        if not audio:
            raise RuntimeError(f"No audio returned for voice {voice}")
        return bytes(audio)
