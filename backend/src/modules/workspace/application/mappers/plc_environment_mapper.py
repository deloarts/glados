"""Converts PlcEnvironment domain entities to DTOs."""

from src.modules.workspace.application.dto.plc_environment_dto import CharConversionDto
from src.modules.workspace.application.dto.plc_environment_dto import ExportColumnDto
from src.modules.workspace.application.dto.plc_environment_dto import PlcEnvironmentResult
from src.modules.workspace.domain.entities.plc_environment import PlcEnvironment


def to_result(environment: PlcEnvironment) -> PlcEnvironmentResult:
    return PlcEnvironmentResult(
        id=environment.id,
        public_id=environment.public_id,
        created=environment.created,
        changed=environment.changed,
        name=environment.name,
        is_default=environment.is_default,
        prefixes=environment.prefixes,
        max_tag_length=environment.max_tag_length,
        conversions=[
            CharConversionDto(source=c.source, target=c.target) for c in environment.conversions
        ],
        tag_table=environment.tag_table,
        safety_tag_table=environment.safety_tag_table,
        export_sheet=environment.export_sheet,
        export_columns=[
            ExportColumnDto(header=c.header, source=c.source, value=c.value)
            for c in environment.export_columns
        ],
        archived=environment.archived,
    )
