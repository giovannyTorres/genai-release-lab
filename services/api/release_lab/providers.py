"""Official SDK adapters; terminal response state and local schemas are both required.

Only structured generation is supported here, not streaming or model tool execution.
Contract tests use documented HTTP envelopes; no service verification is implied.
"""

import asyncio
import os
from typing import TypeVar

import httpx
from google import genai
from google.genai import types
from openai import AsyncOpenAI
from pydantic import BaseModel
from .json_contract import strict_loads

T = TypeVar("T", bound=BaseModel)
_CONCURRENCY = int(os.getenv("MODEL_CONCURRENCY", "2"))
if not 1 <= _CONCURRENCY <= 16:
    raise ValueError("MODEL_CONCURRENCY must be between 1 and 16")
LIMIT = asyncio.Semaphore(_CONCURRENCY)
REQUEST_DEADLINE_SECONDS = 55


class ProviderError(Exception):
    """Safe, user-facing error with no provider response body or credentials."""


def readiness(provider):
    if provider not in {"openai", "gemini"}:
        return {"ready": False, "missing": ["MODEL_PROVIDER must be openai or gemini"]}
    key = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
    return {"ready": bool(os.getenv(key)), "missing": [] if os.getenv(key) else [key]}


def openai_text(response) -> str:
    # A parseable JSON prefix is still unusable when generation was incomplete.
    if response.status != "completed" or response.error is not None:
        raise ProviderError("Model response did not complete; retry or review the output-token limit")
    parts = []
    for item in response.output:
        if item.type == "reasoning":
            continue  # Private model reasoning is never an evaluation output.
        if item.type != "message" or item.status != "completed":
            raise ProviderError("Model returned an unsupported structured response")
        for part in item.content:
            if part.type == "refusal":
                raise ProviderError("Model declined the request; review the evaluation input")
            if part.type != "output_text":
                raise ProviderError("Model returned an unsupported structured response")
            parts.append(part.text)
    if not parts or not "".join(parts).strip():
        raise ProviderError("Model returned no structured output")
    return "".join(parts)


def gemini_text(response) -> str:
    feedback = response.prompt_feedback
    if feedback and feedback.block_reason not in (None, types.BlockedReason.BLOCKED_REASON_UNSPECIFIED):
        raise ProviderError("Model blocked the request; review the evaluation input")
    candidates = response.candidates or []
    if len(candidates) != 1 or candidates[0].finish_reason != types.FinishReason.STOP:
        raise ProviderError("Model response did not complete; retry or review the output-token limit")
    candidate = candidates[0]
    if any(rating.blocked for rating in candidate.safety_ratings or []):
        raise ProviderError("Model blocked the response; review the evaluation input")
    parts = candidate.content.parts if candidate.content else []
    text = []
    for part in parts or []:
        if part.thought:
            continue
        if part.function_call is not None or part.function_response is not None:
            raise ProviderError("Model returned a tool call where structured output was required")
        if part.text:
            text.append(part.text)
    if not text or not "".join(text).strip():
        raise ProviderError("Model returned no structured output")
    return "".join(text)


class ModelProvider:
    def __init__(self, provider, model, transport=None):
        if provider not in {"openai", "gemini"}:
            raise ProviderError("Unsupported provider")
        if not isinstance(model, str) or not model.strip():
            raise ProviderError("A nonempty model identifier is required")
        self.provider, self.model = provider, model
        keyname = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
        key = os.getenv(keyname)
        if not key:
            raise ProviderError(f"LIVE configuration missing {keyname}")
        try:
            self.timeout = float(os.getenv("MODEL_TIMEOUT_SECONDS", "25"))
            self.max_tokens = int(os.getenv("MODEL_MAX_OUTPUT_TOKENS", "1500"))
            self.retries = int(os.getenv("MODEL_MAX_RETRIES", "1"))
        except ValueError:
            raise ProviderError("Model limits must be numeric") from None
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
                vertexai=False,
                http_options=types.HttpOptions(
                    httpx_async_client=self.http,
                    timeout=int(self.timeout * 1000),
                    retry_options=types.HttpRetryOptions(
                        attempts=self.retries + 1, initial_delay=0.25, max_delay=1
                    ),
                ),
            )

    async def structured(self, prompt: str, schema: type[T]) -> tuple[T, int | None]:
        try:
            # Includes queue time, network retry/backoff and response validation.
            async with asyncio.timeout(REQUEST_DEADLINE_SECONDS), LIMIT:
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
                                # Output contains arbitrary typed tool-argument dictionaries.
                                # Strict OpenAI schema subsets cannot represent those; validate locally.
                                "strict": False,
                            }
                        },
                    )
                    text = openai_text(response)
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
                    text = gemini_text(response)
                    tokens = response.usage_metadata.total_token_count if response.usage_metadata else None
                if tokens is not None and (not isinstance(tokens, int) or tokens < 0):
                    raise ProviderError("Model returned invalid usage metadata")
                return schema.model_validate(strict_loads(text)), tokens
        except asyncio.CancelledError:
            raise
        except ProviderError:
            raise
        except Exception:
            # Suppress chained provider bodies too: a traceback must not reveal secrets/prompts.
            raise ProviderError("Model request or structured response validation failed") from None

    async def close(self):
        try:
            if self.provider == "openai":
                await self.client.close()
            else:
                try:
                    await self.client.aio.aclose()
                finally:
                    self.client.close()  # Gemini owns a synchronous client even in its aio facade.
        finally:
            await self.http.aclose()  # The Gemini SDK deliberately does not close injected clients.
