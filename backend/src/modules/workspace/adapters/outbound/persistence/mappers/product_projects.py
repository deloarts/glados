"""
The ids of the projects built on a product, as a subquery for an `IN`
clause. The product detail page rolls up demands, orders and costs over all
of its projects, so every repository that offers a `product_id` filter next
to its `project_id` filter scopes it through this one subquery.
"""

from typing import Any

from sqlalchemy import ColumnElement
from sqlalchemy import Select
from sqlalchemy import select
from sqlalchemy.orm import QueryableAttribute

from src.modules.workspace.adapters.outbound.persistence.models.project_model import ProjectOrmModel


def project_ids_of_product(product_id: int) -> Select[tuple[int]]:
    """Selects the ids of the projects whose product_id is `product_id`.
    Soft-deleted projects are left out, so the rollup covers exactly the
    projects the product page lists."""
    return select(ProjectOrmModel.id).where(
        ProjectOrmModel.product_id == product_id, ProjectOrmModel.deleted.is_(False)
    )


def in_product_projects(column: QueryableAttribute[Any], product_id: int) -> ColumnElement[bool]:
    """True where the project id in `column` belongs to a project built on
    `product_id`."""
    return column.in_(project_ids_of_product(product_id))
