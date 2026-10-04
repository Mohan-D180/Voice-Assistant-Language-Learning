"""Speech to text with faster-whisper (free, offline, ~99 languages)."""
from __future__ import annotations

import io
import threading
from typing import Protocol


class SpeechToText(Protocol):
    def transcribe(self, audio: bytes, language: str | None) -> str: ...


class WhisperSTT:
    """Loads the model once, then transcribes browser recordings (webm/ogg/wav...).

    faster-whisper decodes the container itself, so ffmpeg is not required.
    `transcribe` is blocking - the pipeline runs it in a worker thread.
    """

    def __init__(self, model_size: str = "small", device: str = "auto",
                 compute_type: str = "int8"):
        from faster_whisper import WhisperModel  # imported here: heavy, optional in tests

        self._model = WhisperModel(model_size, device=device, compute_type=compute_type)
        self._lock = threading.Lock()  # one transcription at a time

    def transcribe(self, audio: bytes, language: str | None) -> str:
        with self._lock:
            segments, _info = self._model.transcribe(
                io.BytesIO(audio),
                language=language,
                beam_size=1,                      # greedy decoding: fastest
                vad_filter=True,                  # drop silence / noise, fewer hallucinations
                condition_on_previous_text=False,
            )
            return " ".join(seg.text.strip() for seg in segments).strip()
