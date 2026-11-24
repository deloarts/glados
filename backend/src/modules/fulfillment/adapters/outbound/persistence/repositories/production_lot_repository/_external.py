"""The query behind the procurement list of external work: the open
positions of external work of the live lots, filtered, sorted by their
latest pickup and paged in SQL, so the list stays one query however many
lots there are."""

from datetime import date

from sqlalchemy import Select
from sqlalchemy import and_
from sqlalchemy import exists
from sqlalchemy import func
from sqlalchemy import or_
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql.elements import ColumnElement

from src.modules.catalogue.adapters.outbound.persistence.models.fabrication_method_model import (
    FabricationMethodOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.domain.value_objects.step_role import StepRole
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_model import (
    LotPositionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_position_provision_model import (
    LotPositionProvisionOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.lot_step_model import (
    LotStepOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.order_item_model import (
    OrderItemOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.models.production_lot_model import (
    ProductionLotOrmModel,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _date_in_range,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _external_work_position,
)
from src.modules.fulfillment.adapters.outbound.persistence.repositories.production_lot_repository._filters import (
    _live_lot,
)
from src.modules.fulfillment.domain.services.scheduling.external_work import ExternalWorkAlert
from src.modules.fulfillment.domain.services.scheduling.external_work import ExternalWorkStage
from src.modules.fulfillment.domain.value_objects.order_status import OrderItemStatus
from src.modules.fulfillment.ports.outbound.repositories.production_lot_repository import (
    ExternalWorkFilterDto,
)
from src.modules.platform.adapters.outbound.persistence.like_escape import contains_ci
from src.modules.platform.adapters.outbound.persistence.pagination import clamp_page
from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel

_lp = LotPositionOrmModel
_lot = ProductionLotOrmModel


def _live_line(*clauses: ColumnElement[bool]) -> ColumnElement[bool]:
    """The position has a live order line (not canceled, not closed short)
    meeting `clauses`."""
    oi = OrderItemOrmModel
    return exists().where(
        oi.lot_position_id == _lp.id,
        oi.canceled_at.is_(None),
        oi.closed_short_at.is_(None),
        *clauses,
    )


def _outsourced_step(*clauses: ColumnElement[bool]) -> ColumnElement[bool]:
    """The position has a fabrication step whose method is usually
    outsourced, meeting `clauses`."""
    return exists().where(
        LotStepOrmModel.position_id == _lp.id,
        LotStepOrmModel.role == StepRole.FABRICATION.value,
        LotStepOrmModel.fabrication_method_id == FabricationMethodOrmModel.id,
        FabricationMethodOrmModel.required_external.is_(True),
        *clauses,
    )


def _back_by() -> ColumnElement[date | None]:
    """The day the position is back: the supplier's date on its live line,
    else the latest delivery the walk counted, as the list shows it."""
    oi = OrderItemOrmModel
    supplier_date = (
        select(func.max(oi.expected_delivery_date))
        .where(
            oi.lot_position_id == _lp.id,
            oi.canceled_at.is_(None),
            oi.closed_short_at.is_(None),
        )
        .correlate(_lp)
        .scalar_subquery()
    )
    return func.coalesce(supplier_date, _lp.latest_delivery_date)


def _handed_over() -> ColumnElement[bool]:
    """Some pieces of the position went to the supplier already."""
    return exists().where(LotPositionProvisionOrmModel.lot_position_id == _lp.id)


def _line_status(status: OrderItemStatus) -> ColumnElement[bool]:
    return _live_line(OrderItemOrmModel.status == status.value)


def _stage(stage: str) -> ColumnElement[bool]:
    """Mirrors the list's stage of a row (externalWorkStage in the frontend):
    no line, then partly back, then handed over, then the line's status."""
    if stage == ExternalWorkStage.UNASSIGNED:
        return ~_live_line()
    if stage == ExternalWorkStage.PARTIALLY_BACK:
        return _line_status(OrderItemStatus.PARTIALLY_DELIVERED)
    partly_back = _line_status(OrderItemStatus.PARTIALLY_DELIVERED)
    if stage == ExternalWorkStage.AT_SUPPLIER:
        return and_(_live_line(), _handed_over(), ~partly_back)
    status = {
        ExternalWorkStage.PENDING: OrderItemStatus.PENDING,
        ExternalWorkStage.REQUESTED: OrderItemStatus.REQUESTED,
        ExternalWorkStage.ORDERED: OrderItemStatus.ORDERED,
    }[ExternalWorkStage(stage)]
    return and_(_line_status(status), ~_handed_over(), ~partly_back)


def _overdue(filters: ExternalWorkFilterDto) -> ColumnElement[bool]:
    return and_(
        _lp.latest_pickup_date.is_not(None),
        _lp.latest_pickup_date < filters.today,
        ~_handed_over(),
    )


def _alert(alert: str, filters: ExternalWorkFilterDto) -> ColumnElement[bool]:
    """Mirrors scheduling.external_work.external_work_alert: a missing
    latest pickup, then overdue, then not ready by the latest pickup."""
    if alert == ExternalWorkAlert.NO_TARGET_DATE:
        return _lp.latest_pickup_date.is_(None)
    if alert == ExternalWorkAlert.OVERDUE:
        return _overdue(filters)
    return and_(
        _lp.latest_pickup_date.is_not(None),
        _lp.planned_pickup_date > _lp.latest_pickup_date,
        ~_overdue(filters),
    )


def _critical(filters: ExternalWorkFilterDto) -> ColumnElement[bool]:
    """It cannot be ready by its latest pickup, or that day has passed
    while no piece was handed to the supplier yet."""
    return or_(
        _alert(ExternalWorkAlert.OVERDUE, filters),
        _alert(ExternalWorkAlert.NOT_READY_IN_TIME, filters),
    )


def _filtered(filters: ExternalWorkFilterDto) -> Select[tuple[int, int]]:
    query = (
        select(_lp.id, _lp.lot_id)
        .join(_lot, _lot.id == _lp.lot_id)
        .join(MadeItemOrmModel, MadeItemOrmModel.id == _lot.made_item_id)
        .join(ProjectOrmModel, ProjectOrmModel.id == _lot.project_id)
        .where(_live_lot(), _external_work_position(_lp))
    )
    if filters.only_with_supplier:
        query = query.where(_live_line())
    if filters.fabrication_method_id is not None:
        query = query.where(
            exists().where(
                LotStepOrmModel.position_id == _lp.id,
                LotStepOrmModel.fabrication_method_id == filters.fabrication_method_id,
            )
        )
    if filters.supplier_id is not None:
        query = query.where(
            or_(
                _live_line(OrderItemOrmModel.supplier_id == filters.supplier_id),
                and_(
                    ~_live_line(),
                    _outsourced_step(
                        FabricationMethodOrmModel.default_supplier_id == filters.supplier_id
                    ),
                ),
            )
        )
    if filters.part:
        query = query.where(
            or_(
                contains_ci(MadeItemOrmModel.part_number, filters.part),
                contains_ci(MadeItemOrmModel.article_name, filters.part),
            )
        )
    if filters.lot_ids:
        query = query.where(_lp.lot_id.in_(filters.lot_ids))
    if filters.project_ids:
        query = query.where(_lot.project_id.in_(filters.project_ids))
    if filters.product_ids:
        query = query.where(ProjectOrmModel.product_id.in_(filters.product_ids))
    if filters.back_by_from is not None or filters.back_by_to is not None:
        query = query.where(_date_in_range(_back_by(), filters.back_by_from, filters.back_by_to))
    if filters.stages:
        query = query.where(or_(*(_stage(stage) for stage in filters.stages)))
    if filters.alerts:
        query = query.where(or_(*(_alert(alert, filters) for alert in filters.alerts)))
    if filters.ready_from is not None or filters.ready_to is not None:
        query = query.where(
            _date_in_range(_lp.planned_pickup_date, filters.ready_from, filters.ready_to)
        )
    if filters.latest_pickup_from is not None or filters.latest_pickup_to is not None:
        query = query.where(
            _date_in_range(
                _lp.latest_pickup_date, filters.latest_pickup_from, filters.latest_pickup_to
            )
        )
    if filters.search:
        term = filters.search
        query = query.where(
            or_(
                contains_ci(_lot.lot_number, term),
                contains_ci(MadeItemOrmModel.part_number, term),
                contains_ci(MadeItemOrmModel.article_name, term),
                contains_ci(ProjectOrmModel.project_number, term),
            )
        )
    if filters.only_critical:
        query = query.where(_critical(filters))
    return query


async def external_work_page(
    db: AsyncSession, filters: ExternalWorkFilterDto
) -> tuple[int, list[tuple[int, int]]]:
    """The total and one page of (position id, lot id), latest pickup
    first, then the forecast pickup, undated rows last."""
    query = _filtered(filters)
    total = await db.scalar(select(func.count()).select_from(query.subquery())) or 0
    skip, limit = clamp_page(filters.skip, filters.limit)
    rows = await db.execute(
        query.order_by(
            _lp.latest_pickup_date.is_(None),
            _lp.latest_pickup_date,
            _lp.planned_pickup_date.is_(None),
            _lp.planned_pickup_date,
            _lp.id,
        )
        .offset(skip)
        .limit(limit)
    )
    return total, [(position_id, lot_id) for position_id, lot_id in rows.all()]
