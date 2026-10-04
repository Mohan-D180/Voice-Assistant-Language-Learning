"""Text-only chat in the terminal: test the LLM brain and prompts before adding voice.

    python scripts/cli_chat.py --lang bn --mode chat
Commands:  /lang <code>   /mode chat|tutor   /reset   /quit
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from companion.config import Settings  # noqa: E402
from companion.languages import LANGUAGES  # noqa: E402
from companion.llm import LLMError, build_llm  # noqa: E402
from companion.session import Session  # noqa: E402


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--lang", default="en", choices=sorted(LANGUAGES))
    parser.add_argument("--mode", default="chat", choices=["chat", "tutor"])
    args = parser.parse_args()

    settings = Settings.from_env()
    llm = build_llm(settings)
    session = Session(args.lang, args.mode, settings.max_history_turns)
    print(f"Talking in {session.language.name}. Type /quit to leave.")

    try:
        while True:
            try:
                line = input("you> ").strip()
            except (EOFError, KeyboardInterrupt):
                break
            if not line:
                continue
            if line == "/quit":
                break
            if line == "/reset":
                session.reset()
                continue
            if line.startswith("/lang "):
                session.set_language(line.split(maxsplit=1)[1])
                print(f"(language: {session.language.name})")
                continue
            if line.startswith("/mode "):
                session.set_mode(line.split(maxsplit=1)[1])
                print(f"(mode: {session.mode})")
                continue

            session.add_user(line)
            reply: list[str] = []
            print("ai> ", end="", flush=True)
            try:
                async for token in llm.stream_chat(session.messages()):
                    print(token, end="", flush=True)
                    reply.append(token)
            except LLMError as exc:
                print(f"\n[error] {exc}")
            print()
            session.add_assistant("".join(reply))
    finally:
        await llm.aclose()


if __name__ == "__main__":
    asyncio.run(main())
