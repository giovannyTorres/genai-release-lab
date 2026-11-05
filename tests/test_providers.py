"""HTTP envelopes based on official response contracts, not recorded LIVE responses.

Sources: OpenAI structured-outputs guide and Google generate-content API reference.
The successful JSON payload intentionally also occurs inside failed terminal responses.
"""

import asyncio
import copy
import json
import traceback

import httpx
import pytest

from release_lab import providers
from release_lab.providers import ModelProvider, ProviderError
from release_lab.schemas import JudgeResult

STRUCTURED_TEXT = json.dumps({"verdict": "pass", "reason": "Original synthetic contract example"})
OPENAI_RESPONSE = {
    "id": "resp_contract",
    "object": "response",
    "created_at": 1741476542,
    "status": "completed",
    "error": None,
    "incomplete_details": None,
    "instructions": None,
    "max_output_tokens": 1500,
    "model": "gpt-4.1-mini",
    "output": [
        {
            "type": "message",
            "id": "msg_contract",
            "role": "assistant",
            "status": "completed",
            "content": [{"type": "output_text", "text": STRUCTURED_TEXT, "annotations": []}],
        }
    ],
    "parallel_tool_calls": True,
    "usage": {
        "input_tokens": 5,
        "input_tokens_details": {"cached_tokens": 0},
        "output_tokens": 4,
        "output_tokens_details": {"reasoning_tokens": 0},
        "total_tokens": 9,
    },
    "metadata": {},
}
GEMINI_RESPONSE = {
    "candidates": [
        {
            "content": {"role": "model", "parts": [{"text": STRUCTURED_TEXT}]},
            "finishReason": "STOP",
            "index": 0,
        }
    ],
    "modelVersion": "gemini-2.5-flash",
    "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 4, "totalTokenCount": 9},
}


@pytest.fixture(autouse=True)
def keys(monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")


def envelope(provider):
    return copy.deepcopy(OPENAI_RESPONSE if provider == "openai" else GEMINI_RESPONSE)


@pytest.mark.parametrize("provider", ["openai", "gemini"])
async def test_official_sdk_structured_transport(provider):
    seen = []

    def handler(request):
        body = json.loads(request.content)
        seen.append(body)
        if provider == "openai":
            assert request.url.path == "/v1/responses"
            assert body["model"] == "gpt-4.1-mini"
            assert body["max_output_tokens"] == 1500
            assert body["text"]["format"]["type"] == "json_schema"
            assert body["text"]["format"]["schema"] == JudgeResult.model_json_schema()
            assert body["input"] == "Test"
        else:
            assert request.url.path.endswith("/models/gemini-2.5-flash:generateContent")
            assert body["contents"] == [{"parts": [{"text": "Test"}], "role": "user"}]
            assert body["generationConfig"]["responseMimeType"] == "application/json"
            assert body["generationConfig"]["responseJsonSchema"] == JudgeResult.model_json_schema()
            assert body["generationConfig"]["maxOutputTokens"] == 1500
        return httpx.Response(200, json=envelope(provider))

    adapter = ModelProvider(
        provider, "gpt-4.1-mini" if provider == "openai" else "gemini-2.5-flash", httpx.MockTransport(handler)
    )
    try:
        result, tokens = await adapter.structured("Test", JudgeResult)
        assert result.verdict == "pass" and tokens == 9 and len(seen) == 1
    finally:
        await adapter.close()
    assert adapter.http.is_closed
    if provider == "gemini":
        assert adapter.client._api_client._httpx_client.is_closed


@pytest.mark.parametrize("status", ["incomplete", "failed", "cancelled", "in_progress", "queued", None])
async def test_openai_incomplete_json_is_never_scored(status):
    body = envelope("openai")
    body["status"] = status
    if status == "incomplete":
        body["incomplete_details"] = {"reason": "max_output_tokens"}
    adapter = ModelProvider(
        "openai", "gpt-4.1-mini", httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    )
    try:
        with pytest.raises(ProviderError, match="did not complete"):
            await adapter.structured("Test", JudgeResult)
    finally:
        await adapter.close()


@pytest.mark.parametrize(
    "mutation", ["refusal", "empty", "unfinished_message", "malformed_json", "wrong_schema"]
)
async def test_openai_refusal_and_invalid_outputs_fail_closed(mutation):
    body = envelope("openai")
    message = body["output"][0]
    if mutation == "refusal":
        message["content"].append({"type": "refusal", "refusal": "Synthetic refusal"})
    elif mutation == "empty":
        body["output"] = []
    elif mutation == "unfinished_message":
        message["status"] = "incomplete"
    else:
        message["content"][0]["text"] = "{" if mutation == "malformed_json" else '{"verdict":"unknown"}'
    adapter = ModelProvider(
        "openai", "gpt-4.1-mini", httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    )
    try:
        with pytest.raises(ProviderError):
            await adapter.structured("Test", JudgeResult)
    finally:
        await adapter.close()


@pytest.mark.parametrize("finish", ["MAX_TOKENS", "SAFETY", "RECITATION", "MALFORMED_FUNCTION_CALL", None])
async def test_gemini_nonterminal_or_blocked_json_is_never_scored(finish):
    body = envelope("gemini")
    body["candidates"][0]["finishReason"] = finish
    adapter = ModelProvider(
        "gemini", "gemini-2.5-flash", httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    )
    try:
        with pytest.raises(ProviderError, match="did not complete"):
            await adapter.structured("Test", JudgeResult)
    finally:
        await adapter.close()


@pytest.mark.parametrize(
    "mutation",
    ["blocked_prompt", "no_candidates", "safety_rating", "unexpected_tool", "thought_only", "malformed_json"],
)
async def test_gemini_refusal_and_invalid_outputs_fail_closed(mutation):
    body = envelope("gemini")
    candidate = body["candidates"][0]
    if mutation == "blocked_prompt":
        body["promptFeedback"] = {"blockReason": "SAFETY"}
    elif mutation == "no_candidates":
        body["candidates"] = []
    elif mutation == "safety_rating":
        candidate["safetyRatings"] = [
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "probability": "HIGH", "blocked": True}
        ]
    elif mutation == "unexpected_tool":
        candidate["content"]["parts"].append({"functionCall": {"name": "unexpected", "args": {}}})
    elif mutation == "thought_only":
        candidate["content"]["parts"][0]["thought"] = True
    else:
        candidate["content"]["parts"][0]["text"] = "{"
    adapter = ModelProvider(
        "gemini", "gemini-2.5-flash", httpx.MockTransport(lambda r: httpx.Response(200, json=body))
    )
    try:
        with pytest.raises(ProviderError):
            await adapter.structured("Test", JudgeResult)
    finally:
        await adapter.close()


@pytest.mark.parametrize("provider", ["openai", "gemini"])
async def test_sdk_failures_are_sanitized_in_tracebacks(provider):
    adapter = ModelProvider(
        provider,
        "model",
        httpx.MockTransport(
            lambda r: httpx.Response(
                400,
                json={"error": {"message": "private-test-secret", "code": 400, "status": "INVALID_ARGUMENT"}},
            )
        ),
    )
    try:
        with pytest.raises(ProviderError, match="validation failed") as error:
            await adapter.structured("test", JudgeResult)
        assert "private-test-secret" not in "".join(traceback.format_exception(error.value))
    finally:
        await adapter.close()


@pytest.mark.parametrize("provider", ["openai", "gemini"])
@pytest.mark.parametrize("recover", [False, True])
async def test_rate_limit_retry_is_bounded_and_can_recover(provider, recover):
    calls = []

    def handler(request):
        calls.append(request)
        if recover and len(calls) == 2:
            return httpx.Response(200, json=envelope(provider))
        return httpx.Response(
            429,
            headers={"retry-after": "0"},
            json={"error": {"code": 429, "status": "RESOURCE_EXHAUSTED", "message": "Synthetic quota error"}},
        )

    adapter = ModelProvider(provider, "model", httpx.MockTransport(handler))
    try:
        if recover:
            result, _ = await adapter.structured("Test", JudgeResult)
            assert result.verdict == "pass"
        else:
            with pytest.raises(ProviderError):
                await adapter.structured("Test", JudgeResult)
        assert len(calls) == 2
    finally:
        await adapter.close()


@pytest.mark.parametrize("provider", ["openai", "gemini"])
@pytest.mark.parametrize("cancel", [False, True])
async def test_hanging_transport_is_cancelled_or_deadlined(provider, cancel, monkeypatch):
    entered = asyncio.Event()
    interrupted = asyncio.Event()

    async def handler(request):
        entered.set()
        try:
            await asyncio.Event().wait()
        finally:
            interrupted.set()

    monkeypatch.setattr(providers, "REQUEST_DEADLINE_SECONDS", 0.05)
    adapter = ModelProvider(provider, "model", httpx.MockTransport(handler))
    try:
        task = asyncio.create_task(adapter.structured("Test", JudgeResult))
        await entered.wait()
        if cancel:
            task.cancel()
        with pytest.raises(asyncio.CancelledError if cancel else ProviderError):
            await task
        assert interrupted.is_set()
    finally:
        await adapter.close()
    assert adapter.http.is_closed


async def test_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="missing OPENAI_API_KEY"):
        ModelProvider("openai", "model")


def test_invalid_provider_not_reported_ready():
    assert not providers.readiness("unsupported")["ready"]


async def test_deadline_includes_waiting_for_model_capacity(monkeypatch):
    monkeypatch.setattr(providers, "LIMIT", asyncio.Semaphore(0))
    monkeypatch.setattr(providers, "REQUEST_DEADLINE_SECONDS", 0.01)
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(200, json=envelope("openai"))

    adapter = ModelProvider("openai", "gpt-4.1-mini", httpx.MockTransport(handler))
    try:
        with pytest.raises(ProviderError):
            await adapter.structured("queued input", JudgeResult)
        assert calls == []
    finally:
        await adapter.close()


@pytest.mark.parametrize("provider", ["openai", "gemini"])
async def test_concurrent_model_requests_obey_shared_limit(provider, monkeypatch):
    monkeypatch.setattr(providers, "LIMIT", asyncio.Semaphore(2))
    two_entered, release = asyncio.Event(), asyncio.Event()
    active = 0
    maximum = 0

    async def handler(request):
        nonlocal active, maximum
        active += 1
        maximum = max(maximum, active)
        if active == 2:
            two_entered.set()
        try:
            await release.wait()
            return httpx.Response(200, json=envelope(provider))
        finally:
            active -= 1

    adapters = [ModelProvider(provider, "model", httpx.MockTransport(handler)) for _ in range(3)]
    tasks = [asyncio.create_task(a.structured("synthetic input", JudgeResult)) for a in adapters]
    try:
        await asyncio.wait_for(two_entered.wait(), timeout=1)
        assert maximum == 2
        release.set()
        results = await asyncio.gather(*tasks)
        assert all(result.verdict == "pass" for result, _ in results)
        assert maximum == 2
    finally:
        release.set()
        await asyncio.gather(*(adapter.close() for adapter in adapters))


async def test_gemini_api_key_adapter_does_not_switch_to_vertex_from_environment(monkeypatch):
    monkeypatch.setenv("GOOGLE_GENAI_USE_VERTEXAI", "true")
    seen = []

    def handler(request):
        seen.append(request.url.host)
        return httpx.Response(200, json=envelope("gemini"))

    adapter = ModelProvider("gemini", "gemini-2.5-flash", httpx.MockTransport(handler))
    try:
        result, _ = await adapter.structured("Test", JudgeResult)
        assert result.verdict == "pass"
        assert seen == ["generativelanguage.googleapis.com"]
    finally:
        await adapter.close()


@pytest.mark.parametrize("provider", ["openai", "gemini"])
@pytest.mark.parametrize(
    "text",
    [
        '{"verdict":"fail","verdict":"pass","reason":"duplicate"}',
        '{"answer":"example","tool_calls":[{"name":"example","arguments":{"amount":NaN}}]}',
        '{"answer":"example","tool_calls":[{"name":"example","arguments":{"amount":1e999}}]}',
    ],
)
async def test_nonstandard_json_cannot_enter_persistent_results(provider, text):
    from release_lab.schemas import Output

    body = envelope(provider)
    if provider == "openai":
        body["output"][0]["content"][0]["text"] = text
    else:
        body["candidates"][0]["content"]["parts"][0]["text"] = text
    schema = JudgeResult if "verdict" in text else Output
    adapter = ModelProvider(
        provider, "model", httpx.MockTransport(lambda request: httpx.Response(200, json=body))
    )
    try:
        with pytest.raises(ProviderError):
            await adapter.structured("Test", schema)
    finally:
        await adapter.close()
