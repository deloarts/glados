"""
Append-only audit row: one per print (auto or manual). No soft-delete/audit
block, since a job is immutable history, not an editable catalogue row.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintJobStatus
from src.modules.quality.domain.value_objects.print_classifier import PrintJobTrigger
from src.modules.quality.domain.value_objects.print_classifier import PrintRootType
from src.modules.quality.domain.value_objects.print_classifier import UploadedPrintDocument
from src.shared_kernel.domain.entities.base import Entity


@dataclass
class PrintJob(Entity):
    created: datetime

    template_id: int | None
    printer_id: int | None
    # A template classifier, or the document for a report the browser uploads.
    classifier: PrintClassifier | UploadedPrintDocument
    root_type: PrintRootType
    root_id: int
    copies: int
    status: PrintJobStatus
    error_message: str | None
    rendered_zpl: str | None
    document_bytes: int | None
    trigger: PrintJobTrigger
    source_event_id: str | None
    actor_id: int

    # ── Denormalized (read-only, populated by repository mapper) ──────
    actor_full_name: str = ""
