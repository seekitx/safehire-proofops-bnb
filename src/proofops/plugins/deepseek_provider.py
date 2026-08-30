from __future__ import annotations

import os
from collections.abc import Mapping
from typing import Any

import httpx

from proofops.domain.errors import AdapterUnavailableError
from proofops.harness.contracts import HarnessPlugin, PluginContext


class DeepSeekProvider:
    """Optional OpenAI-compatible provider isolated behind a narrow interface.

    It is deliberately absent from scoring and transaction authority. Responses
    can explain, summarize or challenge deterministic artifacts only.
    """

    def __init__(self, *, api_key: str, base_url: str, model: str, timeout: float) -> None:
        if not api_key:
            raise AdapterUnavailableError("DEEPSEEK_API_KEY is not configured")
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._timeout = timeout

    async def complete(
        self,
        *,
        system: str,
        user: str,
        temperature: float = 0.1,
        metadata: Mapping[str, Any] | None = None,
    ) -> str:
        payload = {
            "model": self._model,
            "temperature": temperature,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
        }
        headers = {"Authorization": f"Bearer {self._api_key}", "Content-Type": "application/json"}
        async with httpx.AsyncClient(timeout=self._timeout) as client:
            response = await client.post(
                f"{self._base_url}/chat/completions", headers=headers, json=payload
            )
            response.raise_for_status()
            data = response.json()
        return str(data["choices"][0]["message"]["content"])


class DeepSeekProviderPlugin(HarnessPlugin):
    async def load(self, context: PluginContext) -> None:
        provider = DeepSeekProvider(
            api_key=os.getenv("DEEPSEEK_API_KEY", ""),
            base_url=os.getenv("DEEPSEEK_BASE_URL", "https://api.deepseek.com"),
            model=os.getenv(
                "DEEPSEEK_MODEL", str(self.manifest.config.get("model", "deepseek-chat"))
            ),
            timeout=float(
                os.getenv(
                    "DEEPSEEK_TIMEOUT_SECONDS", self.manifest.config.get("timeout_seconds", 20)
                )
            ),
        )
        context.provide("llm.provider", provider)
