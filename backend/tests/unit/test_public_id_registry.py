"""
Unit tests for the public_id resolver's registry
(src/modules/platform/adapters/outbound/persistence/public_id_lookup.py). No DB, pure
introspection of the registry mapping and the ORM classes it references.
"""

from sqlalchemy import inspect

from src.modules.platform.adapters.outbound.persistence.public_id_lookup import _REGISTRY
from src.modules.platform.ports.outbound.live_signal import LiveResource


def test_registry_is_not_empty():
    assert len(_REGISTRY) > 0


def test_registry_resource_values_are_unique():
    resources = list(_REGISTRY.values())
    assert len(resources) == len(set(resources)), "duplicate resource path segment in _REGISTRY"


def test_registry_resource_values_match_live_resource_vocabulary():
    known = {v for k, v in vars(LiveResource).items() if not k.startswith("_")}
    for resource in _REGISTRY.values():
        assert resource in known, f"{resource!r} is not declared on LiveResource"


def test_registry_models_have_id_and_public_id_columns():
    for model in _REGISTRY:
        columns = {c.name for c in inspect(model).columns}
        assert "id" in columns, f"{model.__name__} has no id column"
        assert "public_id" in columns, f"{model.__name__} has no public_id column"


def test_registry_models_are_distinct():
    models = list(_REGISTRY.keys())
    assert len(models) == len(set(models))
