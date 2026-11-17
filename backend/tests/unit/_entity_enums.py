"""
Finds the fields of a domain dataclass typed with a string enum, so a test
builder that fills the fields a test leaves out can pick a member for each.
An entity module may postpone its annotations and import some names for type
checking only, so each annotation is resolved on its own in the module of
the class that declares it, and one that cannot be resolved is skipped: such
a field is never a string enum.
"""

import dataclasses
import sys
import types
import typing
from enum import Enum
from typing import Any


def enum_fields(cls: type) -> dict[str, type[Enum]]:
    """The fields of `cls` typed with a string enum, optional or not, by name."""
    found: dict[str, type[Enum]] = {}
    for klass in reversed(cls.__mro__):
        own = vars(klass).get("__annotations__", {})
        module = sys.modules.get(klass.__module__)
        namespace = dict(vars(module)) if module is not None else {}
        for name, annotation in own.items():
            enum_type = _str_enum_of(_resolve(annotation, namespace))
            if enum_type is None:
                found.pop(name, None)
            else:
                found[name] = enum_type
    names = {f.name for f in dataclasses.fields(cls)}  # type: ignore[arg-type]
    return {name: enum_type for name, enum_type in found.items() if name in names}


def _resolve(annotation: Any, namespace: dict[str, Any]) -> Any:
    if not isinstance(annotation, str):
        return annotation
    try:
        return eval(annotation, namespace)
    except NameError:
        return None


def _str_enum_of(hint: Any) -> type[Enum] | None:
    if typing.get_origin(hint) in (types.UnionType, typing.Union):
        members = [arg for arg in typing.get_args(hint) if arg is not type(None)]
        return _str_enum_of(members[0]) if len(members) == 1 else None
    if isinstance(hint, type) and issubclass(hint, Enum) and issubclass(hint, str):
        return hint
    return None
