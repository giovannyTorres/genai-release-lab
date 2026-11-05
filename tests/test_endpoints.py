import asyncio
import pytest
from release_lab.endpoints import host_allowed, resolve_public


@pytest.mark.parametrize(
    "url",
    [
        "http://allowed.example",
        "https://127.0.0.1",
        "https://allowed.example:444",
        "https://allowed.example.evil.test",
        "https://user:pass@allowed.example",
        "https://allowed.example/#secret",
    ],
)
def test_reject_untrusted_destination(url, monkeypatch):
    monkeypatch.setenv("ENDPOINT_ALLOWED_HOSTS", "allowed.example")
    with pytest.raises(ValueError):
        host_allowed(url)


@pytest.mark.parametrize("ip", ["127.0.0.1", "10.0.0.1", "169.254.169.254", "::1", "::ffff:8.8.8.8"])
async def test_reject_private_or_mapped_dns(ip, monkeypatch):
    monkeypatch.setenv("ENDPOINT_ALLOWED_HOSTS", "allowed.example")

    async def dns(*a, **k):
        return [(None, None, None, None, (ip, 443))]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", dns)
    with pytest.raises(ValueError):
        await resolve_public("https://allowed.example/evaluate")
