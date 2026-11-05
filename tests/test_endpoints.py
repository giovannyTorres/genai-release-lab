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


async def test_dns_resolution_is_time_bounded(monkeypatch):
    from release_lab import endpoints

    monkeypatch.setenv("ENDPOINT_ALLOWED_HOSTS", "allowed.example")
    monkeypatch.setattr(endpoints, "DNS_TIMEOUT_SECONDS", 0.01)

    async def dns(*args, **kwargs):
        await asyncio.Event().wait()

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", dns)
    with pytest.raises(TimeoutError):
        await resolve_public("https://allowed.example/evaluate")


async def test_mixed_public_and_private_dns_is_rejected(monkeypatch):
    monkeypatch.setenv("ENDPOINT_ALLOWED_HOSTS", "allowed.example")

    async def dns(*args, **kwargs):
        return [(None, None, None, None, (ip, 443)) for ip in ["93.184.216.34", "10.0.0.1"]]

    monkeypatch.setattr(asyncio.get_running_loop(), "getaddrinfo", dns)
    with pytest.raises(ValueError, match="forbidden network"):
        await resolve_public("https://allowed.example/evaluate")
