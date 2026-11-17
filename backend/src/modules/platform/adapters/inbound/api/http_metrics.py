"""
The HTTP request metrics and the live connection gauge that GET /metrics
publishes next to the application state gauges of metrics.py. They hold no
module's state, so Platform code such as the live hub can update them.
"""

from fastapi import FastAPI
from prometheus_client import Gauge
from prometheus_fastapi_instrumentator import Instrumentator
from prometheus_fastapi_instrumentator.metrics import default as default_http_metrics

# Probes, scrapes and the long-lived SSE stream are not latency data.
_EXCLUDED_HANDLERS = [r"^/health$", r"^/ready$", r"^/metrics$", r"^/api/v1/web/live"]

# "livesum" sums the live workers' counts and drops a dead worker's value.
LIVE_CONNECTIONS = Gauge(
    "glados_live_connections",
    "Live-sync SSE connections currently held open, summed across worker processes.",
    multiprocess_mode="livesum",
)


def instrument(app: FastAPI) -> None:
    """Wires the HTTP metrics middleware onto `app`, once, before routers.
    It never calls `.expose()`, because this module owns /metrics. The
    explicit `.add()` is required, or nothing is recorded.
    """
    instrumentator = Instrumentator(
        should_instrument_requests_inprogress=True,
        should_group_status_codes=False,
        excluded_handlers=_EXCLUDED_HANDLERS,
    )
    instrumentator.add(default_http_metrics())
    instrumentator.instrument(app)
