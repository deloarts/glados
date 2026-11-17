"""
Unit tests for kpi_rules.scrap_by_reason and kpi_rules.rejected_per_supplier,
including the empty-input and zero-denominator cases that must resolve to
an empty list or a None ratio rather than a division by zero.
"""

from src.modules.quality.domain.services import kpi_rules


def _event(quantity: float, reason: str) -> kpi_rules.ScrapReasonRow:
    return kpi_rules.ScrapReasonRow(quantity=quantity, reason=reason)


def _delivery(
    supplier_id: int,
    supplier_name: str,
    quantity: float,
    quantity_rejected: float,
    quantity_rejected_lost: float,
) -> kpi_rules.SupplierDeliveryRow:
    return kpi_rules.SupplierDeliveryRow(
        supplier_id=supplier_id,
        supplier_name=supplier_name,
        quantity=quantity,
        quantity_rejected=quantity_rejected,
        quantity_rejected_lost=quantity_rejected_lost,
    )


class TestScrapByReason:
    def test_empty_input_returns_empty_list(self) -> None:
        assert kpi_rules.scrap_by_reason([]) == []

    def test_groups_and_sums_by_reason(self) -> None:
        rows = kpi_rules.scrap_by_reason(
            [
                _event(2.0, "tool_breakage"),
                _event(1.0, "tool_breakage"),
                _event(3.0, "material_defect"),
            ]
        )
        by_reason = {row.reason: row.quantity for row in rows}
        assert by_reason == {"tool_breakage": 3.0, "material_defect": 3.0}

    def test_sorted_descending_by_quantity(self) -> None:
        rows = kpi_rules.scrap_by_reason(
            [
                _event(1.0, "other"),
                _event(5.0, "tool_breakage"),
                _event(3.0, "material_defect"),
            ]
        )
        assert [row.reason for row in rows] == ["tool_breakage", "material_defect", "other"]

    def test_share_of_total(self) -> None:
        rows = kpi_rules.scrap_by_reason(
            [_event(3.0, "tool_breakage"), _event(1.0, "material_defect")]
        )
        by_reason = {row.reason: row.share for row in rows}
        assert by_reason["tool_breakage"].value == 0.75
        assert by_reason["material_defect"].value == 0.25

    def test_pools_completion_scrap_and_lost_delivery_rejections_into_one_ranking(self) -> None:
        # One reason fed entirely by internal scrap, one entirely by
        # goods-receipt loss, one fed by both; the function itself does
        # not distinguish where an event came from, per its docstring.
        rows = kpi_rules.scrap_by_reason(
            [
                _event(4.0, "tool_breakage"),
                _event(2.0, "supplier_damage"),
                _event(1.0, "supplier_damage"),
            ]
        )
        by_reason = {row.reason: row.quantity for row in rows}
        assert by_reason == {"tool_breakage": 4.0, "supplier_damage": 3.0}


class TestRejectedPerSupplier:
    def test_empty_input_returns_empty_list(self) -> None:
        assert kpi_rules.rejected_per_supplier([]) == []

    def test_zero_denominator_when_nothing_received_yields_none_ratio(self) -> None:
        rows = kpi_rules.rejected_per_supplier([_delivery(1, "Acme", 0.0, 0.0, 0.0)])
        assert len(rows) == 1
        assert rows[0].rejected_ratio.value is None
        assert rows[0].rejected_ratio.denominator == 0

    def test_aggregates_delivered_rejected_and_lost_per_supplier(self) -> None:
        rows = kpi_rules.rejected_per_supplier(
            [
                _delivery(1, "Acme", 8.0, 2.0, 1.0),
                _delivery(1, "Acme", 5.0, 0.0, 0.0),
            ]
        )
        assert len(rows) == 1
        row = rows[0]
        assert row.supplier_id == 1
        assert row.supplier_name == "Acme"
        assert row.delivered == 13.0
        assert row.rejected == 2.0
        assert row.rejected_lost == 1.0
        assert row.rejected_ratio.value == 2.0 / 15.0

    def test_sorted_descending_by_rejected_ratio_none_last(self) -> None:
        rows = kpi_rules.rejected_per_supplier(
            [
                _delivery(1, "Low", 9.0, 1.0, 0.0),  # ratio 0.1
                _delivery(2, "High", 5.0, 5.0, 5.0),  # ratio 0.5
                _delivery(3, "None", 0.0, 0.0, 0.0),  # ratio None
            ]
        )
        assert [row.supplier_id for row in rows] == [2, 1, 3]

    def test_multiple_suppliers_kept_separate(self) -> None:
        rows = kpi_rules.rejected_per_supplier(
            [
                _delivery(1, "Acme", 10.0, 0.0, 0.0),
                _delivery(2, "Beta", 4.0, 1.0, 1.0),
            ]
        )
        by_id = {row.supplier_id: row for row in rows}
        assert by_id[1].delivered == 10.0
        assert by_id[1].rejected == 0.0
        assert by_id[2].delivered == 4.0
        assert by_id[2].rejected == 1.0
        assert by_id[2].rejected_lost == 1.0
