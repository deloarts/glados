"""Synthetic Data Portal JSON:API documents in the shape the live API
answers with (parts with included manufacturer, product groups, documents
and picture; partscheck results)."""

from typing import Any

BASE_URL = "https://portal.example.test/api"
PICTURE_URL = "https://blob.example.test/pictures/512/contactor.png"


def part_resource(part_id: int = 451627) -> dict[str, Any]:
    return {
        "type": "parts",
        "id": str(part_id),
        "attributes": {
            "part_number": "SIE.3RT2015-1BB41",
            "order_number": "3RT2015-1BB41",
            "type_number": "3RT2015-1BB41",
            "designation": {"en_US": "CONTACTOR 3KW", "de_DE": "SCHUETZ 3KW", "fr_FR": "x"},
            "description": {"en_US": "Contactor, AC-3, 3 kW", "de_DE": ""},
            "identcode": "4011209780774 EAN",
        },
        "relationships": {
            "manufacturer": {"data": {"type": "manufacturers", "id": "65"}},
            "product_top_group": {"data": {"type": "eplan_catalog_entries", "id": "1"}},
            "product_group": {"data": {"type": "eplan_catalog_entries", "id": "2"}},
            "product_sub_group": {"data": {"type": "eplan_catalog_entries", "id": "3"}},
            "picture_file": {"data": {"type": "picturefile", "id": "9"}},
            "external_documents": {
                "data": [
                    {"type": "external_document", "id": "100"},
                    {"type": "external_document", "id": "101"},
                ]
            },
        },
    }


def parts_document(*part_ids: int) -> dict[str, Any]:
    return {
        "data": [part_resource(i) for i in (part_ids or (451627,))],
        "included": [
            {
                "type": "manufacturers",
                "id": "65",
                "attributes": {"short_name": "SIE", "long_name": "Siemens"},
            },
            {
                "type": "eplan_catalog_entries",
                "id": "1",
                "attributes": {"name": "Electrical engineering"},
            },
            {
                "type": "eplan_catalog_entries",
                "id": "2",
                "attributes": {"name": "Relays, contactors"},
            },
            {"type": "eplan_catalog_entries", "id": "3", "attributes": {"name": "Contactors"}},
            {
                "type": "external_document",
                "id": "100",
                "attributes": {
                    "external_document_value": "Siemens\\a.pdf",
                    "external_document_type": "0",
                },
            },
            {
                "type": "external_document",
                "id": "101",
                "attributes": {
                    "external_document_value": "https://support.example.test/3RT2015",
                    "external_document_type": "1",
                },
            },
            {
                "type": "picturefile",
                "id": "9",
                "attributes": None,
                "relationships": {"preview": {"data": {"type": "preview", "id": "pic"}}},
            },
            {"type": "preview", "id": "pic", "attributes": {"512": PICTURE_URL}},
        ],
    }


def check_document() -> dict[str, Any]:
    return {
        "data": [
            {
                "type": "partscheckresult",
                "attributes": {"search": "3RT2015-1BB41", "partid": 451627},
            },
            {"type": "partscheckmissingresult", "attributes": {"search": "6ES7", "partid": None}},
            {"type": "partscheckresult", "attributes": {"search": "1234", "partid": 1}},
            {"type": "partscheckresult", "attributes": {"search": "1234", "partid": 2}},
        ]
    }
