"""
Request validation of LotFilterParams, the HTTP schema of the lot list
filters: the parameters that exclude each other and the min/max range
bounds, each rejected with a 422 rather than resolved on the server.
"""

import pytest
from pydantic import ValidationError

from src.modules.fulfillment.adapters.inbound.api.schemas.production_lot_schema import (
    LotFilterParams,
)


class TestCoverableByFilterParamsMutualExclusivity:
    """LotFilterParams (the HTTP-layer schema) rejects a request that sets
    more than one of the three coverable_by_* params: a 422 beats a
    confusing "which one wins" server-side choice."""

    def test_rejects_machine_and_pool_together(self):
        with pytest.raises(ValidationError):
            LotFilterParams(coverable_by_machine_id=1, coverable_by_pool_id=2)

    def test_rejects_machine_and_any_pool_together(self):
        with pytest.raises(ValidationError):
            LotFilterParams(coverable_by_machine_id=1, coverable_by_any_pool=True)

    def test_allows_exactly_one(self):
        assert LotFilterParams(coverable_by_machine_id=1).coverable_by_machine_id == 1  # no raise
        assert LotFilterParams(coverable_by_pool_id=1).coverable_by_pool_id == 1  # no raise
        assert LotFilterParams(coverable_by_any_pool=True).coverable_by_any_pool is True  # no raise


class TestLotFilterParamsStepMethodMutualExclusivity:
    """A step filter names one method: the frontend encodes the grouped
    Select as either a fabrication or an inspection id, never both."""

    def test_rejects_fabrication_and_inspection_method_together(self):
        with pytest.raises(ValidationError):
            LotFilterParams(step_fabrication_method_id=1, step_inspection_method_id=2)

    def test_allows_either_alone(self):
        fabrication = LotFilterParams(step_fabrication_method_id=1)  # no raise
        inspection = LotFilterParams(step_inspection_method_id=1)  # no raise

        assert fabrication.step_fabrication_method_id == 1
        assert inspection.step_inspection_method_id == 1


class TestLotFilterParamsRangeBounds:
    """Each min/max pair must be ordered; a crossed range is a client bug
    that should 422 rather than silently match nothing."""

    @pytest.mark.parametrize(
        "params",
        [
            {"quantity_min": 5, "quantity_max": 4},
            {"step_setup_min": 30, "step_setup_max": 10},
            {"step_per_piece_min": 2.5, "step_per_piece_max": 1.0},
        ],
    )
    def test_rejects_min_above_max(self, params):
        with pytest.raises(ValidationError):
            LotFilterParams(**params)

    @pytest.mark.parametrize(
        "params",
        [
            {"quantity_min": 4, "quantity_max": 4},
            {"step_setup_min": 10, "step_setup_max": 30},
            {"step_per_piece_min": 1.0},
            {"step_per_piece_max": 1.0},
        ],
    )
    def test_allows_ordered_or_open_ranges(self, params):
        accepted = LotFilterParams(**params)  # no raise

        assert accepted.model_dump(include=set(params)) == params

    @pytest.mark.parametrize("field", ["quantity_min", "step_setup_max", "step_per_piece_min"])
    def test_rejects_negative_numbers(self, field):
        with pytest.raises(ValidationError):
            LotFilterParams(**{field: -1})
