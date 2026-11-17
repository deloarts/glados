"""
Evaluates one file's already-mapped field values (application.services.
pdm_variables.map_variables' output) and parsed processes
(pdm_variables.parse_processes) against AdminPdmSettings.required_fields,
the admin-configurable selection layered on top of the fixed locked set
in src.modules.external_data.domain.services.pdm_required_fields. Shared by
ValidatePdmPayload's dry run and IngestPdmFile's create/revise/claim
paths so the two can never disagree on what "required" means for a given
file; see this module's `missing_required_fields`.

`is_revision_required` is the other half of Rule 2's identity check
(part_number plus, conditionally, revision), also shared by both use
cases: it is not part of `missing_required_fields` because a missing
revision is checked separately from the rest of the required-field
catalogue (IngestPdmFile reports it as "identity variables missing";
ValidatePdmPayload folds it into its own pre-release `pending_pdm`
reporting instead, see `split_missing_required_fields`).

`split_missing_required_fields` is ValidatePdmPayload-only: pre-release,
a missing PDM-owned field (part_number, revision, or any other PDM-owned
field an admin has marked required) is not a reason, since the release
workflow assigns it rather than the engineer looking at the result. It
splits `missing_required_fields`' output into the reasons an engineer is
still held to and the PDM-owned field names still pending assignment.
IngestPdmFile never needs this split: it runs after release, when a
PDM-owned field is never legitimately missing, so it keeps calling
`missing_required_fields` directly.

Kept in the application layer rather than alongside the domain catalogue
because it takes parsed processes as `CreateMadeItemProcessCommand`
values, an application-layer DTO domain code must not import.
"""

from collections.abc import Mapping
from collections.abc import Sequence

from src.modules.catalogue.application.dto.made_item_dto import CreateMadeItemProcessCommand
from src.modules.catalogue.domain.policies.item_field_ownership import item_fields
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.external_data.domain.entities.admin_settings.pdm import AdminPdmSettings
from src.modules.external_data.domain.services.pdm_required_fields import LOCKED_REQUIRED_FIELDS
from src.modules.external_data.domain.services.pdm_required_fields import REQUIRED_FIELD_RULES


def _variable_map(kind: str, settings: AdminPdmSettings) -> Mapping[str, str]:
    return settings.made_item_variable_map if kind == "made" else settings.bought_item_variable_map


def _is_present(mapped: Mapping[str, str], field: str) -> bool:
    value = mapped.get(field)
    return bool(value and value.strip())


def _describe(field: str, variable_map: Mapping[str, str]) -> str:
    """A missing field's descriptor: bare when a PDM variable is mapped
    for it (the file simply left it blank), annotated when ingest could
    never have populated it in the first place."""
    if (variable_map.get(field) or "").strip():
        return field
    return f"{field} (no PDM variable mapped)"


def _has_fabrication_step(processes: Sequence[CreateMadeItemProcessCommand]) -> bool:
    return any(
        p.role == StepRole.FABRICATION.value and p.fabrication_method_id is not None
        for p in processes
    )


def is_revision_required(kind: str, settings: AdminPdmSettings) -> bool:
    """Whether ingest's Rule 2 identity check demands a non-empty
    revision for `kind`: always true for made items (`revision` is
    locked, part of their identity), true for bought items only when the
    admin's configurable selection names it (`revision` is data for a
    bought item, not part of its key, see docs/FIELD_OWNERSHIP.md
    principle 2). Shared by IngestPdmFile and ValidatePdmPayload so the
    two never disagree on it. A "revision" entry in the selection is
    already satisfied whenever this check passed, so
    missing_required_fields never needs to evaluate it again."""
    if kind == "made":
        return True
    return "revision" in settings.required_fields.get("bought", [])


def missing_required_fields(
    kind: str,
    mapped: Mapping[str, str],
    settings: AdminPdmSettings,
    processes: Sequence[CreateMadeItemProcessCommand] = (),
) -> list[str]:
    """Ordered list of missing-required-field descriptors: the locked
    fields first (src.modules.external_data.domain.services.pdm_required_fields.
    LOCKED_REQUIRED_FIELDS order), then the admin's configurable
    selection (item_fields() order), then pseudo-rules last. A field
    counts as present when its mapped value is non-empty after
    stripping; a pseudo-rule is evaluated on `processes` instead. Empty
    when nothing required is missing."""
    variable_map = _variable_map(kind, settings)
    selection = set(settings.required_fields.get(kind, []))
    field_order = {f.field: i for i, f in enumerate(item_fields()[kind])}

    missing: list[str] = [
        _describe(field, variable_map)
        for field in LOCKED_REQUIRED_FIELDS[kind]
        if not _is_present(mapped, field)
    ]

    rule_names = {rule.name for rule in REQUIRED_FIELD_RULES[kind]}
    configured_fields = sorted(
        (name for name in selection if name not in rule_names),
        key=lambda name: field_order.get(name, len(field_order)),
    )
    missing.extend(
        _describe(field, variable_map)
        for field in configured_fields
        if not _is_present(mapped, field)
    )

    for rule in REQUIRED_FIELD_RULES[kind]:
        if rule.name not in selection:
            continue
        if rule.name == "fabrication_step" and not _has_fabrication_step(processes):
            missing.append(rule.name)

    return missing


def format_missing_required_fields_reason(missing: Sequence[str]) -> str:
    """The shared wording IngestPdmFile's skip message and
    ValidatePdmPayload's reason both use."""
    return f"required fields missing: {', '.join(missing)}"


def split_missing_required_fields(kind: str, missing: Sequence[str]) -> tuple[list[str], list[str]]:
    """Splits missing_required_fields' output by field ownership
    (src.modules.catalogue.domain.policies.item_field_ownership.item_fields), for
    ValidatePdmPayload's pre-release dry run only; IngestPdmFile runs
    after release, when a PDM-owned field is never legitimately missing,
    so it has no use for this split and keeps calling
    missing_required_fields directly.

    A PDM-owned field (today part_number and revision, plus any other
    PDM-owned field an admin has marked required, e.g. a made item's
    revision_date/revision_note) is not something the engineer can fill
    in before release: the release workflow assigns it, not the caller.
    Returns (engineer_reasons, pending_pdm_fields); engineer_reasons keeps
    each entry's original descriptor, including a "(no PDM variable
    mapped)" annotation where present; pending_pdm_fields carries bare
    field names only, ordered the way item_fields() lists them for `kind`
    rather than missing's own locked-then-configured order. A pseudo-rule
    name (e.g. "fabrication_step") is never PDM-owned, so it always stays
    an engineer reason."""
    owners = {f.field: f.owner for f in item_fields()[kind]}
    order = {f.field: i for i, f in enumerate(item_fields()[kind])}
    engineer: list[str] = []
    pending: set[str] = set()
    for descriptor in missing:
        field = descriptor.split(" (", 1)[0]
        if owners.get(field) == "pdm":
            pending.add(field)
        else:
            engineer.append(descriptor)
    return engineer, sorted(pending, key=lambda f: order.get(f, len(order)))
