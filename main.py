"""Start the voice companion:  python main.py   then open http://localhost:8000"""
import logging

import uvicorn

from companion.config import Settings
from companion.server import create_app


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    settings = Settings.from_env()
    uvicorn.run(create_app(settings=settings), host=settings.host, port=settings.port)


if __name__ == "__main__":
    main()
