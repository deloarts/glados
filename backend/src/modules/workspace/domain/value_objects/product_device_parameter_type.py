"""The value type of a technical parameter a device kind defines, which
decides how a device's value for it is entered and checked."""

from enum import unique

from src.shared_kernel.domain.value_objects.value_enum import StrValueEnum


@unique
class ProductDeviceParameterType(StrValueEnum):
    NUMBER = "number"
    TEXT = "text"
    BOOLEAN = "boolean"
