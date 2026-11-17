"""Use case factories: inspection checklists."""

from src.modules.quality.adapters.inbound.api.deps.controlled_documents import (
    build_controlled_document_deps,
)
from src.modules.quality.adapters.inbound.api.deps.controlled_documents import build_create_dep
from src.modules.quality.adapters.inbound.api.deps.controlled_documents import build_release_dep
from src.modules.quality.adapters.inbound.api.deps.controlled_documents import build_update_dep
from src.modules.quality.adapters.inbound.api.deps.repositories import get_checklist_repo
from src.modules.quality.application.use_cases.checklist.delete_checklist import DeleteChecklist
from src.modules.quality.application.use_cases.checklist.get_checklists import GetChecklist
from src.modules.quality.application.use_cases.checklist.get_checklists import (
    GetChecklistByPublicId,
)
from src.modules.quality.application.use_cases.checklist.get_checklists import GetChecklistRevisions
from src.modules.quality.application.use_cases.checklist.get_checklists import GetChecklists
from src.modules.quality.application.use_cases.checklist.lock_checklist import LockChecklist
from src.modules.quality.application.use_cases.checklist.lock_checklist import UnlockChecklist
from src.modules.quality.application.use_cases.checklist.release_checklist import (
    MarkChecklistInvalid,
)
from src.modules.quality.application.use_cases.checklist.release_checklist import ReleaseChecklist
from src.modules.quality.application.use_cases.checklist.revise_checklist import ReviseChecklist
from src.modules.quality.application.use_cases.checklist.save_checklist import CreateChecklist
from src.modules.quality.application.use_cases.checklist.save_checklist import UpdateChecklist

DEPS = build_controlled_document_deps(
    get_checklist_repo,
    get_many_cls=GetChecklists,
    get_one_cls=GetChecklist,
    get_revisions_cls=GetChecklistRevisions,
    get_by_public_id_cls=GetChecklistByPublicId,
    revise_cls=ReviseChecklist,
    mark_invalid_cls=MarkChecklistInvalid,
    delete_cls=DeleteChecklist,
    lock_cls=LockChecklist,
    unlock_cls=UnlockChecklist,
)

get_checklists_use_case = DEPS.get_many
get_checklist_use_case = DEPS.get_one
get_checklist_revisions_use_case = DEPS.get_revisions
get_checklist_by_public_id_use_case = DEPS.get_by_public_id
get_create_checklist_use_case = build_create_dep(get_checklist_repo, CreateChecklist)
get_update_checklist_use_case = build_update_dep(get_checklist_repo, UpdateChecklist)
get_revise_checklist_use_case = DEPS.revise
get_release_checklist_use_case = build_release_dep(get_checklist_repo, ReleaseChecklist)
get_mark_checklist_invalid_use_case = DEPS.mark_invalid
get_delete_checklist_use_case = DEPS.delete
get_lock_checklist_use_case = DEPS.lock
get_unlock_checklist_use_case = DEPS.unlock
