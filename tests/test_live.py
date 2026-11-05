import os
import pytest
from release_lab.providers import ModelProvider
from release_lab.schemas import JudgeResult


@pytest.mark.live
@pytest.mark.skipif(
    os.getenv("RUN_LIVE") != "1", reason="Explicit RUN_LIVE=1 and credentials required; potentially billable"
)
@pytest.mark.parametrize("provider,model", [("openai", "gpt-4.1-mini"), ("gemini", "gemini-2.5-flash")])
async def test_live_smoke(provider, model):
    key = "OPENAI_API_KEY" if provider == "openai" else "GEMINI_API_KEY"
    if not os.getenv(key):
        pytest.skip(f"{key} missing")
    adapter = ModelProvider(provider, os.getenv("LIVE_SMOKE_MODEL", model))
    try:
        result, _ = await adapter.structured(
            "Return verdict pass and reason: connectivity smoke test only.", JudgeResult
        )
        assert result.verdict == "pass"
    finally:
        await adapter.close()
