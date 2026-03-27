"""
OpenTelemetry initialisation for the MuleSoft-to-SpringBoot Migration API.

Configures distributed tracing with OTLP export and optional Azure Monitor
export.  Instruments FastAPI, Celery, SQLAlchemy, and httpx automatically.

Usage
-----
Call ``init_telemetry(settings)`` once during application startup (lifespan).
Use ``get_tracer(name)`` in any module to obtain a configured tracer.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)


def init_telemetry(settings) -> None:
    """
    Bootstrap OpenTelemetry tracing for the application.

    Parameters
    ----------
    settings : api.config.Settings
        Application settings instance.  The following attributes are used:

        - ``settings.app_name``
        - ``settings.environment.value``
        - ``api.__version__``  (imported internally)

    The function is safe to call even if OpenTelemetry packages are not
    installed — a warning is logged and the call becomes a no-op.
    """
    try:
        from opentelemetry import trace
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor
    except ImportError:
        logger.warning(
            "telemetry.opentelemetry_not_installed",
            hint="Install opentelemetry-sdk to enable distributed tracing.",
        )
        return

    from api import __version__

    # ── Resource attributes ──────────────────────────────────────
    resource = Resource.create(
        {
            "service.name": settings.app_name,
            "service.version": __version__,
            "deployment.environment": settings.environment.value,
        }
    )

    provider = TracerProvider(resource=resource)

    # ── OTLP exporter (gRPC) ────────────────────────────────────
    try:
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
            OTLPSpanExporter,
        )

        otlp_exporter = OTLPSpanExporter()  # reads OTEL_EXPORTER_OTLP_ENDPOINT env var
        provider.add_span_processor(BatchSpanProcessor(otlp_exporter))
        logger.info("telemetry.otlp_exporter_configured")
    except ImportError:
        logger.debug("telemetry.otlp_exporter_not_available")
    except Exception as exc:
        logger.warning("telemetry.otlp_exporter_error", error=str(exc))

    # ── Azure Monitor exporter (optional) ────────────────────────
    app_insights_cs = getattr(settings, "app_insights_connection_string", None)
    if app_insights_cs:
        try:
            from azure.monitor.opentelemetry.exporter import (
                AzureMonitorTraceExporter,
            )

            azure_exporter = AzureMonitorTraceExporter(
                connection_string=app_insights_cs,
            )
            provider.add_span_processor(BatchSpanProcessor(azure_exporter))
            logger.info("telemetry.azure_monitor_configured")
        except ImportError:
            logger.warning(
                "telemetry.azure_monitor_not_installed",
                hint="Install azure-monitor-opentelemetry-exporter.",
            )
        except Exception as exc:
            logger.warning("telemetry.azure_monitor_error", error=str(exc))

    # ── Set global tracer provider ───────────────────────────────
    trace.set_tracer_provider(provider)

    # ── Auto-instrument libraries ────────────────────────────────
    _instrument_fastapi()
    _instrument_celery()
    _instrument_sqlalchemy()
    _instrument_httpx()

    logger.info(
        "telemetry.initialized",
        service=settings.app_name,
        environment=settings.environment.value,
    )


def get_tracer(name: str):
    """
    Return an OpenTelemetry tracer for the given module/component name.

    Falls back to a no-op tracer if OpenTelemetry is not installed.
    """
    try:
        from opentelemetry import trace

        return trace.get_tracer(name)
    except ImportError:
        return _NoOpTracer()


# ── Private helpers ──────────────────────────────────────────────


def _instrument_fastapi() -> None:
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor().instrument()
        logger.debug("telemetry.instrumented.fastapi")
    except ImportError:
        logger.debug("telemetry.instrument_skip.fastapi")
    except Exception as exc:
        logger.warning("telemetry.instrument_error.fastapi", error=str(exc))


def _instrument_celery() -> None:
    try:
        from opentelemetry.instrumentation.celery import CeleryInstrumentor

        CeleryInstrumentor().instrument()
        logger.debug("telemetry.instrumented.celery")
    except ImportError:
        logger.debug("telemetry.instrument_skip.celery")
    except Exception as exc:
        logger.warning("telemetry.instrument_error.celery", error=str(exc))


def _instrument_sqlalchemy() -> None:
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor

        SQLAlchemyInstrumentor().instrument()
        logger.debug("telemetry.instrumented.sqlalchemy")
    except ImportError:
        logger.debug("telemetry.instrument_skip.sqlalchemy")
    except Exception as exc:
        logger.warning("telemetry.instrument_error.sqlalchemy", error=str(exc))


def _instrument_httpx() -> None:
    try:
        from opentelemetry.instrumentation.httpx import HTTPXClientInstrumentor

        HTTPXClientInstrumentor().instrument()
        logger.debug("telemetry.instrumented.httpx")
    except ImportError:
        logger.debug("telemetry.instrument_skip.httpx")
    except Exception as exc:
        logger.warning("telemetry.instrument_error.httpx", error=str(exc))


class _NoOpTracer:
    """Fallback tracer that does nothing when OTEL is not installed."""

    def start_span(self, *args, **kwargs):
        return _NoOpSpan()

    def start_as_current_span(self, *args, **kwargs):
        return _NoOpContextManager()


class _NoOpSpan:
    def end(self, *args, **kwargs):
        pass

    def set_attribute(self, *args, **kwargs):
        pass

    def set_status(self, *args, **kwargs):
        pass


class _NoOpContextManager:
    def __enter__(self):
        return _NoOpSpan()

    def __exit__(self, *args):
        pass
