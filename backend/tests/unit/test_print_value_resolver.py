"""
Unit tests for print field-value resolution: bare root attributes, computed
sources (@today, @actor_full_name, @resolve_url variants), image sources
(@part_image, @company_logo, @qr_image), and row-scoped sources (item.*
fields). All resolvers tested in isolation and against real root types.
"""

from datetime import UTC
from datetime import date
from datetime import datetime

from pydantic import BaseModel

from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.quality.application.services.docket_asset_resolver import DocketAssetResolver
from src.modules.quality.application.services.print_value_resolver import resolve_field_values
from src.modules.quality.application.services.print_value_resolver import resolve_image_sources
from src.modules.quality.application.services.print_value_resolver import resolve_row_values
from src.shared_kernel.domain.services import clock
from src.shared_kernel.domain.services.clock import today_utc


class _FakeRoot(BaseModel):
    public_id: str = "8f3c1234-0000-0000-0000-000000000000"
    lot_public_id: str | None = "aaaa1111-0000-0000-0000-000000000000"
    part_number: str = "MI-004871"
    quantity: float = 2.5
    is_alteration: bool = True
    ready: bool = False
    created: date = date(2026, 1, 1)


class _FakeAdminSettingsRepo:
    def __init__(self, company_name: str | None):
        self._company_name = company_name

    async def get_general(self):
        from src.modules.platform.domain.entities.admin_settings.general import AdminGeneralSettings

        return AdminGeneralSettings(
            id=1,
            company_name=self._company_name,
            company_legal_name=None,
            company_logo_key=None,
            contact_email=None,
            imprint_url=None,
            privacy_url=None,
            support_url=None,
            product_number_pattern="",
            project_number_pattern="",
            allow_headless_projects=True,
            empty_value_placeholder="-",
            office_launcher_enabled=False,
            office_sharepoint_url="",
            default_language=Language.enGB,
            default_timezone="Europe/Vienna",
            default_date_format=DateFormat.ISO,
            currency="EUR",
        )


class _FakeAssetResolver:
    def __init__(self, part_image: bytes | None = None, company_logo: bytes | None = None):
        self._part_image = part_image
        self._company_logo = company_logo
        self.part_image_calls: list[tuple] = []

    async def resolve_part_image(self, root_type, root):
        self.part_image_calls.append((root_type, root))
        return self._part_image

    async def resolve_company_logo(self):
        return self._company_logo

    async def resolve_company_name(self):
        return "unused"


class _FakeQrRenderer:
    def __init__(self):
        self.rendered_payloads: list[str] = []

    def render_qr_png(self, payload, *, size_mm=25.0):
        self.rendered_payloads.append(payload)
        return b"\x89PNG-qr"

    def render_pdf(self, *args, **kwargs):
        raise NotImplementedError

    def render_preview_png(self, *args, **kwargs):
        raise NotImplementedError


class TestResolveFieldValues:
    async def test_bare_field_reads_straight_off_the_root(self):
        values = await resolve_field_values(
            {"pn": "part_number"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["pn"] == "MI-004871"

    async def test_missing_bare_field_resolves_to_empty_string(self):
        values = await resolve_field_values(
            {"x": "does_not_exist"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["x"] == ""

    async def test_today_is_todays_date(self):
        values = await resolve_field_values(
            {"d": "@today"}, _FakeRoot(), domain_url="https://glados.test", actor_full_name="A"
        )
        assert values["d"] == today_utc().isoformat()

    async def test_actor_full_name(self):
        values = await resolve_field_values(
            {"who": "@actor_full_name"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="Jane Doe",
        )
        assert values["who"] == "Jane Doe"

    async def test_resolve_url_builds_from_public_id(self):
        values = await resolve_field_values(
            {"url": "@resolve_url"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["url"] == "https://glados.test/resolve/8f3c1234-0000-0000-0000-000000000000"

    async def test_resolve_url_with_field_builds_from_the_named_uuid_field(self):
        values = await resolve_field_values(
            {"url": "@resolve_url:lot_public_id"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["url"] == "https://glados.test/resolve/aaaa1111-0000-0000-0000-000000000000"

    async def test_resolve_url_with_field_is_independent_of_the_roots_own_public_id(self):
        values = await resolve_field_values(
            {"root_url": "@resolve_url", "lot_url": "@resolve_url:lot_public_id"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["root_url"] != values["lot_url"]

    async def test_resolve_url_with_field_missing_value_resolves_to_empty_string(self):
        values = await resolve_field_values(
            {"url": "@resolve_url:lot_public_id"},
            _FakeRoot(lot_public_id=None),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["url"] == ""

    async def test_event_quantity_present(self):
        values = await resolve_field_values(
            {"qty": "@event_quantity"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
            event_quantity=3.0,
        )
        assert values["qty"] == "3"

    async def test_event_quantity_absent_resolves_to_empty_string(self):
        values = await resolve_field_values(
            {"qty": "@event_quantity"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["qty"] == ""

    async def test_image_valued_computed_source_resolves_to_empty_string_here(self):
        # @part_image/@company_logo/@qr_image are image-valued; they
        # belong to resolve_image_sources, not this string-valued function.
        # Must still degrade gracefully rather than raise if one somehow
        # ends up in a ZPL field_map.
        values = await resolve_field_values(
            {"img": "@part_image"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["img"] == ""

    async def test_company_name_with_no_asset_resolver_resolves_to_empty_string(self):
        values = await resolve_field_values(
            {"name": "@company_name"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["name"] == ""

    async def test_company_name_reads_from_asset_resolver(self):
        resolver = DocketAssetResolver(
            item_picture_repo=None,  # type: ignore[arg-type]
            admin_settings_repo=_FakeAdminSettingsRepo("Example Ltd"),
            storage=None,
        )
        values = await resolve_field_values(
            {"name": "@company_name"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
            asset_resolver=resolver,
        )
        assert values["name"] == "Example Ltd"

    async def test_today_is_the_tenant_day_with_an_asset_resolver(self, monkeypatch):
        """23:30 UTC on 1 November is 00:30 on 2 November in Vienna, the
        tenant's timezone, so a label printed then shows the 2nd."""

        class _Clock(datetime):
            @classmethod
            def now(cls, tz=None):
                return datetime(2026, 11, 1, 23, 30, tzinfo=UTC)

        monkeypatch.setattr(clock, "datetime", _Clock)
        resolver = DocketAssetResolver(
            item_picture_repo=None,  # type: ignore[arg-type]
            admin_settings_repo=_FakeAdminSettingsRepo("Example Ltd"),
            storage=None,
        )
        values = await resolve_field_values(
            {"d": "@today"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
            asset_resolver=resolver,
        )
        assert values["d"] == "2026-11-02"

    async def test_boolean_field_formats_as_yes_no(self):
        values = await resolve_field_values(
            {"alt": "is_alteration", "rdy": "ready"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["alt"] == "Yes"
        assert values["rdy"] == "No"

    async def test_float_field_drops_trailing_zeros(self):
        values = await resolve_field_values(
            {"q": "quantity"}, _FakeRoot(), domain_url="https://glados.test", actor_full_name="A"
        )
        assert values["q"] == "2.5"

    async def test_date_field_formats_as_iso(self):
        values = await resolve_field_values(
            {"c": "created"}, _FakeRoot(), domain_url="https://glados.test", actor_full_name="A"
        )
        assert values["c"] == "2026-01-01"


class TestResolveImageSources:
    async def test_part_image_reads_from_asset_resolver_with_root_type(self):
        resolver = _FakeAssetResolver(part_image=b"\x89PNGpart")
        images = await resolve_image_sources(
            {"photo": "@part_image"},
            _FakeRoot(),
            "made_item",
            domain_url="https://glados.test",
            asset_resolver=resolver,
            qr_renderer=None,
        )
        assert images["photo"] == b"\x89PNGpart"
        assert resolver.part_image_calls == [("made_item", _FakeRoot())]

    async def test_company_logo_reads_from_asset_resolver(self):
        resolver = _FakeAssetResolver(company_logo=b"\x89PNGlogo")
        images = await resolve_image_sources(
            {"logo": "@company_logo"},
            _FakeRoot(),
            "made_item",
            domain_url="https://glados.test",
            asset_resolver=resolver,
            qr_renderer=None,
        )
        assert images["logo"] == b"\x89PNGlogo"

    async def test_no_asset_resolver_resolves_to_none_not_a_raise(self):
        images = await resolve_image_sources(
            {"photo": "@part_image", "logo": "@company_logo"},
            _FakeRoot(),
            "made_item",
            domain_url="https://glados.test",
            asset_resolver=None,
            qr_renderer=None,
        )
        assert images == {"photo": None, "logo": None}

    async def test_qr_image_renders_from_resolve_url(self):
        qr_renderer = _FakeQrRenderer()
        images = await resolve_image_sources(
            {"qr": "@qr_image"},
            _FakeRoot(),
            "made_item",
            domain_url="https://glados.test",
            asset_resolver=None,
            qr_renderer=qr_renderer,
        )
        assert images["qr"] == b"\x89PNG-qr"
        assert qr_renderer.rendered_payloads == [
            "https://glados.test/resolve/8f3c1234-0000-0000-0000-000000000000"
        ]

    async def test_qr_image_with_no_public_id_resolves_to_none(self):
        class _RootWithoutPublicId(BaseModel):
            public_id: str | None = None

        qr_renderer = _FakeQrRenderer()
        images = await resolve_image_sources(
            {"qr": "@qr_image"},
            _RootWithoutPublicId(),
            "made_item",
            domain_url="https://glados.test",
            asset_resolver=None,
            qr_renderer=qr_renderer,
        )
        assert images["qr"] is None
        assert qr_renderer.rendered_payloads == []

    async def test_qr_image_with_field_renders_from_the_named_uuid_field(self):
        qr_renderer = _FakeQrRenderer()
        images = await resolve_image_sources(
            {"qr": "@qr_image:lot_public_id"},
            _FakeRoot(),
            "made_item",
            domain_url="https://glados.test",
            asset_resolver=None,
            qr_renderer=qr_renderer,
        )
        assert images["qr"] == b"\x89PNG-qr"
        assert qr_renderer.rendered_payloads == [
            "https://glados.test/resolve/aaaa1111-0000-0000-0000-000000000000"
        ]

    async def test_non_image_source_is_not_included(self):
        images = await resolve_image_sources(
            {"pn": "part_number"},
            _FakeRoot(),
            "made_item",
            domain_url="https://glados.test",
            asset_resolver=None,
            qr_renderer=None,
        )
        assert images == {}


class _FakeRow:
    def __init__(self, position=1, quantity=5.0, article="Bolt"):
        self.position = position
        self.quantity = quantity
        self.item_article_name = article


class TestResolveRowValues:
    def test_item_prefixed_sources_read_the_row_not_the_root(self):
        field_map = {"pos": "item.position", "art": "item.item_article_name"}
        values = resolve_row_values(field_map, _FakeRow(position=3), {"pos", "art"})
        assert values == {"pos": "3", "art": "Bolt"}

    def test_numbers_stringify_the_same_way_as_document_values(self):
        values = resolve_row_values({"q": "item.quantity"}, _FakeRow(quantity=5.0), {"q"})
        assert values["q"] == "5"

    def test_an_unknown_row_attribute_yields_an_empty_cell(self):
        values = resolve_row_values({"x": "item.nope"}, _FakeRow(), {"x"})
        assert values["x"] == ""

    def test_only_the_requested_placeholders_are_resolved(self):
        field_map = {"pos": "item.position", "art": "item.item_article_name"}
        assert set(resolve_row_values(field_map, _FakeRow(), {"pos"})) == {"pos"}


class TestRowSourcesInDocumentScope:
    async def test_a_row_source_resolves_to_empty_against_the_root(self):
        values = await resolve_field_values(
            {"pos": "item.position"},
            _FakeRow(position=3),
            domain_url="https://glados.test",
            actor_full_name="Tester",
        )
        assert values["pos"] == ""

    async def test_row_count_is_supplied_by_the_caller(self):
        values = await resolve_field_values(
            {"n": "@row_count"},
            _FakeRow(),
            domain_url="https://glados.test",
            actor_full_name="Tester",
            row_count=5,
        )
        assert values["n"] == "5"

    async def test_row_count_without_a_table_is_blank_rather_than_zero(self):
        values = await resolve_field_values(
            {"n": "@row_count"},
            _FakeRow(),
            domain_url="https://glados.test",
            actor_full_name="Tester",
        )
        assert values["n"] == ""
