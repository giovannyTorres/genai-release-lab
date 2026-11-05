"""Shared worker trace initialization; HTTP tracing is initialized by the API."""

import os
import logging
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def configure_logging():
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    # HTTP client INFO/DEBUG events include raw URLs and may expose endpoint query secrets.
    for name in ("httpx", "httpx2", "httpcore"):
        logging.getLogger(name).setLevel(logging.WARNING)


def configure_worker():
    provider = TracerProvider()
    if os.getenv("OTEL_CONSOLE", "false") == "true":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
