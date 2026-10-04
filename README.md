# Voice Companion

Talk out loud to a free LLM in any language you pick. Your voice is turned into text,
the LLM answers like a person, and the answer is spoken back sentence by sentence.

```
mic -> faster-whisper (ears) -> free LLM (brain) -> edge-tts (mouth) -> speaker
        language = your setting   streamed tokens      voice = your language
```

## Project layout

```
voice-companion/
├── main.py                  start the server
├── requirements.txt         5 dependencies
├── .env.example             all settings (copy to .env)
├── companion/
│   ├── config.py            settings from env / .env
│   ├── languages.py         language -> Whisper code + TTS voice + display name
│   ├── prompts.py           system prompts (chat mode, tutor mode)
│   ├── session.py           per-connection language, mode, trimmed history
│   ├── text_utils.py        sentence chunker + "clean for speech"
│   ├── stt.py               speech to text (faster-whisper)
│   ├── llm.py               LLM backends: Ollama (local) or OpenAI-compatible API
│   ├── tts.py               text to speech (edge-tts)
│   ├── pipeline.py          orchestrates STT -> LLM -> chunker -> TTS
│   └── server.py            FastAPI + WebSocket /ws
├── static/                  browser UI (index.html, style.css, app.js)
├── scripts/cli_chat.py      text-only chat to test the brain first
└── tests/                   25 offline tests with fake STT/LLM/TTS
```

## Run it

1. Install Ollama (https://ollama.com) and pull a free model:
   ```
   ollama pull qwen2.5:7b        # or qwen2.5:3b on a weak CPU
   ```
2. Install Python packages:
   ```
   python -m venv .venv
   source .venv/bin/activate      # Windows: .venv\Scripts\activate
   pip install -r requirements.txt
   ```
3. (Optional) `cp .env.example .env` and edit.
4. Start:
   ```
   python main.py
   ```
   The first start downloads the Whisper model. Open http://localhost:8000 and allow the microphone.

Test the brain alone, without voice: `python scripts/cli_chat.py --lang bn`

Run the tests: `python -m unittest discover -s tests -t .`

## Using it

- **Language**: tap the big language name. Ears, voice and replies switch together.
- **Chat / Tutor**: Tutor gently corrects one mistake per turn.
- **Microphone**: tap to talk, tap to send. **Hands-free** listens continuously and detects when you stop speaking.
- **Interrupt**: talk (or tap the mic) while it is speaking and it stops. Use headphones in hands-free mode, otherwise the speakers can feed back into the mic.
- The microphone works on `localhost`; to use it from another device you need HTTPS.

## Settings that matter

| Setting | Effect |
|---|---|
| `OLLAMA_MODEL` | Bigger = smarter, slower. Try `qwen2.5:3b` on CPU. |
| `WHISPER_MODEL` | `tiny`/`base` fast, `small` balanced, `medium`/`large-v3` more accurate (GPU advised). |
| `LLM_BACKEND=openai` | Use a hosted free-tier API instead of a local model (see `.env.example`). |
| `LLM_MAX_TOKENS` | Keep low (~200): short replies start speaking sooner. |

## How it stays fast

- The LLM streams tokens; `SentenceChunker` cuts them into sentences; the first sentence goes to TTS
  while the model is still writing the rest.
- Whisper runs with greedy decoding and its built-in VAD filter.
- Replies are prompted to be one to three short spoken sentences.
- If TTS fails, the text still appears.

## WebSocket protocol (for your own client)

See the docstring at the top of `companion/server.py`.

## Extending

- **New language**: add one line in `companion/languages.py` (`edge-tts --list-voices` shows voices).
- **Offline voice**: write a class with `async synthesize(text, voice) -> bytes` (for example Piper)
  and return it from `build_default_pipeline` in `companion/pipeline.py`.
  Note the browser expects mp3/wav/ogg audio bytes.
- **Long-term memory**: `Session.messages()` is the single place the prompt is built.
  Add a summary of older turns or a vector-search result there.
- **Auto language detection**: Whisper can return the detected language; call `session.set_language(...)`
  with it in `VoicePipeline.transcribe`.

## Troubleshooting

| Symptom | Fix |
|---|---|
| "Cannot reach Ollama" | Run `ollama serve`, and check `OLLAMA_HOST`. |
| "model not found" | `ollama pull <OLLAMA_MODEL>` |
| No sound, text appears | TTS needs internet (edge-tts); check the server log. |
| Slow first answer | Use a smaller `OLLAMA_MODEL` / `WHISPER_MODEL`, or a GPU. |
| Wrong words heard | Use a bigger `WHISPER_MODEL`, a quieter room, or a headset mic. |
| Replies in the wrong language | Small models drift in low-resource languages; try a larger one. |
