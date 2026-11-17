"""Converts between Printer domain entity and DTOs, including nested bought items."""

from src.modules.catalogue.application.mappers.bought_item_mapper import BoughtItemMapper
from src.modules.quality.application.dto.printer_dto import PrinterResult
from src.modules.quality.domain.entities.printer import Printer


class PrinterMapper:
    @staticmethod
    def to_result(entity: Printer) -> PrinterResult:
        return PrinterResult(
            id=entity.id,
            public_id=entity.public_id,
            created=entity.created,
            changed=entity.changed,
            archived=entity.archived,
            name=entity.name,
            internal_name=entity.internal_name,
            kind=entity.kind,
            host=entity.host,
            port=entity.port,
            timeout_seconds=entity.timeout_seconds,
            transport=entity.transport,
            ipp_uri_path=entity.ipp_uri_path,
            head_dpi=entity.head_dpi,
            format_convert_factor=entity.format_convert_factor,
            default_media=entity.default_media,
            location=entity.location,
            vendor=entity.vendor,
            model=entity.model,
            firmware=entity.firmware,
            bought_item_ids=entity.bought_item_ids,
            bought_items=[BoughtItemMapper.to_result(b) for b in entity.bought_items],
            enabled=entity.enabled,
            is_default=entity.is_default,
            note=entity.note,
            creator_id=entity.creator_id,
            creator_full_name=entity.creator_full_name,
            changed_by_id=entity.changed_by_id,
            changed_by_full_name=entity.changed_by.full_name if entity.changed_by else "",
            changes=entity.changes,
        )
