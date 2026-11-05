"""Operator-only HTTPS destinations, public DNS pinning, bounded response, no redirects."""

import asyncio
import ipaddress
import os
import socket
from urllib.parse import urlsplit, urlunsplit
import httpx
from .providers import ProviderError
from .json_contract import strict_loads

DNS_TIMEOUT_SECONDS = 5
TOTAL_TIMEOUT_SECONDS = 25


def host_allowed(url):
    parsed = urlsplit(url)
    allowed = {x.strip().lower() for x in os.getenv("ENDPOINT_ALLOWED_HOSTS", "").split(",") if x.strip()}
    if (
        parsed.scheme != "https"
        or not parsed.hostname
        or parsed.username
        or parsed.password
        or parsed.fragment
        or parsed.port not in (None, 443)
        or parsed.hostname.lower() not in allowed
    ):
        raise ValueError(
            "Endpoint must use HTTPS port 443 on an operator-configured exact host allowlist, without credentials or fragments"
        )
    return parsed


async def resolve_public(url):
    parsed = host_allowed(url)
    async with asyncio.timeout(DNS_TIMEOUT_SECONDS):
        addresses = await asyncio.get_running_loop().getaddrinfo(
            parsed.hostname, 443, type=socket.SOCK_STREAM
        )
    ips = {a[4][0] for a in addresses}
    if not ips or any(
        not ipaddress.ip_address(ip).is_global
        or getattr(ipaddress.ip_address(ip), "ipv4_mapped", None) is not None
        for ip in ips
    ):
        raise ValueError("Endpoint resolves to a forbidden network")
    return parsed, sorted(ips)[0]


async def invoke(url, payload):
    try:
        # Bound DNS, connect, retry-free request, and slow-drip bodies as one operation.
        async with asyncio.timeout(TOTAL_TIMEOUT_SECONDS):
            parsed, address = await resolve_public(url)
            ip_host = f"[{address}]" if ":" in address else address
            pinned = urlunsplit(("https", ip_host, parsed.path or "/", parsed.query, ""))
            # Pin the checked IP; keep TLS SNI and Host as the allowlisted original host.
            # Direct egress is the supported trust model; environment proxy routing is not enabled.
            async with httpx.AsyncClient(timeout=20, follow_redirects=False, trust_env=False) as client:
                async with client.stream(
                    "POST",
                    pinned,
                    json=payload,
                    headers={"Host": parsed.hostname},
                    extensions={"sni_hostname": parsed.hostname},
                ) as response:
                    response.raise_for_status()
                    if response.is_redirect:
                        raise ValueError("Redirects are forbidden")
                    body = bytearray()
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        body.extend(chunk)
                        if len(body) > 256_000:
                            raise ValueError("Endpoint response exceeds limit")
                    return strict_loads(body)
    except asyncio.CancelledError:
        raise
    except (httpx.HTTPError, ValueError, OSError, TimeoutError):
        raise ProviderError("Registered endpoint request failed") from None
