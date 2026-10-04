import unittest

from fastapi.testclient import TestClient

from companion.config import Settings
from companion.server import create_app
from companion.session import Session
from tests.fakes import FakeLLM, FakeSTT, FakeTTS, make_pipeline


class PipelineTests(unittest.IsolatedAsyncioTestCase):
    async def test_streams_sentences_with_audio_and_stores_history(self):
        tts = FakeTTS()
        pipe = make_pipeline(tts=tts)
        session = Session("bn")
        events = [e async for e in pipe.respond(session, "hi")]
        self.assertEqual([e.text for e in events], ["Hello there.", "How are you?"])
        self.assertEqual(events[0].audio, b"MP3:Hello there.")
        self.assertEqual(tts.calls[0][1], "bn-BD-NabanitaNeural")  # voice follows language
        self.assertEqual(session.messages()[-1]["content"], "Hello there. How are you?")

    async def test_tts_failure_falls_back_to_text(self):
        pipe = make_pipeline(tts=FakeTTS(fail=True))
        events = [e async for e in pipe.respond(Session("en"), "hi")]
        self.assertEqual(len(events), 2)
        self.assertTrue(all(e.audio is None for e in events))

    async def test_early_stop_keeps_only_spoken_part(self):
        pipe = make_pipeline()
        session = Session("en")
        gen = pipe.respond(session, "hi")
        first = await gen.__anext__()
        await gen.aclose()
        self.assertEqual(first.text, "Hello there.")
        self.assertEqual(session.messages()[-1]["content"], "Hello there.")


class ServerTests(unittest.TestCase):
    def setUp(self):
        self.stt = FakeSTT("good morning")
        self.llm = FakeLLM()
        self.app = create_app(make_pipeline(stt=self.stt, llm=self.llm), Settings())

    def test_languages_endpoint(self):
        with TestClient(self.app) as client:
            data = client.get("/api/languages").json()
            codes = [l["code"] for l in data["languages"]]
            self.assertIn("bn", codes)
            self.assertTrue(client.get("/api/health").json()["llm"])
            self.assertEqual(client.get("/").status_code, 200)

    def test_text_turn(self):
        with TestClient(self.app) as client, client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "config", "language": "de", "mode": "chat"})
            ws.send_json({"type": "text", "text": "Hallo"})
            self.assertEqual(ws.receive_json()["type"], "thinking")
            self.assertEqual(ws.receive_json(), {"type": "transcript", "text": "Hallo"})
            first = ws.receive_json()
            self.assertEqual(first, {"type": "sentence", "text": "Hello there.", "audio": True})
            self.assertEqual(ws.receive_bytes(), b"MP3:Hello there.")
            second = ws.receive_json()
            self.assertEqual(second["text"], "How are you?")
            ws.receive_bytes()
            self.assertEqual(ws.receive_json(), {"type": "done"})
            self.assertIn("German", self.llm.seen_messages[0][0]["content"])

    def test_audio_turn_uses_session_language_for_stt(self):
        with TestClient(self.app) as client, client.websocket_connect("/ws") as ws:
            ws.send_json({"type": "config", "language": "fr"})
            ws.send_bytes(b"\x00" * 4000)
            self.assertEqual(ws.receive_json()["type"], "thinking")
            self.assertEqual(ws.receive_json(), {"type": "transcript", "text": "good morning"})
            self.assertEqual(self.stt.calls, ["fr"])

    def test_tiny_audio_is_ignored(self):
        with TestClient(self.app) as client, client.websocket_connect("/ws") as ws:
            ws.send_bytes(b"\x00" * 10)
            ws.send_json({"type": "text", "text": "still works"})
            self.assertEqual(ws.receive_json()["type"], "thinking")


if __name__ == "__main__":
    unittest.main()
