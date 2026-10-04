"""LLM backends. Both stream tokens so speech can start before the reply is done.

* OllamaClient  - free open-weight models running locally (Qwen, Llama, Gemma...).
* OpenAICompatClient - any hosted OpenAI-compatible API (Groq, OpenRouter, Gemini...).
"""
from __future__ import annotations

import json
from abc import ABC, abstractmethod
from typing import AsyncIterator

import httpx

from .config import Settings


class LLMError(RuntimeError):
    """Raised with a human-readable message when the LLM cannot answer."""


class LLMClient(ABC):
    @abstractmethod
    def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        """Yield the reply token by token."""

    @abstractmethod
    async def check(self) -> bool:
        """Return True if the backend is reachable."""

    @abstractmethod
    async def aclose(self) -> None: ...


class OllamaClient(LLMClient):
    def __init__(self, host: str, model: str, temperature: float, max_tokens: int):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self._http = httpx.AsyncClient(
            base_url=host.rstrip("/"), timeout=httpx.Timeout(120.0, connect=5.0)
        )

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "options": {"temperature": self.temperature, "num_predict": self.max_tokens},
        }
        try:
            async with self._http.stream("POST", "/api/chat", json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="ignore")[:200]
                    raise LLMError(
                        f"Ollama answered {resp.status_code}: {body} "
                        f"(is the model pulled?  ollama pull {self.model})"
                    )
                async for line in resp.aiter_lines():
                    if not line:
                        continue
                    data = json.loads(line)
                    piece = data.get("message", {}).get("content", "")
                    if piece:
                        yield piece
                    if data.get("done"):
                        break
        except httpx.ConnectError as exc:
            raise LLMError("Cannot reach Ollama. Start it with:  ollama serve") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("The language model took too long to respond.") from exc

    async def check(self) -> bool:
        try:
            return (await self._http.get("/api/tags")).status_code == 200
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._http.aclose()


class OpenAICompatClient(LLMClient):
    def __init__(self, base_url: str, api_key: str, model: str,
                 temperature: float, max_tokens: int):
        if not base_url or not model:
            raise LLMError("Set OPENAI_BASE_URL and OPENAI_MODEL for the 'openai' backend.")
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), headers=headers,
            timeout=httpx.Timeout(120.0, connect=5.0),
        )

    async def stream_chat(self, messages: list[dict]) -> AsyncIterator[str]:
        payload = {
            "model": self.model,
            "messages": messages,
            "stream": True,
            "temperature": self.temperature,
            "max_tokens": self.max_tokens,
        }
        try:
            async with self._http.stream("POST", "/chat/completions", json=payload) as resp:
                if resp.status_code != 200:
                    body = (await resp.aread()).decode(errors="ignore")[:200]
                    raise LLMError(f"LLM API answered {resp.status_code}: {body}")
                async for line in resp.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if data == "[DONE]":
                        break
                    choices = json.loads(data).get("choices") or []
                    if choices:
                        piece = choices[0].get("delta", {}).get("content") or ""
                        if piece:
                            yield piece
        except httpx.ConnectError as exc:
            raise LLMError("Cannot reach the LLM API. Check OPENAI_BASE_URL.") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("The language model took too long to respond.") from exc

    async def check(self) -> bool:
        try:
            return (await self._http.get("/models")).status_code < 400
        except httpx.HTTPError:
            return False

    async def aclose(self) -> None:
        await self._http.aclose()


def build_llm(settings: Settings) -> LLMClient:
    if settings.llm_backend == "openai":
        return OpenAICompatClient(
            settings.openai_base_url, settings.openai_api_key, settings.openai_model,
            settings.llm_temperature, settings.llm_max_tokens,
        )
    return OllamaClient(
        settings.ollama_host, settings.ollama_model,
        settings.llm_temperature, settings.llm_max_tokens,
    )
