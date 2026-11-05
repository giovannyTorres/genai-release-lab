import json
import pytest
import httpx
from release_lab.providers import ModelProvider, ProviderError
from release_lab.schemas import JudgeResult


@pytest.mark.parametrize("provider", ["openai", "gemini"])
async def test_official_sdk_structured_transport(provider, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "synthetic-test-key")
    monkeypatch.setenv("GEMINI_API_KEY", "synthetic-test-key")
    seen = []

    def handler(request):
        seen.append(json.loads(request.content))
        text = json.dumps({"verdict": "pass", "reason": "Synthetic SDK transport fixture"})
        if provider == "openai":
            return httpx.Response(
                200,
                json={
                    "id": "resp_fixture",
                    "object": "response",
                    "created_at": 0,
                    "model": "fixture-model",
                    "output": [
                        {
                            "type": "message",
                            "id": "msg_fixture",
                            "role": "assistant",
                            "status": "completed",
                            "content": [{"type": "output_text", "text": text, "annotations": []}],
                        }
                    ],
                    "usage": {"input_tokens": 5, "output_tokens": 4, "total_tokens": 9},
                },
            )
        return httpx.Response(
            200,
            json={
                "candidates": [
                    {"content": {"role": "model", "parts": [{"text": text}]}, "finishReason": "STOP"}
                ],
                "usageMetadata": {"promptTokenCount": 5, "candidatesTokenCount": 4, "totalTokenCount": 9},
            },
        )

    adapter = ModelProvider(provider, "fixture-model", httpx.MockTransport(handler))
    try:
        result, tokens = await adapter.structured("Test", JudgeResult)
        assert result.verdict == "pass" and tokens == 9
        assert len(seen) == 1
    finally:
        await adapter.close()


@pytest.mark.parametrize("provider", ["openai", "gemini"])
async def test_sdk_failures_are_sanitized(provider, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "test-secret")
    monkeypatch.setenv("GEMINI_API_KEY", "test-secret")
    adapter = ModelProvider(
        provider,
        "model",
        httpx.MockTransport(
            lambda r: httpx.Response(
                400,
                json={
                    "error": {
                        "message": "test-secret private detail",
                        "code": 400,
                        "status": "INVALID_ARGUMENT",
                    }
                },
            )
        ),
    )
    with pytest.raises(ProviderError, match="validation failed") as error:
        await adapter.structured("test", JudgeResult)
    assert "test-secret" not in str(error.value)
    await adapter.close()


async def test_missing_key(monkeypatch):
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    with pytest.raises(ProviderError, match="missing OPENAI_API_KEY"):
        ModelProvider("openai", "model")
