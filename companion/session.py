"""Per-connection conversation state: language, mode and recent history."""
from __future__ import annotations

from .languages import Language, get_language
from .prompts import MODES, build_system_prompt


class Session:
    def __init__(self, language: str = "en", mode: str = "chat", max_turns: int = 12):
        self.language: Language = get_language(language)
        self.mode = mode if mode in MODES else "chat"
        self.max_turns = max_turns
        self._history: list[dict] = []

    # --- settings -------------------------------------------------------
    def set_language(self, code: str) -> None:
        self.language = get_language(code)

    def set_mode(self, mode: str) -> None:
        if mode in MODES:
            self.mode = mode

    # --- history --------------------------------------------------------
    def add_user(self, text: str) -> None:
        self._history.append({"role": "user", "content": text})

    def add_assistant(self, text: str) -> None:
        """Store what the AI actually said (empty replies are ignored)."""
        text = text.strip()
        if text:
            self._history.append({"role": "assistant", "content": text})

    def reset(self) -> None:
        self._history.clear()

    def messages(self) -> list[dict]:
        """System prompt + the most recent turns, ready to send to the LLM."""
        recent = self._history[-2 * self.max_turns:]
        while recent and recent[0]["role"] != "user":
            recent = recent[1:]
        system = {
            "role": "system",
            "content": build_system_prompt(self.language.name, self.mode),
        }
        return [system, *recent]
