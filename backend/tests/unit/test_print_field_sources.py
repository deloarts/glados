"""
The field-source allowlist that drives both the frontend's field-map
editor and UpdatePrintTemplate's validation.
"""

from src.modules.quality.application.services.print_field_sources import field_sources_for
from src.modules.quality.application.services.print_field_sources import related_uuid_fields_for
from src.modules.quality.application.services.print_field_sources import valid_source_names
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier


class TestFieldSourcesFor:
    def test_company_name_is_offered_for_a_zpl_label_classifier(self):
        # Text-valued, so it works for ZPL too: resolve_field_values()
        # resolves it the same way regardless of output_kind.
        names = {s.name for s in field_sources_for(PrintClassifier.SOURCE_ITEM_LABEL, None)}
        assert "@company_name" in names

    def test_company_name_is_offered_for_a_docket_classifier(self):
        names = {s.name for s in field_sources_for(PrintClassifier.MADE_ITEM_DOCKET, None)}
        assert "@company_name" in names

    def test_image_valued_sources_are_docket_only(self):
        label_names = {s.name for s in field_sources_for(PrintClassifier.SOURCE_ITEM_LABEL, None)}
        docket_names = {s.name for s in field_sources_for(PrintClassifier.MADE_ITEM_DOCKET, None)}
        for image_source in ("@part_image", "@company_logo", "@qr_image"):
            assert image_source not in label_names
            assert image_source in docket_names


class TestValidSourceNames:
    def test_company_name_is_a_valid_source_for_a_zpl_classifier(self):
        assert "@company_name" in valid_source_names(PrintClassifier.SOURCE_ITEM_LABEL, None)


class TestRelatedUuidFieldsFor:
    def test_production_order_label_offers_lot_and_made_item_uuids(self):
        assert set(related_uuid_fields_for(PrintClassifier.PRODUCTION_ORDER_LABEL)) == {
            "lot_public_id",
            "made_item_public_id",
        }

    def test_lot_label_offers_only_made_item_uuid(self):
        # LotResult's own public_id is the root's; only made_item_public_id
        # is an *additional* related uuid.
        assert set(related_uuid_fields_for(PrintClassifier.LOT_LABEL)) == {"made_item_public_id"}

    def test_made_item_label_offers_no_related_uuids(self):
        # A catalogue-rooted classifier's root has no other record's uuid
        # denormalized onto it.
        assert related_uuid_fields_for(PrintClassifier.MADE_ITEM_LABEL) == []


class TestFieldSourcesForRelatedUuids:
    def test_production_order_label_offers_a_resolve_url_variant_per_related_uuid(self):
        names = {s.name for s in field_sources_for(PrintClassifier.PRODUCTION_ORDER_LABEL, None)}
        assert "@resolve_url" in names
        assert "@resolve_url:lot_public_id" in names
        assert "@resolve_url:made_item_public_id" in names

    def test_resolve_url_variant_description_names_the_record(self):
        sources = field_sources_for(PrintClassifier.PRODUCTION_ORDER_LABEL, None)
        lot_url = next(s for s in sources if s.name == "@resolve_url:lot_public_id")
        assert "lot" in lot_url.description.lower()

    def test_qr_image_variant_only_offered_for_dockets(self):
        label_names = {
            s.name for s in field_sources_for(PrintClassifier.PRODUCTION_ORDER_LABEL, None)
        }
        docket_names = {
            s.name for s in field_sources_for(PrintClassifier.PRODUCTION_ORDER_DOCKET, None)
        }
        assert "@qr_image:lot_public_id" not in label_names
        assert "@qr_image:lot_public_id" in docket_names

    def test_made_item_label_offers_no_resolve_url_variants_beyond_the_base(self):
        names = [s.name for s in field_sources_for(PrintClassifier.MADE_ITEM_LABEL, None)]
        resolve_url_names = [n for n in names if n.startswith("@resolve_url")]
        assert resolve_url_names == ["@resolve_url"]


class TestRowSources:
    def test_order_docket_offers_the_item_namespace(self):
        names = {s.name for s in field_sources_for(PrintClassifier.ORDER_DOCKET, None)}
        assert "item.position" in names
        assert "item.item_article_name" in names
        assert "item.product_number" in names

    def test_order_docket_offers_the_per_row_part_photo(self):
        names = {s.name for s in field_sources_for(PrintClassifier.ORDER_DOCKET, None)}
        assert "@item_image" in names

    def test_row_sources_are_tagged_so_the_editor_can_group_them(self):
        rows = [s for s in field_sources_for(PrintClassifier.ORDER_DOCKET, None) if s.kind == "row"]
        assert rows
        assert all(s.name.startswith("item.") or s.name == "@item_image" for s in rows)

    def test_the_root_child_collection_is_not_offered_as_a_text_field(self):
        # OrderResult.items is the table's row source, not a printable value.
        names = {s.name for s in field_sources_for(PrintClassifier.ORDER_DOCKET, None)}
        assert "items" not in names

    def test_a_classifier_without_rows_offers_no_row_namespace(self):
        sources = field_sources_for(PrintClassifier.LOT_DOCKET, None)
        assert not [s for s in sources if s.kind == "row"]

    def test_row_count_is_offered_for_a_table_classifier(self):
        names = {s.name for s in field_sources_for(PrintClassifier.ORDER_DOCKET, None)}
        assert "@row_count" in names

    def test_row_count_is_withheld_where_there_is_nothing_to_count(self):
        names = {s.name for s in field_sources_for(PrintClassifier.LOT_DOCKET, None)}
        assert "@row_count" not in names
