"""Independent review of the endpoint execution boundary; no external network."""

from urllib.parse import urlsplit

import httpx
import pytest

from release_lab import endpoints
from release_lab.providers import ProviderError


def install_transport(monkeypatch, handler):
    original_client = httpx.AsyncClient

    async def checked_destination(url):
        return urlsplit(url), "93.184.216.34"

    def client(**kwargs):
        assert kwargs["follow_redirects"] is False
        assert kwargs["trust_env"] is False
        return original_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(endpoints, "resolve_public", checked_destination)
    monkeypatch.setattr(endpoints.httpx, "AsyncClient", client)


async def test_endpoint_query_does_not_enter_http_client_logs(monkeypatch, caplog):
    import logging
    from release_lab.telemetry import configure_logging

    caplog.set_level(logging.INFO)
    configure_logging()
    install_transport(monkeypatch, lambda request: httpx.Response(200, json={"answer": "example"}))
    await endpoints.invoke("https://evaluator.example/evaluate?token=PRIVATE_QUERY_CANARY", {})
    logging.getLogger("release.worker").info("Operational event remains available")
    assert "PRIVATE_QUERY_CANARY" not in caplog.text
    assert "Operational event remains available" in caplog.text


@pytest.mark.asyncio
async def test_execution_pins_address_but_preserves_tls_identity(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.host == "93.184.216.34"
        assert request.url.path == "/evaluate"
        assert request.headers["host"] == "evaluator.example"
        assert request.extensions["sni_hostname"] == "evaluator.example"
        return httpx.Response(200, json={"answer": "synthetic result"})

    install_transport(monkeypatch, handler)
    result = await endpoints.invoke("https://evaluator.example/evaluate", {"case_id": "review"})
    assert result == {"answer": "synthetic result"}
    assert len(seen) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "status,body,headers",
    [
        (302, b"", {"Location": "http://169.254.169.254/metadata"}),
        (200, b"x" * 256_001, {}),
        (200, b"not valid JSON", {}),
    ],
)
async def test_redirect_oversize_and_invalid_json_fail_closed(monkeypatch, status, body, headers):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, content=body, headers=headers)

    install_transport(monkeypatch, handler)
    with pytest.raises(ProviderError, match="Registered endpoint request failed"):
        await endpoints.invoke("https://evaluator.example/evaluate", {})
    assert len(calls) == 1  # The redirect destination is never requested.


@pytest.mark.asyncio
async def test_dns_failure_is_sanitized_for_the_worker(monkeypatch):
    import socket
    import traceback

    async def failed_dns(url):
        raise socket.gaierror("private-host-and-query-value")

    monkeypatch.setattr(endpoints, "resolve_public", failed_dns)
    with pytest.raises(ProviderError) as error:
        await endpoints.invoke("https://evaluator.example/evaluate", {})
    assert "private-host-and-query-value" not in "".join(traceback.format_exception(error.value))


@pytest.mark.asyncio
async def test_slow_drip_body_has_overall_deadline_and_is_closed(monkeypatch):
    import asyncio

    closed = asyncio.Event()

    class SlowBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            while True:
                yield b" "
                await asyncio.sleep(0.01)

        async def aclose(self):
            closed.set()

    install_transport(monkeypatch, lambda request: httpx.Response(200, stream=SlowBody()))
    monkeypatch.setattr(endpoints, "TOTAL_TIMEOUT_SECONDS", 0.03)
    with pytest.raises(ProviderError):
        await endpoints.invoke("https://evaluator.example/evaluate", {})
    assert closed.is_set()


@pytest.mark.asyncio
async def test_endpoint_cancellation_closes_active_response(monkeypatch):
    import asyncio

    entered, closed = asyncio.Event(), asyncio.Event()

    class WaitingBody(httpx.AsyncByteStream):
        async def __aiter__(self):
            entered.set()
            await asyncio.Event().wait()
            yield b"{}"

        async def aclose(self):
            closed.set()

    install_transport(monkeypatch, lambda request: httpx.Response(200, stream=WaitingBody()))
    task = asyncio.create_task(endpoints.invoke("https://evaluator.example/evaluate", {}))
    await entered.wait()
    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    assert closed.is_set()


@pytest.mark.parametrize("body", [b'{"value":NaN}', b'{"value":1,"value":2}', b'{"value":1e999}'])
async def test_endpoint_nonstandard_json_is_rejected_before_persistence(monkeypatch, body):
    install_transport(monkeypatch, lambda request: httpx.Response(200, content=body))
    with pytest.raises(ProviderError):
        await endpoints.invoke("https://evaluator.example/evaluate", {})
