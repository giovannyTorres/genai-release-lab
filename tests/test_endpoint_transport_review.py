"""Independent review of the endpoint execution boundary; no external network."""
from urllib.parse import urlsplit

import httpx
import pytest

from release_lab import endpoints
from release_lab.providers import ProviderError


def install_transport(monkeypatch, handler):
    original_client = httpx.AsyncClient

    async def checked_destination(url):
        return urlsplit(url), '93.184.216.34'

    def client(**kwargs):
        assert kwargs['follow_redirects'] is False
        assert kwargs['trust_env'] is False
        return original_client(transport=httpx.MockTransport(handler), **kwargs)

    monkeypatch.setattr(endpoints, 'resolve_public', checked_destination)
    monkeypatch.setattr(endpoints.httpx, 'AsyncClient', client)


@pytest.mark.asyncio
async def test_execution_pins_address_but_preserves_tls_identity(monkeypatch):
    seen = []

    def handler(request):
        seen.append(request)
        assert request.url.host == '93.184.216.34'
        assert request.url.path == '/evaluate'
        assert request.headers['host'] == 'evaluator.example'
        assert request.extensions['sni_hostname'] == 'evaluator.example'
        return httpx.Response(200, json={'answer': 'synthetic result'})

    install_transport(monkeypatch, handler)
    result = await endpoints.invoke('https://evaluator.example/evaluate', {'case_id': 'review'})
    assert result == {'answer': 'synthetic result'}
    assert len(seen) == 1


@pytest.mark.asyncio
@pytest.mark.parametrize('status,body,headers', [
    (302, b'', {'Location': 'http://169.254.169.254/metadata'}),
    (200, b'x' * 256_001, {}),
    (200, b'not valid JSON', {}),
])
async def test_redirect_oversize_and_invalid_json_fail_closed(monkeypatch, status, body, headers):
    calls = []

    def handler(request):
        calls.append(request)
        return httpx.Response(status, content=body, headers=headers)

    install_transport(monkeypatch, handler)
    with pytest.raises(ProviderError, match='Registered endpoint request failed'):
        await endpoints.invoke('https://evaluator.example/evaluate', {})
    assert len(calls) == 1  # The redirect destination is never requested.
