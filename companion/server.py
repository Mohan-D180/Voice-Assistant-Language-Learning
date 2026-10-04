"""FastAPI app: static UI, a few JSON endpoints, and the /ws conversation socket.

WebSocket protocol
------------------
client -> server
  binary                         one recorded utterance (webm/ogg/wav)
  {"type":"config","language":"bn","mode":"chat"|"tutor"}
  {"type":"text","text":"..."}   typed message instead of speech
  {"type":"interrupt"}           stop the current reply (barge-in)
  {"type":"reset"}               forget the conversation

server -> client
  {"type":"thinking"}                       a turn started
  {"type":"transcript","text":"..."}        what the user said
  {"type":"sentence","text":"...","audio":true}  followed by ONE binary mp3 frame
  {"type":"sentence","text":"...","audio":false} text only (TTS failed)
  {"type":"done"}                           the turn is finished
  {"type":"error","message":"..."}
"""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from starlette.websockets import WebSocketDisconnect

from .config import STATIC_DIR, Settings
from .languages import LANGUAGES
from .llm import LLMError
from .pipeline import VoicePipeline, build_default_pipeline
from .session import Session

log = logging.getLogger("companion.server")

MIN_AUDIO_BYTES = 1500  # anything smaller is a click or silence, not speech


def create_app(pipeline: VoicePipeline | None = None,
               settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings.from_env()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.pipeline = pipeline or await asyncio.to_thread(
            build_default_pipeline, settings
        )
        yield
        await app.state.pipeline.aclose()

    app = FastAPI(title="Voice Companion", lifespan=lifespan)
    app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

    @app.get("/")
    async def index():
        return FileResponse(STATIC_DIR / "index.html")

    @app.get("/api/languages")
    async def languages():
        return {
            "default": settings.default_language,
            "languages": [
                {"code": l.code, "name": l.name, "native": l.native, "rtl": l.rtl}
                for l in LANGUAGES.values()
            ],
        }

    @app.get("/api/health")
    async def health():
        return {"llm": await app.state.pipeline.llm.check()}

    @app.websocket("/ws")
    async def conversation(ws: WebSocket):
        await ws.accept()
        pipe: VoicePipeline = app.state.pipeline
        session = Session(settings.default_language, "chat", settings.max_history_turns)
        send_lock = asyncio.Lock()
        turn: asyncio.Task | None = None

        async def send(payload: dict, audio: bytes | None = None) -> None:
            async with send_lock:  # keep a sentence message and its audio frame together
                await ws.send_json(payload)
                if audio is not None:
                    await ws.send_bytes(audio)

        async def run_turn(audio: bytes | None = None, text: str | None = None) -> None:
            replies = None
            try:
                await send({"type": "thinking"})
                if audio is not None:
                    text = await pipe.transcribe(audio, session)
                if not text:
                    await send({"type": "done"})
                    return
                await send({"type": "transcript", "text": text})
                replies = pipe.respond(session, text)
                async for event in replies:
                    await send(
                        {"type": "sentence", "text": event.text, "audio": event.audio is not None},
                        event.audio,
                    )
                await send({"type": "done"})
            except asyncio.CancelledError:
                raise
            except LLMError as exc:
                await send({"type": "error", "message": str(exc)})
            except Exception:
                log.exception("Turn failed")
                await send({"type": "error", "message": "Something went wrong. Please try again."})
            finally:
                if replies is not None:
                    await replies.aclose()  # records the partial reply in the history

        async def cancel_turn() -> None:
            nonlocal turn
            if turn and not turn.done():
                turn.cancel()
                try:
                    await turn
                except asyncio.CancelledError:
                    pass
            turn = None

        try:
            while True:
                message = await ws.receive()
                if message["type"] == "websocket.disconnect":
                    break
                if message.get("bytes") is not None:
                    if len(message["bytes"]) < MIN_AUDIO_BYTES:
                        continue
                    await cancel_turn()
                    turn = asyncio.create_task(run_turn(audio=message["bytes"]))
                elif message.get("text") is not None:
                    data = json.loads(message["text"])
                    kind = data.get("type")
                    if kind == "config":
                        session.set_language(data.get("language", session.language.code))
                        session.set_mode(data.get("mode", session.mode))
                    elif kind == "text" and str(data.get("text", "")).strip():
                        await cancel_turn()
                        turn = asyncio.create_task(run_turn(text=data["text"].strip()))
                    elif kind == "interrupt":
                        await cancel_turn()
                    elif kind == "reset":
                        await cancel_turn()
                        session.reset()
        except WebSocketDisconnect:
            pass
        finally:
            await cancel_turn()

    return app
