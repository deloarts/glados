"""
Unit tests for the customer data PDM ingest takes from a made file's
datacard: it is stored as received, never refused for being incomplete, a
dangling customer id reads as no customer, and a new file version updates it
in place. No database, no HTTP.
"""

from datetime import UTC
from datetime import datetime

from src.modules.catalogue.domain.entities.customer import Customer
from src.modules.catalogue.domain.value_objects.customer_level import CustomerLevel
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from tests.unit.ingest_pdm_file._helpers import MADE_VAR_MAP
from tests.unit.ingest_pdm_file._helpers import MADE_VARIABLES
from tests.unit.ingest_pdm_file._helpers import make_made_item
from tests.unit.ingest_pdm_file._helpers import make_payload
from tests.unit.ingest_pdm_file._helpers import make_pdm_settings
from tests.unit.ingest_pdm_file.rig import Rig

_CUSTOMER_MAP = {
    "customer_id": "Glados.CustomerId",
    "customer_name": "Glados.CustomerName",
    "customer_part_number": "Glados.CustomerPartNumber",
    "customer_revision": "Glados.CustomerRevision",
}


def _customer(id: int, *, archived: bool = False) -> Customer:
    return Customer(
        id=id,
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=None,
        changes=[],
        archived=archived,
        name=f"Customer {id}",
        legal_name=None,
        vat_id=None,
        level=CustomerLevel.B,
        street=None,
        city=None,
        country=None,
        postal_code=None,
        email=None,
        phone=None,
        weblink=None,
        creator_id=1,
    )


def _rig(**kwargs) -> Rig:
    return Rig(pdm_settings=make_pdm_settings(made_map={**MADE_VAR_MAP, **_CUSTOMER_MAP}), **kwargs)


def _variables(**customer: str) -> dict[str, str]:
    names = {
        "id": "Glados.CustomerId",
        "name": "Glados.CustomerName",
        "part_number": "Glados.CustomerPartNumber",
        "revision": "Glados.CustomerRevision",
    }
    return {**MADE_VARIABLES, **{names[key]: value for key, value in customer.items()}}


class TestCreate:
    async def test_stores_the_customer_data(self):
        rig = _rig(customers=[_customer(7)])
        payload = make_payload(
            kind="made",
            variables=_variables(id="7", name="Customer 7", part_number="C-100", revision="B"),
        )

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.customer_id == 7
        assert item.customer_part_number == "C-100"
        assert item.customer_revision == "B"

    async def test_accepts_an_archived_customer(self):
        rig = _rig(customers=[_customer(7, archived=True)])
        payload = make_payload(kind="made", variables=_variables(id="7", part_number="C-100"))

        outcome = await rig.use_case.execute(payload)

        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.customer_id == 7

    async def test_incomplete_data_is_stored_as_received(self):
        rig = _rig(customers=[_customer(7)])
        payload = make_payload(kind="made", variables=_variables(id="7", revision="B"))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.customer_id == 7
        assert item.customer_revision == "B"

    async def test_a_dangling_customer_id_reads_as_no_customer(self):
        rig = _rig(customers=[])
        payload = make_payload(kind="made", variables=_variables(id="99", part_number="C-100"))

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "created"
        item = await rig.made_item_repo.get_by_id(outcome.item_id)
        assert item.customer_id is None
        assert item.customer_part_number == "C-100"


class TestInPlaceUpdate:
    async def test_a_new_file_version_updates_the_customer_data_in_place(self):
        item = make_made_item(
            1,
            part_number="CAD-1001",
            revision="A",
            data_source=DataSource.CAD,
            vault_id="V1",
            pdm_file_id=100,
            pdm_file_version=1,
        )
        item.note = "from CAD"
        item.customer_id = 7
        item.customer_part_number = "C-100"
        item.customer_revision = "B"
        rig = _rig(made_items=[item], customers=[_customer(7), _customer(8)])
        payload = make_payload(
            kind="made",
            file_version=2,
            variables=_variables(id="8", part_number="D-200", revision="C"),
        )

        outcome = await rig.use_case.execute(payload)

        assert outcome.action == "updated"
        updated = await rig.made_item_repo.get_by_id(1)
        assert updated.revision == "A"
        assert updated.customer_id == 8
        assert updated.customer_part_number == "D-200"
        assert updated.customer_revision == "C"
