"""
The STEP, MESH and DXF validators every catalogue file family shares, so a
rule change lands in all of them at once.
"""

from src.modules.catalogue.application.use_cases.bought_item._file_kind import BOUGHT_ITEM_FILE_KIND
from src.modules.catalogue.application.use_cases.made_item._file_kind import MADE_ITEM_FILE_KIND
from src.modules.catalogue.application.use_cases.source_item._file_kind import SOURCE_ITEM_FILE_KIND
from src.modules.platform.application.services.file_attachments.config import DXF_VALIDATOR
from src.modules.platform.application.services.file_attachments.config import MESH_VALIDATOR
from src.modules.platform.application.services.file_attachments.config import STEP_VALIDATOR
from src.modules.platform.application.services.file_attachments.config import MiB
from src.modules.platform.domain.services.content_types import content_type_for


def test_item_file_validators_accept_the_documented_extensions() -> None:
    assert STEP_VALIDATOR.extensions == {".step", ".stp"}
    assert DXF_VALIDATOR.extensions == {".dxf"}
    assert MESH_VALIDATOR.extensions == {".stl", ".3mf"}
    assert {ext: content_type_for(ext) for ext in MESH_VALIDATOR.extensions} == {
        ".stl": "model/stl",
        ".3mf": "model/3mf",
    }
    assert MiB == 1024 * 1024


def test_item_file_families_share_one_validator_per_category() -> None:
    for kind in (BOUGHT_ITEM_FILE_KIND, MADE_ITEM_FILE_KIND, SOURCE_ITEM_FILE_KIND):
        validators = {category.name: v for category, v in kind.extra_validators.items()}
        assert validators["MESH"] is MESH_VALIDATOR
        assert validators.get("STEP", STEP_VALIDATOR) is STEP_VALIDATOR
        assert validators.get("DXF", DXF_VALIDATOR) is DXF_VALIDATOR
