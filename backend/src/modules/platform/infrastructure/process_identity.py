"""
Stable "which OS process is this" identity, used to tag rows so a hung or
crashed worker's aftermath is diagnosable (see backup_runs.worker). Prod
runs gunicorn with `-w 4` (docker-compose.yml), so a fixed name would tag
every worker the same; hostname+pid keeps them distinct and stays readable.

events/worker.py builds its per-consumer-group name inline as
`f"{group}-{socket.gethostname()}-{os.getpid()}"` rather than through this
helper.
"""

import os
import socket


def worker_identity() -> str:
    """hostname-pid: unique across gunicorn's worker processes, stable for
    the process's whole lifetime."""
    return f"{socket.gethostname()}-{os.getpid()}"
