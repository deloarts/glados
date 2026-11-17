"""
How a PLC environment is checked when it is saved. Who may change it is
the rule of the device resources (ProductDeviceResourceRules). No I/O.
"""

from src.modules.workspace.domain.entities.plc_environment import PlcEnvironment
from src.modules.workspace.domain.errors import PlcEnvironmentInvalidError
from src.modules.workspace.domain.value_objects.plc_environment_settings import PREFIX_KEYS
from src.modules.workspace.domain.value_objects.plc_environment_settings import CharConversion
from src.modules.workspace.domain.value_objects.plc_environment_settings import ExportColumn
from src.modules.workspace.domain.value_objects.plc_environment_settings import ExportColumnSource

NAME_MAX_LENGTH = 100
PREFIX_MAX_LENGTH = 20
TABLE_MAX_LENGTH = 100
HEADER_MAX_LENGTH = 100
VALUE_MAX_LENGTH = 200
CONVERSION_MAX_LENGTH = 10
MAX_CONVERSIONS = 200
MAX_COLUMNS = 50
TAG_LENGTH_RANGE = range(8, 1025)


def _text(value: str, what: str, max_length: int, *, required: bool) -> str:
    cleaned = value.strip()
    if required and not cleaned:
        raise PlcEnvironmentInvalidError(f"The {what} must not be empty.")
    if len(cleaned) > max_length:
        raise PlcEnvironmentInvalidError(f"The {what} is longer than {max_length} characters.")
    return cleaned


def clean_name(name: str) -> str:
    return _text(" ".join(name.split()), "name", NAME_MAX_LENGTH, required=True)


def clean_prefixes(prefixes: dict[str, str]) -> dict[str, str]:
    """Every prefix key with its prefix, missing keys as an empty prefix.
    Prefixes are kept as typed, since a trailing underscore belongs to them."""
    unknown = sorted(set(prefixes) - set(PREFIX_KEYS))
    if unknown:
        raise PlcEnvironmentInvalidError(f"Unknown prefix keys: {', '.join(unknown)}.")
    result: dict[str, str] = {}
    for key in PREFIX_KEYS:
        value = prefixes.get(key, "")
        if len(value) > PREFIX_MAX_LENGTH or value != value.strip():
            raise PlcEnvironmentInvalidError(
                f"The {key} prefix has spaces at an end or is longer than "
                f"{PREFIX_MAX_LENGTH} characters."
            )
        result[key] = value
    return result


def check_tag_length(length: int) -> int:
    if length not in TAG_LENGTH_RANGE:
        raise PlcEnvironmentInvalidError(
            f"The tag length must lie between {TAG_LENGTH_RANGE.start} and "
            f"{TAG_LENGTH_RANGE.stop - 1}."
        )
    return length


def clean_conversions(conversions: list[CharConversion]) -> list[CharConversion]:
    if len(conversions) > MAX_CONVERSIONS:
        raise PlcEnvironmentInvalidError(f"At most {MAX_CONVERSIONS} conversions.")
    seen: set[str] = set()
    for conversion in conversions:
        if not conversion.source or len(conversion.source) > CONVERSION_MAX_LENGTH:
            raise PlcEnvironmentInvalidError(
                f"A conversion needs a source of 1 to {CONVERSION_MAX_LENGTH} characters."
            )
        if len(conversion.target) > CONVERSION_MAX_LENGTH:
            raise PlcEnvironmentInvalidError(
                f"A conversion target is longer than {CONVERSION_MAX_LENGTH} characters."
            )
        if conversion.source in seen:
            raise PlcEnvironmentInvalidError(f"{conversion.source!r} is converted twice.")
        seen.add(conversion.source)
    return list(conversions)


def clean_columns(columns: list[ExportColumn]) -> list[ExportColumn]:
    if not columns:
        raise PlcEnvironmentInvalidError("The export needs at least one column.")
    if len(columns) > MAX_COLUMNS:
        raise PlcEnvironmentInvalidError(f"At most {MAX_COLUMNS} export columns.")
    result: list[ExportColumn] = []
    for column in columns:
        header = _text(column.header, "column header", HEADER_MAX_LENGTH, required=True)
        value = None
        if column.source == ExportColumnSource.CONSTANT:
            value = _text(column.value or "", "column value", VALUE_MAX_LENGTH, required=False)
        result.append(ExportColumn(header=header, source=column.source, value=value))
    return result


def apply_settings(
    environment: PlcEnvironment,
    *,
    name: str,
    prefixes: dict[str, str],
    max_tag_length: int,
    conversions: list[CharConversion],
    tag_table: str,
    safety_tag_table: str | None,
    export_sheet: str,
    export_columns: list[ExportColumn],
) -> None:
    """Checks the settings and writes them onto `environment`."""
    environment.name = clean_name(name)
    environment.prefixes = clean_prefixes(prefixes)
    environment.max_tag_length = check_tag_length(max_tag_length)
    environment.conversions = clean_conversions(conversions)
    environment.tag_table = _text(tag_table, "tag table", TABLE_MAX_LENGTH, required=True)
    safety = _text(safety_tag_table or "", "safety tag table", TABLE_MAX_LENGTH, required=False)
    environment.safety_tag_table = safety or None
    environment.export_sheet = _text(export_sheet, "export sheet", TABLE_MAX_LENGTH, required=True)
    environment.export_columns = clean_columns(export_columns)
