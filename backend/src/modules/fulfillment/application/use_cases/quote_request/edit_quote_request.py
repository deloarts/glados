"""
Creates quote requests and changes their lines, suppliers and offers.

Every writer locks the request row and reads it again under the lock, so
two users entering offers or lines one after the other never overwrite each
other. A writer that puts a line to work on a project (a new request or
line, a replacement line, a line taken back) share-locks that project
before the request and checks it is active, as every use case creating
work on a project does, so a project being completed or archived counts
the line or refuses it. Lines, suppliers and offers change while the request is DRAFT or
SENT. A change to the request's own note or deadline checks and moves its
edit version; a line, supplier or offer write is serialized by the lock and
takes no version, so two people can record the offers of two suppliers side
by side. After every write the change is noted in the request's changelog
and the lifecycle reconciler derives the request's status again. A dropped
line can also be taken back while the request is CLOSED only because every
line was dropped. A request someone closed is reopened when an award on it
was voided since, so the line that award left open can be awarded anew.

A line can be replaced for every supplier by a line for another item of
its kind, which takes over the demand shares and the reason; the replaced
line is dropped and names its replacement, and removing the replacement
asks for the replaced line again. One supplier's alternative item is part
of its offer.

None of these writes touches an order line or a demand: a demand share is
no allocation, so the reconciler derives nothing but the request, and no
lifecycle lock is taken besides the request's own, which comes last in the
lock order.
"""

from src.modules.catalogue.domain.errors import SupplierNotFoundError
from src.modules.catalogue.ports.outbound.catalogue_queries import ISupplierQueries
from src.modules.fulfillment.application.dto.quote_request_dto import AddQuoteRequestLinesCommand
from src.modules.fulfillment.application.dto.quote_request_dto import (
    AddQuoteRequestSuppliersCommand,
)
from src.modules.fulfillment.application.dto.quote_request_dto import CreateQuoteRequestCommand
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteInput
from src.modules.fulfillment.application.dto.quote_request_dto import QuoteRequestResult
from src.modules.fulfillment.application.dto.quote_request_dto import SaveOfferCommand
from src.modules.fulfillment.application.dto.quote_request_dto import (
    SubstituteQuoteRequestLineCommand,
)
from src.modules.fulfillment.application.dto.quote_request_dto import UpdateQuoteRequestCommand
from src.modules.fulfillment.application.dto.quote_request_dto import UpdateQuoteRequestLineCommand
from src.modules.fulfillment.application.mappers.quote_request_mapper import QuoteRequestMapper
from src.modules.fulfillment.application.services.lifecycle_reconciler import LifecycleReconciler
from src.modules.fulfillment.application.use_cases.quote_request._lines import LineRepositories
from src.modules.fulfillment.application.use_cases.quote_request._lines import build_line
from src.modules.fulfillment.application.use_cases.quote_request._lines import check_substitute_item
from src.modules.fulfillment.application.use_cases.quote_request._lines import line_project_ids
from src.modules.fulfillment.application.use_cases.quote_request._lines import next_position
from src.modules.fulfillment.domain.entities.quote_request import Quote
from src.modules.fulfillment.domain.entities.quote_request import QuoteExtraCost
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequest
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLine
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestLineDemand
from src.modules.fulfillment.domain.entities.quote_request import QuoteRequestSupplier
from src.modules.fulfillment.domain.errors import QuoteRequestInvalidError
from src.modules.fulfillment.domain.errors import QuoteRequestNotFoundError
from src.modules.fulfillment.domain.errors import QuoteRequestSupplierAlreadyAddedError
from src.modules.fulfillment.domain.errors import QuoteRequestSupplierInUseError
from src.modules.fulfillment.domain.services.extra_cost_rules import ExtraCostDraft
from src.modules.fulfillment.domain.services.extra_cost_rules import assert_valid_extra_costs
from src.modules.fulfillment.domain.services.extra_cost_rules import normalized_label
from src.modules.fulfillment.domain.services.lifecycle.quote_request import lines_restorable
from src.modules.fulfillment.domain.services.quote_request_rules import (
    allowed_quote_request_actions,
)
from src.modules.fulfillment.domain.services.quote_request_rules import (
    assert_can_write_quote_requests,
)
from src.modules.fulfillment.domain.services.quote_request_rules import assert_line_open
from src.modules.fulfillment.domain.services.quote_request_rules import assert_quote_request_action
from src.modules.fulfillment.domain.services.quote_request_rules import assert_quote_request_open
from src.modules.fulfillment.domain.services.quote_request_rules import assert_shares_fit
from src.modules.fulfillment.domain.services.quote_request_rules import find_line
from src.modules.fulfillment.domain.services.quote_request_rules import find_supplier_row
from src.modules.fulfillment.domain.services.quote_request_rules import line_item_id
from src.modules.fulfillment.domain.services.quote_request_rules import substitute_reason
from src.modules.fulfillment.domain.value_objects.order_status import OrderLineType
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestLineState
from src.modules.fulfillment.domain.value_objects.quote_request_status import QuoteRequestStatus
from src.modules.fulfillment.ports.outbound.fulfillment_settings_repository import (
    IFulfillmentSettingsRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_file_repository import (
    IQuoteRequestFileRepository,
)
from src.modules.fulfillment.ports.outbound.repositories.quote_request_repository import (
    IQuoteRequestRepository,
)
from src.modules.platform.application.services.lookup import found_or_raise
from src.modules.platform.application.services.storage_asset import (
    delete_storage_object_best_effort,
)
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.services.edit_version import assert_edit_version
from src.modules.platform.domain.services.edit_version import bump_edit_version
from src.modules.platform.domain.services.quantities import assert_whole_pieces
from src.modules.platform.infrastructure.logging.logger import log
from src.modules.platform.ports.outbound.storage_port import IStoragePort
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork
from src.modules.workspace.domain.errors import ProjectNotFoundError
from src.modules.workspace.domain.policies.project_activity import assert_project_active
from src.modules.workspace.ports.outbound.workspace_queries import IProjectQueries
from src.shared_kernel.domain.services.changelog_service import append_changelog
from src.shared_kernel.domain.services.clock import now_utc
from src.shared_kernel.domain.value_objects.lifecycle_action import LifecycleAction


class _QuoteRequestWriter:
    """The lock, the status refresh, the changelog and the commit every
    writer of a request shares."""

    def __init__(
        self,
        request_repo: IQuoteRequestRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        self._requests = request_repo
        self._uow = uow
        self._reconciler = reconciler

    async def _locked(self, request_id: int) -> QuoteRequest:
        return found_or_raise(
            await self._requests.get_by_id_for_update(request_id),
            QuoteRequestNotFoundError,
            f"Quote request #{request_id} not found.",
        )

    async def _share_lock_line_project(
        self, projects: IProjectQueries, request_id: int, line_id: int
    ) -> None:
        """Share-locks the project of an existing line before the request
        lock, for a writer that puts the line back to work on it. A line
        never changes its project, so the unlocked read names the right one."""
        request = found_or_raise(
            await self._requests.get_by_id(request_id),
            QuoteRequestNotFoundError,
            f"Quote request #{request_id} not found.",
        )
        line = request.line(line_id)
        if line is not None and line.project_id is not None:
            await projects.lock_for_share([line.project_id])

    async def _finish(
        self,
        actor: User,
        request_id: int,
        change: str,
        *,
        bump: bool = False,
        created: bool = False,
    ) -> QuoteRequestResult:
        """Notes `change` in the request's changelog, moves its edit version
        when `bump`, lets the reconciler derive the status of the request as
        written, and commits. `created` marks a request this transaction
        inserted."""
        request = found_or_raise(
            await self._requests.get_by_id(request_id),
            QuoteRequestNotFoundError,
            f"Quote request #{request_id} not found.",
        )
        now = now_utc()
        request.changes = append_changelog(request.changes, actor.full_name, change)
        request.changed = now
        if bump:
            bump_edit_version(request)
        await self._requests.save(request)
        self._reconciler.touch_quote_requests([request_id], created=created)
        await self._reconciler.run(actor, now, reason=change.rstrip("."))
        await self._uow.commit()
        saved = found_or_raise(
            await self._requests.get_by_id(request_id),
            QuoteRequestNotFoundError,
            f"Quote request #{request_id} not found.",
        )
        return QuoteRequestMapper.to_result(saved, allowed_quote_request_actions(saved, actor))


async def _assert_line_project_active(projects: IProjectQueries, line: QuoteRequestLine) -> None:
    if line.project_id is None:
        return
    assert_project_active(
        found_or_raise(
            await projects.get_by_id(line.project_id),
            ProjectNotFoundError,
            f"Project #{line.project_id} not found.",
        ),
        work="new quote request lines",
    )


async def _suppliers_exist(suppliers: ISupplierQueries, supplier_ids: list[int]) -> None:
    for supplier_id in supplier_ids:
        found_or_raise(
            await suppliers.get_by_id(supplier_id),
            SupplierNotFoundError,
            f"Supplier #{supplier_id} not found.",
        )


class CreateQuoteRequest(_QuoteRequestWriter):
    """Creates a request, optionally with its suppliers and lines, numbered
    from the configured quote request number format."""

    def __init__(
        self,
        request_repo: IQuoteRequestRepository,
        line_repos: LineRepositories,
        supplier_repo: ISupplierQueries,
        admin_settings_repo: IFulfillmentSettingsRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(request_repo, uow=uow, reconciler=reconciler)
        self._lines = line_repos
        self._suppliers = supplier_repo
        self._admin_settings = admin_settings_repo

    async def execute(self, actor: User, cmd: CreateQuoteRequestCommand) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        await self._lines.projects.lock_for_share(await line_project_ids(self._lines, cmd.lines))
        supplier_ids = list(dict.fromkeys(cmd.supplier_ids))
        await _suppliers_exist(self._suppliers, supplier_ids)

        now = now_utc()
        template = (await self._admin_settings.get_orders()).quote_request_number_format
        number = await self._requests.next_request_number(template)
        request = await self._requests.save(
            QuoteRequest(
                id=0,
                request_number=number,
                created=now,
                changed=now,
                changes=[],
                status=QuoteRequestStatus.default(),
                creator_id=actor.id,
                note=(cmd.note or "").strip() or None,
                deadline=cmd.deadline,
            )
        )
        for position, supplier_id in enumerate(supplier_ids, start=1):
            await self._requests.save_supplier(
                QuoteRequestSupplier(
                    id=0, quote_request_id=request.id, supplier_id=supplier_id, position=position
                )
            )
        for position, data in enumerate(cmd.lines, start=1):
            line = await build_line(
                self._lines, data, request_id=request.id, position=position, now_at=now
            )
            await self._requests.save_line(line)
        log.info(f"Created quote request {number!r}, ID={request.id}.")
        return await self._finish(
            actor, request.id, f"Quote request {number} created.", created=True
        )


class AddQuoteRequestLines(_QuoteRequestWriter):
    def __init__(
        self,
        request_repo: IQuoteRequestRepository,
        line_repos: LineRepositories,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(request_repo, uow=uow, reconciler=reconciler)
        self._lines = line_repos

    async def execute(
        self, actor: User, request_id: int, cmd: AddQuoteRequestLinesCommand
    ) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        await self._lines.projects.lock_for_share(await line_project_ids(self._lines, cmd.lines))
        request = await self._locked(request_id)
        assert_quote_request_open(request)
        now = now_utc()
        position = next_position(request.lines)
        for offset, data in enumerate(cmd.lines):
            line = await build_line(
                self._lines, data, request_id=request.id, position=position + offset, now_at=now
            )
            await self._requests.save_line(line)
        count = len(cmd.lines)
        return await self._finish(
            actor, request.id, f"{count} line{'s' if count != 1 else ''} added."
        )


class UpdateQuoteRequest(_QuoteRequestWriter):
    async def execute(
        self, actor: User, request_id: int, cmd: UpdateQuoteRequestCommand
    ) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        request = await self._locked(request_id)
        assert_quote_request_open(request)
        assert_edit_version(
            request, cmd.expected_edit_version, what=f"Quote request {request.request_number}"
        )
        provided = cmd.model_fields_set
        if "note" in provided:
            request.note = (cmd.note or "").strip() or None
        if "deadline" in provided:
            request.deadline = cmd.deadline
        await self._requests.save(request)
        return await self._finish(actor, request.id, "Note or deadline changed.", bump=True)


class UpdateQuoteRequestLine(_QuoteRequestWriter):
    async def execute(
        self, actor: User, request_id: int, line_id: int, cmd: UpdateQuoteRequestLineCommand
    ) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        request = await self._locked(request_id)
        assert_quote_request_open(request)
        line = find_line(request, line_id)
        assert_line_open(line)
        provided = cmd.model_fields_set
        if "quantity" in provided and cmd.quantity is not None:
            counted = None if line.line_type == OrderLineType.MADE else line.unit
            assert_whole_pieces(cmd.quantity, what="The quote request line quantity", unit=counted)
            assert_shares_fit(cmd.quantity, (d.quantity for d in line.demands))
            line.quantity = cmd.quantity
        if "note" in provided:
            line.note = (cmd.note or "").strip() or None
        await self._requests.save_line(line)
        return await self._finish(actor, request.id, f"Line {line.position} changed.")


def _copied_shares(line: QuoteRequestLine) -> list[QuoteRequestLineDemand]:
    return [
        QuoteRequestLineDemand(
            id=0, line_id=0, family=d.family, demand_item_id=d.demand_item_id, quantity=d.quantity
        )
        for d in line.demands
    ]


class RemoveQuoteRequestLine(_QuoteRequestWriter):
    """Removes an open line with its offers. Removing a line that replaced
    another asks for the replaced line again, with the demand shares."""

    async def execute(self, actor: User, request_id: int, line_id: int) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        request = await self._locked(request_id)
        assert_quote_request_open(request)
        line = find_line(request, line_id)
        assert_line_open(line)
        replaced = next((r for r in request.lines if r.substituted_by_line_id == line.id), None)
        await self._requests.delete_line(line.id)
        if replaced is None:
            return await self._finish(actor, request.id, f"Line {line.position} removed.")
        replaced.demands = _copied_shares(line)
        replaced.dropped_at = None
        replaced.substituted_by_line_id = None
        await self._requests.save_line(replaced)
        return await self._finish(
            actor,
            request.id,
            f"Line {line.position} removed; line {replaced.position} is asked for again.",
        )


class SubstituteQuoteRequestLine(_QuoteRequestWriter):
    """Replaces an open line for every supplier with a line for another item
    of its kind. The new line comes last, with the old line's quantity,
    unit, project, note and demand shares and the reason, if given; the old
    line is
    dropped and names it, so what was asked first stays on the request. A
    supplier already asked has not been asked for the new line, so the
    request goes out to it again."""

    def __init__(
        self,
        request_repo: IQuoteRequestRepository,
        line_repos: LineRepositories,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(request_repo, uow=uow, reconciler=reconciler)
        self._lines = line_repos

    async def execute(
        self,
        actor: User,
        request_id: int,
        line_id: int,
        cmd: SubstituteQuoteRequestLineCommand,
    ) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        await self._share_lock_line_project(self._lines.projects, request_id, line_id)
        request = await self._locked(request_id)
        assert_quote_request_open(request)
        line = find_line(request, line_id)
        assert_line_open(line)
        # Asking the suppliers for another item is new work on the project.
        await _assert_line_project_active(self._lines.projects, line)
        item_id = await check_substitute_item(
            self._lines, line, cmd.bought_item_id, cmd.source_item_id
        )
        if item_id == line_item_id(line):
            raise QuoteRequestInvalidError(f"Line {line.position} already asks for this item.")
        reason = substitute_reason(cmd.reason)
        now = now_utc()
        bought = line.line_type == OrderLineType.BOUGHT
        replacement = QuoteRequestLine(
            id=0,
            quote_request_id=request.id,
            position=next_position(request.lines),
            line_type=line.line_type,
            quantity=line.quantity,
            unit=line.unit,
            created=now,
            project_id=line.project_id,
            bought_item_id=item_id if bought else None,
            source_item_id=None if bought else item_id,
            note=line.note,
            substitute_reason=reason,
            demands=_copied_shares(line),
        )
        # The shares leave the old line before the new one takes them.
        line.demands = []
        line.dropped_at = now
        await self._requests.save_line(line)
        saved = await self._requests.save_line(replacement)
        line.substituted_by_line_id = saved.id
        await self._requests.save_line(line)
        because = f": {reason}" if reason else ""
        return await self._finish(
            actor,
            request.id,
            f"Line {line.position} replaced by line {saved.position} ({saved.item_name}){because}.",
        )


class DropQuoteRequestLine(_QuoteRequestWriter):
    """Gives a line to nobody, or takes that back while the request is open
    or CLOSED only because every line was dropped; an awarded line cannot be
    dropped, and a replaced line comes back only by removing its
    replacement. Taking a line back puts it to work on its project again,
    so the project must be active then; dropping it only cleans up.
    """

    def __init__(
        self,
        request_repo: IQuoteRequestRepository,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
        project_repo: IProjectQueries,
    ) -> None:
        super().__init__(request_repo, uow=uow, reconciler=reconciler)
        self._projects = project_repo

    async def execute(
        self, actor: User, request_id: int, line_id: int, *, dropped: bool
    ) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        if not dropped:
            await self._share_lock_line_project(self._projects, request_id, line_id)
        request = await self._locked(request_id)
        if dropped or not lines_restorable(request):
            assert_quote_request_open(request)
        line = find_line(request, line_id)
        if dropped:
            assert_line_open(line)
            line.dropped_at = now_utc()
        else:
            if line.state is not QuoteRequestLineState.DROPPED:
                raise QuoteRequestInvalidError(f"Line #{line.id} was not dropped.")
            if line.substituted_by_line_id is not None:
                replacement = request.line(line.substituted_by_line_id)
                raise QuoteRequestInvalidError(
                    f"Line {line.position} was replaced by line "
                    f"{replacement.position if replacement else line.substituted_by_line_id}; "
                    "remove that line to ask for this one again."
                )
            await _assert_line_project_active(self._projects, line)
            line.dropped_at = None
        await self._requests.save_line(line)
        verb = "dropped" if dropped else "taken back"
        return await self._finish(actor, request.id, f"Line {line.position} {verb}.")


class AddQuoteRequestSuppliers(_QuoteRequestWriter):
    def __init__(
        self,
        request_repo: IQuoteRequestRepository,
        supplier_repo: ISupplierQueries,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(request_repo, uow=uow, reconciler=reconciler)
        self._suppliers = supplier_repo

    async def execute(
        self, actor: User, request_id: int, cmd: AddQuoteRequestSuppliersCommand
    ) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        request = await self._locked(request_id)
        assert_quote_request_open(request)
        supplier_ids = list(dict.fromkeys(cmd.supplier_ids))
        present = {row.supplier_id for row in request.suppliers}
        clash = [s for s in supplier_ids if s in present]
        if clash:
            raise QuoteRequestSupplierAlreadyAddedError(
                f"Supplier #{clash[0]} is already on quote request {request.request_number}."
            )
        await _suppliers_exist(self._suppliers, supplier_ids)
        position = max((row.position for row in request.suppliers), default=0)
        names = []
        for offset, supplier_id in enumerate(supplier_ids, start=1):
            saved = await self._requests.save_supplier(
                QuoteRequestSupplier(
                    id=0,
                    quote_request_id=request.id,
                    supplier_id=supplier_id,
                    position=position + offset,
                )
            )
            names.append(saved.supplier_name)
        return await self._finish(actor, request.id, f"Suppliers added: {', '.join(names)}.")


class RemoveQuoteRequestSupplier(_QuoteRequestWriter):
    """Removes a supplier with its offer and its documents, unless it won a
    line. The stored documents are deleted once the removal committed."""

    def __init__(
        self,
        request_repo: IQuoteRequestRepository,
        file_repo: IQuoteRequestFileRepository,
        storage: IStoragePort | None,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(request_repo, uow=uow, reconciler=reconciler)
        self._files = file_repo
        self._storage = storage

    async def execute(self, actor: User, request_id: int, row_id: int) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        request = await self._locked(request_id)
        assert_quote_request_open(request)
        row = find_supplier_row(request, row_id)
        if any(
            line.awarded_supplier_id == row.id and line.state is QuoteRequestLineState.AWARDED
            for line in request.lines
        ):
            raise QuoteRequestSupplierInUseError(
                f"{row.supplier_name} won a line of quote request {request.request_number} "
                "and stays on it."
            )
        files = await self._files.get_by_item_id(row.id)
        for file in files:
            await self._files.delete(file)
        await self._requests.delete_supplier(row.id)
        result = await self._finish(actor, request.id, f"Supplier {row.supplier_name} removed.")
        if self._storage is not None:
            for file in files:
                await delete_storage_object_best_effort(
                    self._storage,
                    file.storage_path,
                    context=f"removing supplier entry #{row.id} of {request.request_number}",
                )
        return result


class MarkQuoteRequestSupplierSent(_QuoteRequestWriter):
    """Records that the request went out to one supplier, by mail or any
    other way; every open line counts as asked of the supplier from then."""

    async def execute(self, actor: User, request_id: int, row_id: int) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        request = await self._locked(request_id)
        assert_quote_request_action(LifecycleAction.SEND, request, actor)
        row = find_supplier_row(request, row_id)
        row.sent_at = now_utc()
        await self._requests.save_supplier(row)
        return await self._finish(actor, request.id, f"Sent to {row.supplier_name}.")


class SaveOffer(_QuoteRequestWriter):
    """Records a supplier's offer as a whole: a unit price or "no offer" per
    line, with lead time, minimum quantity and an alternative item, the
    extra costs of the offer, its validity and whether the supplier declined
    to quote. An alternative is checked like a line's item, unless it is the
    one already recorded, and its reason is optional; one naming the line's
    own item is no alternative."""

    def __init__(
        self,
        request_repo: IQuoteRequestRepository,
        line_repos: LineRepositories,
        *,
        uow: IUnitOfWork,
        reconciler: LifecycleReconciler,
    ) -> None:
        super().__init__(request_repo, uow=uow, reconciler=reconciler)
        self._lines = line_repos

    async def _alternative(
        self, request: QuoteRequest, row: QuoteRequestSupplier, quote: QuoteInput
    ) -> tuple[int | None, int | None, str | None]:
        """The alternative item of `quote` as recorded: the bought item, the
        source item and the reason, or all None."""
        if quote.no_offer or (
            quote.substitute_bought_item_id is None and quote.substitute_source_item_id is None
        ):
            return None, None, None
        line = find_line(request, quote.line_id)
        named = (quote.substitute_bought_item_id, quote.substitute_source_item_id)
        recorded = row.quote_for(line.id)
        if (
            recorded is None
            or (
                recorded.substitute_bought_item_id,
                recorded.substitute_source_item_id,
            )
            != named
        ):
            item_id = await check_substitute_item(self._lines, line, *named)
            if item_id == line_item_id(line):
                return None, None, None
        return *named, substitute_reason(quote.substitute_reason)

    async def execute(
        self, actor: User, request_id: int, row_id: int, cmd: SaveOfferCommand
    ) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        request = await self._locked(request_id)
        assert_quote_request_open(request)
        row = find_supplier_row(request, row_id)
        line_ids = {line.id for line in request.lines}
        seen: set[int] = set()
        for quote in cmd.quotes:
            if quote.line_id not in line_ids:
                raise QuoteRequestInvalidError(
                    f"Line #{quote.line_id} is not on quote request {request.request_number}."
                )
            if quote.line_id in seen:
                raise QuoteRequestInvalidError("An offer names each line once.")
            seen.add(quote.line_id)
        drafts = [
            ExtraCostDraft(
                kind=c.kind,
                amount=c.amount,
                label=normalized_label(c.label),
                note=(c.note or "").strip() or None,
                line_id=c.line_id,
            )
            for c in cmd.extra_costs
        ]
        assert_valid_extra_costs(drafts, line_ids)

        quotes: list[Quote] = []
        for q in cmd.quotes:
            bought, source, reason = await self._alternative(request, row, q)
            alternative = bought is not None or source is not None
            if not (
                q.no_offer
                or q.unit_price is not None
                or q.note
                or q.lead_time_days is not None
                or alternative
            ):
                continue
            quotes.append(
                Quote(
                    id=0,
                    supplier_row_id=row.id,
                    line_id=q.line_id,
                    unit_price=None if q.no_offer else q.unit_price,
                    no_offer=q.no_offer,
                    lead_time_days=q.lead_time_days,
                    min_quantity=q.min_quantity,
                    note=(q.note or "").strip() or None,
                    substitute_bought_item_id=bought,
                    substitute_source_item_id=source,
                    substitute_reason=reason,
                )
            )
        costs = [
            QuoteExtraCost(
                id=0,
                supplier_row_id=row.id,
                kind=d.kind,
                amount=d.amount,
                position=position,
                label=d.label,
                note=d.note,
                line_id=d.line_id,
            )
            for position, d in enumerate(drafts, start=1)
        ]
        await self._requests.set_offer(row.id, quotes, costs)
        now = now_utc()
        if quotes or costs:
            row.responded_at = row.responded_at or now
        row.declined_at = (row.declined_at or now) if cmd.declined else None
        row.valid_until = cmd.valid_until
        row.note = (cmd.note or "").strip() or None
        await self._requests.save_supplier(row)
        return await self._finish(actor, request.id, f"Offer of {row.supplier_name} recorded.")


class EndQuoteRequest(_QuoteRequestWriter):
    """Closes a request once a line was awarded, dropping the lines still
    open, or cancels one that awarded nothing. Both are irreversible and
    check the edit version."""

    async def execute(
        self,
        actor: User,
        request_id: int,
        action: LifecycleAction,
        expected_edit_version: int | None,
    ) -> QuoteRequestResult:
        if action not in (LifecycleAction.CLOSE, LifecycleAction.CANCEL):
            raise ValueError(f"{action.value} does not end a quote request.")
        assert_can_write_quote_requests(actor)
        request = await self._locked(request_id)
        assert_quote_request_action(action, request, actor)
        assert_edit_version(
            request, expected_edit_version, what=f"Quote request {request.request_number}"
        )
        now = now_utc()
        if action is LifecycleAction.CLOSE:
            for line in request.lines:
                if line.state is QuoteRequestLineState.OPEN:
                    line.dropped_at = now
                    await self._requests.save_line(line)
            request.closed_at = now
        else:
            request.canceled_at = now
        await self._requests.save(request)
        verb = "closed" if action is LifecycleAction.CLOSE else "canceled"
        return await self._finish(actor, request.id, f"Quote request {verb}.", bump=True)


class ReopenQuoteRequest(_QuoteRequestWriter):
    """Clears the close of a request on which an award was voided after the
    close, so the line it left open can be awarded again. The status is
    derived again from the lines, SENT or DRAFT with the open line; the
    offers stay and the lines the close dropped stay dropped, to be taken
    back while the request is open. Checks the edit version like the close
    it undoes."""

    async def execute(
        self, actor: User, request_id: int, expected_edit_version: int | None
    ) -> QuoteRequestResult:
        assert_can_write_quote_requests(actor)
        request = await self._locked(request_id)
        assert_quote_request_action(LifecycleAction.REOPEN, request, actor)
        assert_edit_version(
            request, expected_edit_version, what=f"Quote request {request.request_number}"
        )
        request.closed_at = None
        await self._requests.save(request)
        return await self._finish(actor, request.id, "Quote request reopened.", bump=True)
