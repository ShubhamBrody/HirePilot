"""
LLM Service — Ollama integration for AI-powered features.

Provides a reusable interface to call local Ollama LLM models
for recruiter discovery, message generation, resume analysis, etc.
"""

import json
from typing import Any

import httpx

from app.core.config import get_settings
from app.core.logging import get_logger

settings = get_settings()
logger = get_logger(__name__)


class LLMService:
    """Calls a local Ollama instance for LLM inference."""

    def __init__(
        self,
        base_url: str | None = None,
        model: str | None = None,
        timeout: float = 120.0,
    ):
        self.base_url = (base_url or settings.ollama_base_url).rstrip("/")
        self.model = model or settings.ollama_model
        self.timeout = timeout

    # ── Core helpers ────────────────────────────────────────────

    async def _ensure_model(self) -> None:
        """Pull the model if it's not already available."""
        async with httpx.AsyncClient(timeout=10) as client:
            try:
                resp = await client.get(f"{self.base_url}/api/tags")
                resp.raise_for_status()
                models = [m["name"] for m in resp.json().get("models", [])]
                # Check both with and without :latest tag
                if self.model in models or f"{self.model}:latest" in models:
                    return
            except httpx.HTTPError:
                logger.warning("Could not check Ollama models, will attempt pull")

        # Model not found — pull it (this can take a while on first run)
        logger.info("Pulling Ollama model", model=self.model)
        async with httpx.AsyncClient(timeout=600) as client:
            resp = await client.post(
                f"{self.base_url}/api/pull",
                json={"name": self.model, "stream": False},
                timeout=600,
            )
            resp.raise_for_status()
            logger.info("Ollama model pulled successfully", model=self.model)

    async def generate(self, prompt: str, *, system: str | None = None) -> str:
        """
        Generate a text completion from Ollama.
        Returns the raw response text.
        """
        await self._ensure_model()

        payload: dict[str, Any] = {
            "model": self.model,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": 0.7,
                "num_predict": 4096,
            },
        }
        if system:
            payload["system"] = system

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/generate",
                json=payload,
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["response"]

    async def generate_json(
        self, prompt: str, *, system: str | None = None
    ) -> Any:
        """
        Generate a response and parse it as JSON.
        Attempts to extract JSON from markdown code fences if present.
        """
        raw = await self.generate(prompt, system=system)
        return self._parse_json(raw)

    async def chat(
        self,
        messages: list[dict[str, str]],
    ) -> str:
        """
        Multi-turn chat with Ollama.
        Each message: {"role": "system"|"user"|"assistant", "content": "..."}
        """
        await self._ensure_model()

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            resp = await client.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": messages,
                    "stream": False,
                    "options": {"temperature": 0.7},
                },
                timeout=self.timeout,
            )
            resp.raise_for_status()
            return resp.json()["message"]["content"]

    # ── JSON extraction ─────────────────────────────────────────

    @staticmethod
    def _parse_json(text: str) -> Any:
        """Parse JSON, handling markdown code fences."""
        text = text.strip()
        # Strip ```json ... ``` fences
        if text.startswith("```"):
            lines = text.split("\n")
            # Remove first line (```json) and last line (```)
            lines = [l for l in lines if not l.strip().startswith("```")]
            text = "\n".join(lines).strip()
        return json.loads(text)

    # ── Health check ────────────────────────────────────────────

    async def is_available(self) -> bool:
        """Check if the Ollama server is reachable."""
        try:
            async with httpx.AsyncClient(timeout=5) as client:
                resp = await client.get(f"{self.base_url}/api/tags")
                return resp.status_code == 200
        except httpx.HTTPError:
            return False
