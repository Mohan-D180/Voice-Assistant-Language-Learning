"""Language registry.

One entry ties together everything that changes when the user switches language:
the Whisper code (ears), the TTS voice (mouth), and the display names (UI).
To add a language, append one `Language(...)` line.
Voice names are Microsoft Edge neural voices used by `edge-tts`
(list them all with:  edge-tts --list-voices).
"""
from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Language:
    code: str      # our id, also the Whisper language code
    name: str      # English name, used inside prompts
    native: str    # name written in its own script, shown in the UI
    voice: str     # edge-tts voice
    rtl: bool = False


_ALL = [
    Language("en", "English", "English", "en-US-AriaNeural"),
    Language("bn", "Bengali", "বাংলা", "bn-BD-NabanitaNeural"),
    Language("hi", "Hindi", "हिन्दी", "hi-IN-SwaraNeural"),
    Language("ur", "Urdu", "اردو", "ur-PK-UzmaNeural", rtl=True),
    Language("ar", "Arabic", "العربية", "ar-SA-ZariyahNeural", rtl=True),
    Language("es", "Spanish", "Español", "es-ES-ElviraNeural"),
    Language("fr", "French", "Français", "fr-FR-DeniseNeural"),
    Language("de", "German", "Deutsch", "de-DE-KatjaNeural"),
    Language("it", "Italian", "Italiano", "it-IT-ElsaNeural"),
    Language("pt", "Portuguese", "Português", "pt-BR-FranciscaNeural"),
    Language("nl", "Dutch", "Nederlands", "nl-NL-ColetteNeural"),
    Language("sv", "Swedish", "Svenska", "sv-SE-SofieNeural"),
    Language("pl", "Polish", "Polski", "pl-PL-ZofiaNeural"),
    Language("ru", "Russian", "Русский", "ru-RU-SvetlanaNeural"),
    Language("tr", "Turkish", "Türkçe", "tr-TR-EmelNeural"),
    Language("ja", "Japanese", "日本語", "ja-JP-NanamiNeural"),
    Language("ko", "Korean", "한국어", "ko-KR-SunHiNeural"),
    Language("zh", "Chinese", "中文", "zh-CN-XiaoxiaoNeural"),
]

LANGUAGES: dict[str, Language] = {lang.code: lang for lang in _ALL}


def get_language(code: str) -> Language:
    """Return the language for `code`, falling back to English."""
    return LANGUAGES.get(code, LANGUAGES["en"])
