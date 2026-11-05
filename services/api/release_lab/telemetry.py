"""Shared worker trace initialization; HTTP tracing is initialized by the API."""

import os
from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter


def configure_worker():
    provider = TracerProvider()
    if os.getenv("OTEL_CONSOLE", "false") == "true":
        provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)
