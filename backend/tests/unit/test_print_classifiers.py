"""
Unit tests for the classifier/trigger registry's pure helper functions.
"""

from src.modules.quality.application.services.print_classifiers import CLASSIFIERS
from src.modules.quality.application.services.print_classifiers import TRIGGERS
from src.modules.quality.application.services.print_classifiers import display_order_of
from src.modules.quality.application.services.print_classifiers import printer_kind_for
from src.modules.quality.application.services.print_classifiers import triggers_for
from src.modules.quality.domain.value_objects.print_classifier import PrintClassifier
from src.modules.quality.domain.value_objects.print_classifier import PrintOutputKind
from src.modules.quality.domain.value_objects.print_classifier import PrintTrigger


class TestTriggersFor:
    def test_source_item_label_offers_only_source_item_delivered(self):
        triggers = triggers_for(PrintClassifier.SOURCE_ITEM_LABEL)
        assert set(triggers) == {PrintTrigger.SOURCE_ITEM_DELIVERED}

    def test_bought_item_label_offers_only_bought_item_delivered(self):
        triggers = triggers_for(PrintClassifier.BOUGHT_ITEM_LABEL)
        assert set(triggers) == {PrintTrigger.BOUGHT_ITEM_DELIVERED}

    def test_made_item_label_offers_only_made_item_completed(self):
        triggers = triggers_for(PrintClassifier.MADE_ITEM_LABEL)
        assert set(triggers) == {PrintTrigger.MADE_ITEM_COMPLETED}

    def test_production_order_label_offers_only_production_order_rooted_triggers(self):
        triggers = triggers_for(PrintClassifier.PRODUCTION_ORDER_LABEL)
        assert set(triggers) == {
            PrintTrigger.PRODUCTION_ORDER_CREATED,
            PrintTrigger.PRODUCTION_ORDER_STARTED,
            PrintTrigger.PRODUCTION_ORDER_COMPLETION_RECORDED,
            PrintTrigger.PRODUCTION_ORDER_COMPLETED,
        }

    def test_catalogue_dockets_each_offer_their_matching_catalogue_trigger(self):
        # Every catalogue docket's root has a matching catalogue-rooted
        # delivery/completion trigger (source_item_delivered,
        # bought_item_delivered, made_item_completed all root at their
        # respective *_ITEM types); manual-only by default (no
        # default_trigger seeded) but armable for auto-print like any other
        # trigger-eligible classifier.
        assert triggers_for(PrintClassifier.MADE_ITEM_DOCKET) == [PrintTrigger.MADE_ITEM_COMPLETED]
        assert triggers_for(PrintClassifier.BOUGHT_ITEM_DOCKET) == [
            PrintTrigger.BOUGHT_ITEM_DELIVERED
        ]
        assert triggers_for(PrintClassifier.SOURCE_ITEM_DOCKET) == [
            PrintTrigger.SOURCE_ITEM_DELIVERED
        ]

    def test_every_classifier_has_a_key_in_the_registry(self):
        for classifier in PrintClassifier:
            assert classifier in CLASSIFIERS

    def test_every_trigger_has_a_key_in_the_registry(self):
        for trigger in PrintTrigger:
            assert trigger in TRIGGERS


class TestDisplayOrder:
    def test_the_two_settings_tabs_read_in_the_same_root_order(self):
        # Each tab filters CLASSIFIERS by output kind, so both must walk
        # the same stock -> purchased -> manufactured -> lot -> order flow.
        # order_docket leads the docket tab: procurement is upstream of all
        # of it, and no label has an ORDER root to pair with.
        labels = [c.value for c in CLASSIFIERS if CLASSIFIERS[c].output_kind == PrintOutputKind.ZPL]
        dockets = [
            c.value for c in CLASSIFIERS if CLASSIFIERS[c].output_kind == PrintOutputKind.PDF_DOCKET
        ]

        assert labels == [
            "source_item_label",
            "bought_item_label",
            "made_item_label",
            "lot_label",
            "scrap_tag",
            "production_order_label",
        ]
        assert dockets == [
            "order_docket",
            "source_item_docket",
            "bought_item_docket",
            "made_item_docket",
            "lot_docket",
            "production_order_docket",
        ]

    def test_every_classifier_has_a_distinct_display_position(self):
        positions = [display_order_of(c.value) for c in PrintClassifier]
        assert sorted(positions) == list(range(len(list(PrintClassifier))))

    def test_an_unknown_classifier_sorts_last_rather_than_raising(self):
        assert display_order_of("not_a_classifier") == len(list(PrintClassifier))


class TestPrinterKindFor:
    def test_zpl_output_needs_a_zpl_label_printer(self):
        assert printer_kind_for(PrintOutputKind.ZPL) == "zpl_label"

    def test_docket_output_needs_an_ipp_document_printer(self):
        assert printer_kind_for(PrintOutputKind.PDF_DOCKET) == "ipp_document"


class TestManualOnlyClassifiersHaveNoDefaultTrigger:
    def test_catalogue_dockets_have_no_default_trigger(self):
        assert CLASSIFIERS[PrintClassifier.MADE_ITEM_DOCKET].default_trigger is None
        assert CLASSIFIERS[PrintClassifier.BOUGHT_ITEM_DOCKET].default_trigger is None
        assert CLASSIFIERS[PrintClassifier.SOURCE_ITEM_DOCKET].default_trigger is None

    def test_labels_and_lifecycle_dockets_have_a_default_trigger(self):
        for classifier in (
            PrintClassifier.SOURCE_ITEM_LABEL,
            PrintClassifier.BOUGHT_ITEM_LABEL,
            PrintClassifier.MADE_ITEM_LABEL,
            PrintClassifier.PRODUCTION_ORDER_LABEL,
            PrintClassifier.LOT_LABEL,
            PrintClassifier.LOT_DOCKET,
            PrintClassifier.PRODUCTION_ORDER_DOCKET,
        ):
            assert CLASSIFIERS[classifier].default_trigger is not None
