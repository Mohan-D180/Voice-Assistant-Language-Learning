"""Text helpers that sit between the LLM and the speech synthesizer."""
from __future__ import annotations

import re

# A sentence boundary is either:
#  - CJK punctuation (no space follows in those scripts), or
#  - . ! ? ... | (Hindi/Bengali danda) or Arabic question mark followed by whitespace.
# Requiring whitespace after Latin-style punctuation keeps "3.14" and "e.g." intact.
_BOUNDARY = re.compile(
    r"[。！？]+[\"'”’」』)\]]*"
    r"|[.!?…।؟]+[\"'”’)\]]*(?=\s)"
)


class SentenceChunker:
    """Turns a stream of LLM tokens into speakable sentences.

    Feed tokens as they arrive; each call returns any sentences that are now
    complete. Call `flush()` at the end for the remaining tail.
    """

    def __init__(self, min_chars: int = 10, max_chars: int = 220):
        self.min_chars = min_chars
        self.max_chars = max_chars
        self.buffer = ""

    def feed(self, token: str) -> list[str]:
        self.buffer += token
        sentences: list[str] = []
        while (cut := self._find_cut()) is not None:
            sentence, self.buffer = self.buffer[:cut].strip(), self.buffer[cut:].lstrip()
            if sentence:
                sentences.append(sentence)
        return sentences

    def flush(self) -> str | None:
        tail, self.buffer = self.buffer.strip(), ""
        return tail or None

    def _find_cut(self) -> int | None:
        for match in _BOUNDARY.finditer(self.buffer):
            if len(self.buffer[: match.end()].strip()) >= self.min_chars:
                return match.end()
        # Safety valve: a very long run with no punctuation is cut at a soft break.
        if len(self.buffer) > self.max_chars:
            soft = max(
                self.buffer.rfind(", ", 0, self.max_chars),
                self.buffer.rfind(" ", 0, self.max_chars),
            )
            return soft + 1 if soft > 0 else self.max_chars
        return None


_CODE = re.compile(r"`+")
_LINK = re.compile(r"\[([^\]]+)\]\([^)]+\)")
_URL = re.compile(r"https?://\S+")
_LIST_MARKER = re.compile(r"(?m)^\s*(?:[-*•>]+|\d+[.)]|#{1,6})\s+")
_EMPHASIS = re.compile(r"(?<!\w)[_*~]+|[_*~]+(?!\w)")
_EMOJI = re.compile(
    "[\U0001F000-\U0001FAFF\U00002600-\U000027BF\U00002B00-\U00002BFF\uFE0F\u200d]"
)
_SPACES = re.compile(r"\s+")


def clean_for_speech(text: str) -> str:
    """Strip markdown, links and emojis so TTS reads only natural words.

    Returns "" when nothing speakable is left (e.g. only punctuation).
    """
    text = _LINK.sub(r"\1", text)
    text = _URL.sub("", text)
    text = _CODE.sub("", text)
    text = _LIST_MARKER.sub("", text)
    text = _EMPHASIS.sub("", text)
    text = _EMOJI.sub("", text)
    text = _SPACES.sub(" ", text).strip()
    return text if any(ch.isalnum() for ch in text) else ""
