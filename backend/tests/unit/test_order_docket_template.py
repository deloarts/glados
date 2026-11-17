"""
End-to-end check of the drafted order docket: the JSON an admin is meant to
paste into the docket editor must actually parse, validate against its own
field map, and rasterise to a real multi-page PDF.

The fixture next door is the canonical copy, so the version this test pins
has to live in the tree, or a fresh clone would test nothing.

This is the only place every piece of the table machinery runs at once
(page scoping, column stacks, per-row images, page numbering) against the
real DocketRenderer rather than a fake, so it doubles as the feature's
integration test.
"""

import json
import re
from pathlib import Path

from src.modules.quality.adapters.outbound.rendering.docket_renderer import DocketRenderer
from src.modules.quality.application.services.docket_pagination import DocketRow
from src.modules.quality.application.services.docket_pagination import paginate
from src.modules.quality.application.services.docket_spec import parse_docket_spec
from src.modules.quality.application.services.docket_spec import row_fields_in_docket_spec
from src.modules.quality.application.services.docket_spec import validate_docket_spec
from src.modules.quality.application.services.print_field_sources import valid_source_names
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier

_TEMPLATE = Path(__file__).resolve().parents[1] / "fixtures" / "order_docket_a4.json"
_MEDIABOX_RE = re.compile(rb"/MediaBox\s*\[\s*[\d.]+\s+[\d.]+\s+([\d.]+)\s+([\d.]+)\s*\]")


def _draft() -> tuple[str, dict[str, str]]:
    raw = json.loads(_TEMPLATE.read_text())
    return json.dumps(raw["source"]), raw["field_map"]


def _rows(spec, count: int) -> list[DocketRow]:
    placeholders = row_fields_in_docket_spec(spec)
    return [
        DocketRow(
            values={p: f"{p}-{n}" for p in placeholders},
            images={p: None for p in placeholders},
        )
        for n in range(count)
    ]


class TestDraftedOrderDocket:
    def test_the_shipped_draft_parses(self):
        source, _ = _draft()
        spec = parse_docket_spec(source)
        assert spec.table is not None
        assert [c.header for c in spec.table.columns] == [
            "POS",
            "QTY",
            "PROJECT / PRODUCT",
            "IMAGE",
            "ARTICLE / PART NO. / DIM.",
        ]

    def test_the_shipped_draft_validates_against_its_own_field_map(self):
        source, field_map = _draft()
        validate_docket_spec(source, field_map)  # must not raise

    def test_every_source_the_draft_uses_is_actually_selectable(self):
        """The check that catches a source the resolver understands but the
        field-source list never offers: UpdatePrintTemplate rejects the save
        outright, so the drafted template would be unpasteable even though
        it renders perfectly in isolation."""
        _, field_map = _draft()
        allowed = valid_source_names(PrintClassifier.ORDER_DOCKET, None)
        assert set(field_map.values()) <= allowed

    def test_columns_fit_inside_the_frame(self):
        source, _ = _draft()
        spec = parse_docket_spec(source)
        frame = next(b for b in spec.blocks if b.type == "rect")
        right = spec.table.x_mm + sum(c.width_mm for c in spec.table.columns)
        assert spec.table.x_mm >= frame.x
        assert right <= frame.x + frame.w

    def test_five_positions_render_to_a_single_a4_page(self):
        source, _ = _draft()
        spec = parse_docket_spec(source)
        pages = paginate(spec, {"qr_payload": "https://glados.test/resolve/x"}, {}, _rows(spec, 5))
        pdf, _ = DocketRenderer().render_pdf(pages, paper="a4")

        sizes = _MEDIABOX_RE.findall(pdf)
        assert len(sizes) == 1
        width_pt, height_pt = (float(v) for v in sizes[0])
        assert (round(width_pt * 25.4 / 72), round(height_pt * 25.4 / 72)) == (210, 297)

    def test_twenty_positions_spill_onto_a_second_page(self):
        source, _ = _draft()
        spec = parse_docket_spec(source)
        pages = paginate(spec, {"qr_payload": "https://glados.test/resolve/x"}, {}, _rows(spec, 20))
        assert len(pages) == 2

        pdf, warnings = DocketRenderer().render_pdf(pages, paper="a4")
        assert len(_MEDIABOX_RE.findall(pdf)) == 2
        assert warnings == []

    def test_the_qr_encodes_the_orders_own_resolve_url(self):
        _, field_map = _draft()
        assert field_map["qr_payload"] == "@resolve_url"

    def test_an_order_with_no_positions_still_produces_one_page(self):
        source, _ = _draft()
        spec = parse_docket_spec(source)
        pages = paginate(spec, {"qr_payload": "https://glados.test/resolve/x"}, {}, [])
        pdf, _ = DocketRenderer().render_pdf(pages, paper="a4")
        assert len(_MEDIABOX_RE.findall(pdf)) == 1
