"""The conversation pipeline:  audio -> text -> LLM tokens -> sentences -> audio.

The pipeline only orchestrates; STT, LLM and TTS are injected, so each one can
be swapped (or faked in tests) without touching this file.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from typing import AsyncIterator

from .config import Settings
from .llm import LLMClient, build_llm
from .session import Session
from .stt import SpeechToText
from .text_utils import SentenceChunker, clean_for_speech
from .tts import TextToSpeech

log = logging.getLogger("companion.pipeline")


@dataclass
class SentenceEvent:
    text: str
    audio: bytes | None  # None when speech synthesis failed: show the text anyway


class VoicePipeline:
    def __init__(self, stt: SpeechToText, llm: LLMClient, tts: TextToSpeech):
        self.stt = stt
        self.llm = llm
        self.tts = tts

    async def transcribe(self, audio: bytes, session: Session) -> str:
        """Speech -> text in the session's language (runs in a worker thread)."""
        return await asyncio.to_thread(self.stt.transcribe, audio, session.language.code)

    async def respond(self, session: Session, user_text: str) -> AsyncIterator[SentenceEvent]:
        """Stream the reply sentence by sentence, each already turned into audio.

        The first sentence is spoken while the LLM is still writing the rest.
        If the consumer stops early (user interrupts), only what was actually
        produced is stored in the history.
        """
        session.add_user(user_text)
        chunker = SentenceChunker()
        spoken: list[str] = []
        try:
            async for token in self.llm.stream_chat(session.messages()):
                for sentence in chunker.feed(token):
                    event = await self._speak(session, sentence)
                    if event:
                        spoken.append(event.text)
                        yield event
            tail = chunker.flush()
            if tail:
                event = await self._speak(session, tail)
                if event:
                    spoken.append(event.text)
                    yield event
        finally:
            session.add_assistant(" ".join(spoken))

    async def _speak(self, session: Session, sentence: str) -> SentenceEvent | None:
        text = clean_for_speech(sentence)
        if not text:
            return None
        try:
            audio = await self.tts.synthesize(text, session.language.voice)
        except Exception:  # network hiccup, unsupported voice...
            log.exception("TTS failed; falling back to text only")
            audio = None
        return SentenceEvent(text=text, audio=audio)

    async def aclose(self) -> None:
        await self.llm.aclose()


def build_default_pipeline(settings: Settings) -> VoicePipeline:
    """Wire the real components (loads the Whisper model, so this takes a moment)."""
    from .stt import WhisperSTT
    from .tts import EdgeTTS

    stt = WhisperSTT(settings.whisper_model, settings.whisper_device, settings.whisper_compute)
    return VoicePipeline(stt=stt, llm=build_llm(settings), tts=EdgeTTS(settings.tts_rate))
