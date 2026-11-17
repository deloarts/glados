"""
The invariant tying a routing step's role to its method ids, shared by the
made item processes and the lot steps. A fabrication step has only a
fabrication method and an inspection step only an inspection method, which
the database check constraints on both tables mirror. The callers differ
only in the error they raise and the noun their message uses.
"""

from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.platform.domain.exceptions import DomainError


def assert_role_matches_methods(
    role: str,
    fabrication_method_id: int | None,
    inspection_method_id: int | None,
    *,
    error: type[DomainError],
    noun: str,
) -> None:
    """Raises `error` when the method ids do not fit `role` or the role is
    unknown. `noun` names the step in the message, such as "process"."""
    if role == StepRole.FABRICATION:
        if fabrication_method_id is None:
            raise error(f"A fabrication-role {noun} requires a fabrication_method_id.")
        if inspection_method_id is not None:
            raise error(f"A fabrication-role {noun} must not have an inspection_method_id.")
    elif role == StepRole.INSPECTION:
        if fabrication_method_id is not None:
            raise error(f"An inspection-role {noun} must not have a fabrication_method_id.")
        if inspection_method_id is None:
            raise error(f"An inspection-role {noun} requires an inspection_method_id.")
    else:
        raise error(f"Unknown step role: {role!r}.")
