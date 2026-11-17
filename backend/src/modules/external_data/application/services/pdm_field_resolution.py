"""
Read-only field-resolution helpers shared between IngestPdmFile and
ValidatePdmPayload (the pre-release validation dry run, see
docs/reference/pdm-ingest.md section 8): both start from the same `mapped` dict
(pdm_variables.map_variables' output) and need to resolve a handful of
its values against the real catalogue before deciding anything: a
manufacturer id, an existing bought/made item a reference points at, the
article groups a comma-separated id list names, and whether the PDM file
at hand is already linked to an item under the OTHER kind. They live here
so the two use cases share exactly one implementation of each check, and
IngestPdmFile's methods delegate to them (its behaviour is covered by
tests/unit/ingest_pdm_file/).

`resolve_file_identity_from_path` is the one function here used only by
ValidatePdmPayload, not shared with IngestPdmFile: the PAT surface's own
input has no vault-issued file id at all, only the document's local path,
so it resolves one from the snapshot table before the shared checks above
can run against it.

Every function is read-only: no repository write method is called from
here, and nothing commits.
"""

from collections.abc import Awaitable
from collections.abc import Callable

from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.ports.outbound.cad_item_store_port import IBoughtItemCadStore
from src.modules.catalogue.ports.outbound.cad_item_store_port import IMadeItemCadStore
from src.modules.catalogue.ports.outbound.catalogue_queries import IArticleGroupQueries
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.external_data.application.services.pdm_variables import parse_int
from src.modules.external_data.application.services.pdm_variables import parse_int_list
from src.modules.external_data.domain.entities.pdm_file_snapshot import PdmFileSnapshot
from src.modules.external_data.ports.outbound.repositories.pdm_file_snapshot_repository import (
    IPdmFileSnapshotRepository,
)


async def resolve_manufacturer(
    mapped: dict[str, str], supplier_repo: ISupplierQueries
) -> tuple[int | None, bool]:
    """Returns (resolved id or None, unresolved). `unresolved` is True
    only when `manufacturer_id` WAS mapped and present but didn't resolve
    to a real supplier; an unmapped field is simply "nothing to
    update"/"nothing to check", never a problem on its own; the caller
    decides whether a resolved id is required for the action at hand."""
    if "manufacturer_id" not in mapped:
        return None, False
    candidate = parse_int(mapped["manufacturer_id"])
    if candidate is not None and await supplier_repo.get_by_id(candidate):
        return candidate, False
    return None, True


async def resolve_article_group_ids(
    mapped: dict[str, str], article_group_repo: IArticleGroupQueries
) -> tuple[list[int], str | None]:
    """The mapped `article_group_ids` value's comma-separated ids, minus
    any that don't resolve to a real article group; those are reported
    in the returned message (never raised) so a single stale id doesn't
    block the rest of the list."""
    if "article_group_ids" not in mapped:
        return [], None
    raw_ids = parse_int_list(mapped["article_group_ids"])
    if not raw_ids:
        return [], None
    found_ids = {g.id for g in await article_group_repo.get_by_ids(raw_ids)}
    unknown = [i for i in raw_ids if i not in found_ids]
    resolved = [i for i in raw_ids if i in found_ids]
    warning = f"Unknown article group id(s) {unknown} dropped." if unknown else None
    return resolved, warning


async def resolve_existing_id(
    mapped: dict[str, str], field: str, lookup: Callable[[int], Awaitable[object | None]]
) -> int | None:
    """The mapped `field` value as an id, but only when `lookup` (a
    repository's get_by_id) confirms a row with that id actually exists;
    an unmapped field, an unparsable value or a dangling reference all
    resolve to None alike."""
    if field not in mapped:
        return None
    candidate = parse_int(mapped[field])
    if candidate is None:
        return None
    return candidate if await lookup(candidate) is not None else None


async def find_other_kind_link(
    made_item_repo: IMadeItemCadStore,
    bought_item_repo: IBoughtItemCadStore,
    vault_id: str,
    file_id: int,
    kind: str,
) -> MadeItem | BoughtItem | None:
    """The item already linked to (vault_id, file_id) under the kind
    OTHER than `kind`, if any. Made and bought items key their link the
    same way ((vault_id, file_id)), so the same PDM file can never
    legitimately be linked under both. IngestPdmFile's kind-changed
    guard and ValidatePdmPayload's own consistency check both call this
    to detect that a file's resolved kind disagrees with an existing
    link."""
    if kind == "made":
        return await bought_item_repo.get_by_pdm_file(vault_id, file_id)
    family = await made_item_repo.get_family_by_pdm_file(vault_id, file_id)
    return family[0] if family else None


async def resolve_file_identity_from_path(
    snapshot_repo: IPdmFileSnapshotRepository, vault_id: str, file_path: str
) -> PdmFileSnapshot | None:
    """Resolves a PDM file's identity from its full local document path:
    the SolidWorks add-in's own on-disk path, drive letter and vault view
    root included (e.g. "C:\\DEMO-VAULT\\Engineering\\Glados\\
    CAD-1001.sldprt"), for ValidatePdmPayload's PAT surface, which has
    no vault-issued file id of its own, unlike the API-key surface which
    is handed one directly. Normalises separators and case, then delegates
    to IPdmFileSnapshotRepository.find_by_path_suffix, which matches a
    snapshot's own vault-relative path as a suffix of the normalised
    document path. Returns None for a blank path, no match, or an
    ambiguous match; see find_by_path_suffix's own docstring for the
    ambiguity rule."""
    normalized = file_path.strip().replace("/", "\\").lower()
    if not normalized:
        return None
    return await snapshot_repo.find_by_path_suffix(vault_id, normalized)
