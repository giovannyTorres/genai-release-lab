"""Official SDK adapters. Contracts tested locally; no service verification without explicit LIVE opt-in."""

import asyncio
import os
from typing import TypeVar
import httpx
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from pydantic import BaseModel

T = TypeVar("T", bound=BaseModel)
LIMIT = asyncio.Semaphore(int(os.getenv("MODEL_CONCURRENCY", "2")))


class ProviderError(Exception):
    pass


def readiness(provider):
    key = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
    return {"ready": bool(os.getenv(key)), "missing": [] if os.getenv(key) else [key]}


class ModelProvider:
    def __init__(self, provider, model, transport=None):
        if provider not in {"openai", "gemini"}:
            raise ProviderError("Unsupported provider")
        self.provider, self.model = provider, model
        keyname = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
        key = os.getenv(keyname)
        if not key:
            raise ProviderError(f"LIVE configuration missing {keyname}")
        self.timeout = float(os.getenv("MODEL_TIMEOUT_SECONDS", "25"))
        self.max_tokens = int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "1500"))
        self.retries = int(os.getenv("MODEL_MAX_RETRIES", "1"))
        if not 1 <= self.timeout <= 25 or not 1 <= self.max_tokens <= 8192 or not 0 <= self.retries <= 1:
            raise ProviderError("Model limits exceed supported bounds")
        self.http = httpx.AsyncClient(transport=transport, timeout=self.timeout)
        if provider == "openai":
            self.client = AsyncOpenAI(
                api_key=key, http_client=self.http, max_retries=self.retries, timeout=self.timeout
            )
        else:
            self.client = genai.Client(
                api_key=key,
                http_options=types.HttpOptions(
                    httpx_async_client=self.http,
                    timeout=int(self.timeout * 1000),
                    retry_options=types.HttpRetryOptions(attempts=self.retries + 1),
                ),
            )

    async def structured(self, prompt: str, schema: type[T]) -> tuple[T, int | None]:
        async with LIMIT:
            try:
                async with asyncio.timeout(55):
                    if self.provider == "openai":
                        response = await self.client.responses.create(
                            model=self.model,
                            input=prompt,
                            max_output_tokens=self.max_tokens,
                            text={
                                "format": {
                                    "type": "json_schema",
                                    "name": schema.__name__,
                                    "schema": schema.model_json_schema(),
                                    "strict": False,
                                }
                            },
                        )
                        text = response.output_text
                        tokens = response.usage.total_tokens if response.usage else None
                    else:
                        response = await self.client.aio.models.generate_content(
                            model=self.model,
                            contents=prompt,
                            config=types.GenerateContentConfig(
                                response_mime_type="application/json",
                                response_json_schema=schema.model_json_schema(),
                                max_output_tokens=self.max_tokens,
                            ),
                        )
                        text = response.text
                        tokens = (
                            response.usage_metadata.total_token_count if response.usage_metadata else None
                        )
                    return schema.model_validate_json(text or ""), tokens
            except asyncio.CancelledError:
                raise
            except Exception as exc:
                # No raw provider errors, request headers or prompts in public error text.
                raise ProviderError("Model request or structured response validation failed") from exc

    async def close(self):
        await self.http.aclose()
        if self.provider == "gemini":
            await self.client.aio.aclose()
