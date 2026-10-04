"""In-memory stand-ins for Whisper, the LLM and TTS, so tests run instantly and offline."""
from companion.llm import LLMClient
from companion.pipeline import VoicePipeline


class FakeSTT:
    def __init__(self, text="hello there"):
        self.text = text
        self.calls = []

    def transcribe(self, audio, language):
        self.calls.append(language)
        return self.text


class FakeLLM(LLMClient):
    def __init__(self, tokens=("Hello there. ", "How are you?")):
        self.tokens = tokens
        self.seen_messages = []

    async def stream_chat(self, messages):
        self.seen_messages.append(messages)
        for token in self.tokens:
            yield token

    async def check(self):
        return True

    async def aclose(self):
        pass


class FakeTTS:
    def __init__(self, fail=False):
        self.fail = fail
        self.calls = []

    async def synthesize(self, text, voice):
        self.calls.append((text, voice))
        if self.fail:
            raise RuntimeError("tts down")
        return b"MP3:" + text.encode()


def make_pipeline(stt=None, llm=None, tts=None):
    return VoicePipeline(stt or FakeSTT(), llm or FakeLLM(), tts or FakeTTS())
