"""
A production machine's operational status, computed on read rather than
stored. See resolve_machine_status in production_machine_status_rules.py
for the precedence between an open downtime and the machine's active
production orders.
"""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ProductionMachineStatus(StrValueEnum):
    DOWN = "down"
    RUNNING = "running"
    PAUSED = "paused"
    IDLE = "idle"
