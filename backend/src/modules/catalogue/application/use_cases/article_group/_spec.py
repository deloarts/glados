"""
Shared wiring for the article group CRUD use cases. See
src/modules/catalogue/application/services/labeled_entity_crud.py for the shared logic.
"""

from src.modules.catalogue.application.services.labeled_entity_crud import LabeledEntitySpec
from src.modules.catalogue.domain.entities.article_group import ArticleGroup
from src.modules.catalogue.domain.errors import ArticleGroupNotFoundError
from src.modules.catalogue.domain.services.article_group_rules import ArticleGroupRules

SPEC = LabeledEntitySpec(
    entity_cls=ArticleGroup,
    rules=ArticleGroupRules,
    not_found_error=ArticleGroupNotFoundError,
    label="article group",
    label_indefinite="An article group",
)
