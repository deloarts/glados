"""Updates the EPLAN Data Portal settings. The base URL must be an https
address, enabling needs a token, the language must be supported and the
default article groups must exist. A changed token is audited without its
value; an empty token clears it, which also switches the lookups off."""

from dataclasses import replace

from src.modules.catalogue.domain.errors import ArticleGroupNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import IArticleGroupQueries
from src.modules.external_data.application.dto.admin_settings_dto.eplan_data_portal import (
    AdminEdpSettingsResult,
)
from src.modules.external_data.application.dto.admin_settings_dto.eplan_data_portal import (
    UpdateEdpSettingsCommand,
)
from src.modules.external_data.application.mappers.admin_settings_mapper.eplan_data_portal import (
    EdpSettingsMapper,
)
from src.modules.external_data.domain.entities.admin_settings.eplan_data_portal import (
    normalize_edp_base_url,
)
from src.modules.external_data.ports.outbound.external_data_settings_repository import (
    IExternalDataSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.audit import AdminSettingsAuditEntry
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.settings_rules import SettingsRules
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork


class UpdateEdpSettings:
    def __init__(
        self,
        repo: IExternalDataSettingsRepository,
        article_group_repo: IArticleGroupQueries,
        *,
        uow: IUnitOfWork,
    ) -> None:
        self._repo = repo
        self._article_groups = article_group_repo
        self._uow = uow

    async def execute(self, actor: User, cmd: UpdateEdpSettingsCommand) -> AdminEdpSettingsResult:
        SettingsRules.assert_can_write(actor)

        current = await self._repo.get_edp()
        pat = current.pat
        token_changed = False
        if cmd.pat is not None:
            pat = cmd.pat.strip() or None
            token_changed = pat != current.pat
        settings = replace(
            current,
            enabled=cmd.enabled if cmd.enabled is not None else current.enabled,
            base_url=(
                normalize_edp_base_url(cmd.base_url)
                if cmd.base_url is not None
                else current.base_url
            ),
            pat=pat,
            default_article_group_ids=(
                list(dict.fromkeys(cmd.default_article_group_ids))
                if cmd.default_article_group_ids is not None
                else current.default_article_group_ids
            ),
            language=cmd.language if cmd.language is not None else current.language,
        )
        if token_changed and settings.pat is None:
            settings.enabled = False
        settings.assert_valid()
        await self._assert_groups_exist(settings.default_article_group_ids)

        saved = await self._repo.save_edp(settings)
        summary = f"EPLAN Data Portal settings updated by {actor.username}."
        if token_changed:
            summary += " The personal access token was replaced."
        await self._repo.append_audit(
            AdminSettingsAuditEntry.by_actor(
                actor, settings_domain="eplan_data_portal", summary=summary
            )
        )
        await self._uow.commit()

        log.info("Updated EPLAN Data Portal settings.")
        return EdpSettingsMapper.edp_to_result(saved)

    async def _assert_groups_exist(self, ids: list[int]) -> None:
        if not ids:
            return
        found = {g.id for g in await self._article_groups.get_by_ids(ids) if not g.archived}
        missing = sorted(set(ids) - found)
        if missing:
            raise ArticleGroupNotFoundError(f"Article group(s) {missing} not found.")
