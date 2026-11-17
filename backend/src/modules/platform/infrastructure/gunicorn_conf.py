"""Gunicorn config module; gunicorn reads every module-level setting name.

child_exit runs in the master after a worker exits and deletes that worker's
multiprocess metrics files, or live gauges would keep its last value forever.
It only acts when PROMETHEUS_MULTIPROC_DIR is set.
"""

import os
from typing import Any

from prometheus_client import multiprocess

# Process and timeout settings, read by gunicorn as module-level names.
# GUNICORN_WORKERS sizes the process count per container; the database pool
# budget (DATABASE__POOL_SIZE + MAX_OVERFLOW per worker) scales with it.
workers = int(os.environ.get("GUNICORN_WORKERS", "4"))
# Time a worker gets after SIGTERM before gunicorn kills it. Above the
# worker's own 25s uvicorn graceful shutdown (gunicorn_worker.py), and below
# the container's stop_grace_period in docker-compose.yml.
graceful_timeout = 30
# Idle keep-alive between nginx and the backend.
keepalive = 5
# Gunicorn 25.1 and later open a control socket for gunicornc by default.
# Nothing here uses it, so it stays off rather than adding a management
# endpoint and a thread in the master.
control_socket_disable = True
# Peers whose X-Forwarded-For and X-Forwarded-Proto the server believes,
# comma-separated addresses or CIDR networks. Uvicorn then resolves
# request.client from the rightmost X-Forwarded-For entry that is not one of
# them; any other peer is the client itself. docker-compose.yml sets
# NETWORK__TRUSTED_PROXIES to the network the frontend's nginx connects from.
# Read here rather than from FORWARDED_ALLOW_IPS, so the trust has one
# documented name. Gunicorn refuses a malformed entry at start.
forwarded_allow_ips = os.environ.get("NETWORK__TRUSTED_PROXIES") or "127.0.0.1,::1"
# No max_requests: each worker also runs the in-process background jobs
# (event consumers, schedulers, auto-plan runs, backups), and recycling it
# after N requests would cut those off mid-run.


def child_exit(server: Any, worker: Any) -> None:
    if not os.environ.get("PROMETHEUS_MULTIPROC_DIR"):
        return
    # mark_process_dead ships without annotations even though the package
    # itself is py.typed, untyped rather than unresolvable; see values.py's own
    # equally unannotated get_value_class() for the same pattern upstream.
    multiprocess.mark_process_dead(worker.pid)  # type: ignore[no-untyped-call]
