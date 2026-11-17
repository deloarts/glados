"""
Import every ORM model so Base.metadata is fully populated before
Alembic inspects it. Walking the models packages of every module (rather
than a hand-maintained import list) means a new model file is picked up
automatically, the previous hand list silently drifted out of sync with the
models package and caused autogenerate to propose dropping tables it didn't
know about. The packages are found on disk, so Platform names no module.
DDL ordering does not depend on import order: Alembic/SQLAlchemy
topologically sort by FK when emitting DDL.
"""

import importlib
import pkgutil
from pathlib import Path
from types import ModuleType

from src.modules.platform.adapters.outbound.persistence.models.base import Base  # noqa: F401

_SRC = Path(__file__).resolve().parents[5]


def _model_packages() -> list[ModuleType]:
    """The models package of every module, in module name order."""
    return [
        importlib.import_module(".".join(("src", *models.relative_to(_SRC).parts)))
        for models in sorted(_SRC.glob("modules/*/adapters/outbound/persistence/models"))
    ]


MODEL_PACKAGES = _model_packages()


def model_module_names() -> list[str]:
    """The dotted name of every model module, subpackages included."""
    return [
        info.name
        for package in MODEL_PACKAGES
        for info in pkgutil.walk_packages(package.__path__, package.__name__ + ".")
    ]


for _name in model_module_names():
    importlib.import_module(_name)
