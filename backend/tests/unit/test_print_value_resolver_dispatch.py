"""
print_value_resolver's dispatch is a plain if/elif chain rather than a
dict of resolvers: 10 branches in 24 lines with a final `else`
fallthrough is small enough to read, but the chain IS order-dependent (the
exact-match @resolve_url branch is tried before the @resolve_url: prefix
branch, and both before the generic "@" catch-all and the plain-attribute
fallthrough). This file pins one test per branch
of resolve_field_values's dispatch chain, plus the disambiguation and
unknown-"@" cases explicitly, so a future refactor of the chain (e.g. into
a dict of resolvers) has a net proving it didn't reorder anything.
"""

from pydantic import BaseModel

from src.modules.quality.application.services.print_value_resolver import resolve_field_values
from src.shared_kernel.domain.services.clock import today_utc


class _FakeRoot(BaseModel):
    public_id: str = "8f3c1234-0000-0000-0000-000000000000"
    lot_public_id: str | None = "aaaa1111-0000-0000-0000-000000000000"
    part_number: str = "MI-004871"


class TestResolveFieldValuesDispatchChain:
    """One test per branch of the :63-86 chain, in source order, plus the
    disambiguation and unknown-source guard tests."""

    async def test_at_today_resolves_to_todays_iso_date(self):
        values = await resolve_field_values(
            {"d": "@today"}, _FakeRoot(), domain_url="https://glados.test", actor_full_name="A"
        )
        assert values["d"] == today_utc().isoformat()

    async def test_at_actor_full_name_resolves_to_the_actor_argument(self):
        values = await resolve_field_values(
            {"who": "@actor_full_name"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="Jane Doe",
        )
        assert values["who"] == "Jane Doe"

    async def test_at_resolve_url_exact_match_uses_the_default_public_id_field(self):
        values = await resolve_field_values(
            {"url": "@resolve_url"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["url"] == "https://glados.test/resolve/8f3c1234-0000-0000-0000-000000000000"

    async def test_at_resolve_url_colon_prefix_uses_the_named_field_not_public_id(self):
        values = await resolve_field_values(
            {"url": "@resolve_url:lot_public_id"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["url"] == "https://glados.test/resolve/aaaa1111-0000-0000-0000-000000000000"

    async def test_exact_at_resolve_url_and_prefixed_at_resolve_url_colon_never_collide(self):
        """The disambiguation that matters here: "@resolve_url" must
        hit the exact-match branch (:67) and "@resolve_url:lot_public_id"
        must hit the prefix branch (:69), never the other one; if the
        `elif source.startswith("@resolve_url:")` check ever moved ahead
        of the `== "@resolve_url"` check, or the exact check were changed
        to a prefix check, this would start returning the wrong field's
        value (or the same value) for both placeholders."""
        values = await resolve_field_values(
            {"root_url": "@resolve_url", "lot_url": "@resolve_url:lot_public_id"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert (
            values["root_url"] == "https://glados.test/resolve/8f3c1234-0000-0000-0000-000000000000"
        )
        assert (
            values["lot_url"] == "https://glados.test/resolve/aaaa1111-0000-0000-0000-000000000000"
        )
        assert values["root_url"] != values["lot_url"]

    async def test_at_event_quantity_present_stringifies_the_argument(self):
        values = await resolve_field_values(
            {"qty": "@event_quantity"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
            event_quantity=3.0,
        )
        assert values["qty"] == "3"

    async def test_at_company_name_with_no_resolver_is_blank_not_a_raise(self):
        values = await resolve_field_values(
            {"name": "@company_name"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["name"] == ""

    async def test_at_row_count_present_stringifies_the_argument(self):
        values = await resolve_field_values(
            {"n": "@row_count"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
            row_count=7,
        )
        assert values["n"] == "7"

    async def test_row_scoped_source_resolves_to_empty_against_the_document_root(self):
        # is_row_source(source): meaningless against the root, resolved
        # per-row by resolve_row_values instead; the document-level slot
        # is intentionally left blank rather than erroring.
        values = await resolve_field_values(
            {"pos": "item.position"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["pos"] == ""

    async def test_unknown_at_prefixed_source_falls_through_to_the_generic_catch_all(self):
        """Any "@"-prefixed source not matched by an earlier, more
        specific branch hits the generic `startswith("@")` catch-all
        (:83) and resolves to "" rather than raising or reading a
        (nonexistent) root attribute literally named e.g.
        "@totally_unknown_source"."""
        values = await resolve_field_values(
            {"x": "@totally_unknown_source"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["x"] == ""

    async def test_plain_attribute_name_falls_through_to_the_final_else(self):
        values = await resolve_field_values(
            {"pn": "part_number"},
            _FakeRoot(),
            domain_url="https://glados.test",
            actor_full_name="A",
        )
        assert values["pn"] == "MI-004871"
