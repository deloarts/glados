"""
DB-backed coverage for the PDM link columns on MadeItem/BoughtItem: a
round trip through the repository mappers, get_family_by_pdm_file's
newest-revision-first ordering (revision_scheme.sort_key), get_by_pdm_file,
find_claim_candidate's three outcomes, and the partial unique indexes
(uq_made_item_pdm_file_revision, uq_bought_item_pdm_file) that back
identity per docs/reference/field-ownership.md section 1.2.
"""

from datetime import UTC
from datetime import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from src.modules.catalogue.adapters.outbound.persistence.models.bought_item_model import (
    BoughtItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.models.made_item_model import (
    MadeItemOrmModel,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.bought_item_repository.item import (
    SqlAlchemyBoughtItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.made_item_repository.item import (
    SqlAlchemyMadeItemRepository,
)
from src.modules.catalogue.adapters.outbound.persistence.repositories.supplier_repository import (
    SqlAlchemySupplierRepository,
)
from src.modules.catalogue.domain.entities.bought_item import BoughtItem
from src.modules.catalogue.domain.entities.made_item import MadeItem
from src.modules.catalogue.domain.entities.supplier import Supplier
from src.modules.catalogue.domain.value_objects.bought_item_status import BoughtItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.data_source import DataSource
from src.modules.catalogue.domain.value_objects.made_item_status import MadeItemCatalogueStatus
from src.modules.catalogue.domain.value_objects.pdm_sync_state import PdmSyncState
from src.modules.catalogue.domain.value_objects.supplier_level import SupplierLevel
from src.modules.platform.adapters.outbound.persistence.statements import count_rows

_SYNCED_AT = datetime(2026, 9, 3, 10, 0, tzinfo=UTC)


async def _made_item(
    db,
    creator_id: int,
    *,
    part_number: str | None,
    revision: str,
    vault_id: str | None = None,
    pdm_file_id: int | None = None,
    pdm_file_version: int | None = None,
    pdm_synced_at: datetime | None = None,
    pdm_sync_state: PdmSyncState | None = None,
    pdm_source_item_id: int | None = None,
    archived: bool = False,
) -> MadeItem:
    seeded = await SqlAlchemyMadeItemRepository(db).save(
        MadeItem(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=archived,
            revision=revision,
            revision_date=None,
            revision_note=None,
            article_name="Bracket",
            status=MadeItemCatalogueStatus.ACTIVE,
            data_source=DataSource.CAD if pdm_file_id is not None else DataSource.WEB,
            part_number=part_number,
            material=None,
            mass=None,
            base_size=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            bought_item_id=None,
            source_item_id=None,
            article_group_ids=[],
            successor_item_id=None,
            changed_by_id=None,
            vault_id=vault_id,
            pdm_file_id=pdm_file_id,
            pdm_file_version=pdm_file_version,
            pdm_synced_at=pdm_synced_at,
            pdm_sync_state=pdm_sync_state,
            pdm_source_item_id=pdm_source_item_id,
        )
    )
    await db.commit()
    return seeded


async def _supplier(db, creator_id: int) -> Supplier:
    saved = await SqlAlchemySupplierRepository(db).save(
        Supplier(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=False,
            name="Acme",
            legal_name=None,
            vat_id=None,
            level=SupplierLevel.B,
            capability_ids=[],
            article_group_ids=[],
            street=None,
            city=None,
            country=None,
            postal_code=None,
            email=None,
            phone=None,
            weblink=None,
            order_email=None,
            order_language=None,
            order_template=None,
            request_email=None,
            request_language=None,
            request_template=None,
            creator_id=creator_id,
        )
    )
    await db.commit()
    return saved


async def _bought_item(
    db,
    creator_id: int,
    manufacturer_id: int,
    *,
    order_code_1: str = "OC-1",
    gtin: str | None = None,
    data_source: DataSource = DataSource.WEB,
    part_number: str | None = None,
    vault_id: str | None = None,
    pdm_file_id: int | None = None,
    pdm_file_version: int | None = None,
    pdm_synced_at: datetime | None = None,
    pdm_sync_state: PdmSyncState | None = None,
    archived: bool = False,
) -> BoughtItem:
    saved = await SqlAlchemyBoughtItemRepository(db).save(
        BoughtItem(
            id=0,
            created=datetime(2026, 1, 1, tzinfo=UTC),
            changed=datetime(2026, 1, 1, tzinfo=UTC),
            changes=[],
            archived=archived,
            article_name="Widget",
            order_code_1=order_code_1,
            order_code_2=None,
            gtin=gtin,
            ean=None,
            tariff_number=None,
            status=BoughtItemCatalogueStatus.ACTIVE,
            data_source=data_source,
            part_number=part_number,
            mass=None,
            note=None,
            weblink=None,
            files=[],
            creator_id=creator_id,
            approver_id=None,
            manufacturer_id=manufacturer_id,
            article_group_ids=[],
            successor_item_id=None,
            vault_id=vault_id,
            pdm_file_id=pdm_file_id,
            pdm_file_version=pdm_file_version,
            pdm_synced_at=pdm_synced_at,
            pdm_sync_state=pdm_sync_state,
        )
    )
    await db.commit()
    return saved


class TestMadeItemPdmLinkRoundTrip:
    async def test_link_columns_round_trip(self, db, create_user):
        user = await create_user()
        saved = await _made_item(
            db,
            user.id,
            part_number="PN-1",
            revision="A",
            vault_id="VAULT-1",
            pdm_file_id=101,
            pdm_file_version=3,
            pdm_synced_at=_SYNCED_AT,
            pdm_sync_state=PdmSyncState.SYNCED,
            pdm_source_item_id=55,
        )

        result = await SqlAlchemyMadeItemRepository(db).get_by_id(saved.id)

        assert result is not None
        assert result.vault_id == "VAULT-1"
        assert result.pdm_file_id == 101
        assert result.pdm_file_version == 3
        assert result.pdm_synced_at == _SYNCED_AT
        assert result.pdm_sync_state == "synced"
        assert result.pdm_source_item_id == 55

    async def test_link_columns_default_to_none(self, db, create_user):
        user = await create_user()
        saved = await _made_item(db, user.id, part_number="PN-2", revision="A")

        result = await SqlAlchemyMadeItemRepository(db).get_by_id(saved.id)

        assert result is not None
        assert result.vault_id is None
        assert result.pdm_file_id is None
        assert result.pdm_file_version is None
        assert result.pdm_synced_at is None
        assert result.pdm_sync_state is None
        assert result.pdm_source_item_id is None


class TestBoughtItemPdmLinkRoundTrip:
    async def test_link_columns_round_trip(self, db, create_user):
        user = await create_user()
        supplier = await _supplier(db, user.id)
        saved = await _bought_item(
            db,
            user.id,
            supplier.id,
            data_source=DataSource.CAD,
            part_number="PN-B1",
            vault_id="VAULT-1",
            pdm_file_id=201,
            pdm_file_version=2,
            pdm_synced_at=_SYNCED_AT,
            pdm_sync_state=PdmSyncState.SYNCED,
        )

        result = await SqlAlchemyBoughtItemRepository(db).get_by_id(saved.id)

        assert result is not None
        assert result.vault_id == "VAULT-1"
        assert result.pdm_file_id == 201
        assert result.pdm_file_version == 2
        assert result.pdm_synced_at == _SYNCED_AT
        assert result.pdm_sync_state == "synced"


class TestGetFamilyByPdmFile:
    async def test_newest_revision_first_numeric(self, db, create_user):
        """Same "9" < "10" trap as get_multi's latest_only window
        (test_made_item_repository.py): plain string order would rank
        "9" above "10"."""
        user = await create_user()
        older = await _made_item(
            db, user.id, part_number="PN-1", revision="9", vault_id="V1", pdm_file_id=1
        )
        newer = await _made_item(
            db, user.id, part_number="PN-1", revision="10", vault_id="V1", pdm_file_id=1
        )

        results = await SqlAlchemyMadeItemRepository(db).get_family_by_pdm_file("V1", 1)

        assert [r.id for r in results] == [newer.id, older.id]

    async def test_newest_revision_first_alpha(self, db, create_user):
        user = await create_user()
        older = await _made_item(
            db, user.id, part_number="PN-2", revision="Z", vault_id="V1", pdm_file_id=2
        )
        newer = await _made_item(
            db, user.id, part_number="PN-2", revision="AA", vault_id="V1", pdm_file_id=2
        )

        results = await SqlAlchemyMadeItemRepository(db).get_family_by_pdm_file("V1", 2)

        assert [r.id for r in results] == [newer.id, older.id]

    async def test_excludes_other_pdm_files_and_deleted_rows(self, db, create_user):
        user = await create_user()
        target = await _made_item(
            db, user.id, part_number="PN-3", revision="A", vault_id="V1", pdm_file_id=3
        )
        await _made_item(
            db, user.id, part_number="PN-4", revision="A", vault_id="V1", pdm_file_id=4
        )
        await _made_item(
            db,
            user.id,
            part_number="PN-3",
            revision="B",
            vault_id="V1",
            pdm_file_id=3,
            archived=True,
        )

        results = await SqlAlchemyMadeItemRepository(db).get_family_by_pdm_file("V1", 3)

        assert [r.id for r in results] == [target.id]

    async def test_unknown_file_returns_empty(self, db, create_user):
        await create_user()
        assert await SqlAlchemyMadeItemRepository(db).get_family_by_pdm_file("V1", 999) == []


class TestGetByPdmFile:
    async def test_returns_the_match(self, db, create_user):
        user = await create_user()
        supplier = await _supplier(db, user.id)
        saved = await _bought_item(db, user.id, supplier.id, vault_id="V1", pdm_file_id=10)

        result = await SqlAlchemyBoughtItemRepository(db).get_by_pdm_file("V1", 10)

        assert result is not None
        assert result.id == saved.id

    async def test_returns_none_when_missing(self, db, create_user):
        user = await create_user()
        await _supplier(db, user.id)
        assert await SqlAlchemyBoughtItemRepository(db).get_by_pdm_file("V1", 999) is None

    async def test_ignores_deleted_rows(self, db, create_user):
        user = await create_user()
        supplier = await _supplier(db, user.id)
        await _bought_item(db, user.id, supplier.id, vault_id="V1", pdm_file_id=11, archived=True)

        assert await SqlAlchemyBoughtItemRepository(db).get_by_pdm_file("V1", 11) is None


class TestFindClaimCandidate:
    async def test_matches_on_exact_gtin(self, db, create_user):
        user = await create_user()
        supplier = await _supplier(db, user.id)
        target = await _bought_item(db, user.id, supplier.id, gtin="1234567890123")

        result = await SqlAlchemyBoughtItemRepository(db).find_claim_candidate(
            gtin="1234567890123", manufacturer_id=None, order_code_1=None
        )

        assert result is not None
        assert result.id == target.id

    async def test_falls_back_to_manufacturer_and_order_code(self, db, create_user):
        user = await create_user()
        supplier = await _supplier(db, user.id)
        target = await _bought_item(db, user.id, supplier.id, order_code_1="OC-77", gtin=None)

        result = await SqlAlchemyBoughtItemRepository(db).find_claim_candidate(
            gtin=None, manufacturer_id=supplier.id, order_code_1="OC-77"
        )

        assert result is not None
        assert result.id == target.id

    async def test_no_match_returns_none(self, db, create_user):
        user = await create_user()
        supplier = await _supplier(db, user.id)
        await _bought_item(db, user.id, supplier.id, order_code_1="OC-1", gtin=None)

        result = await SqlAlchemyBoughtItemRepository(db).find_claim_candidate(
            gtin=None, manufacturer_id=supplier.id, order_code_1="OC-DOES-NOT-EXIST"
        )

        assert result is None

    async def test_ambiguous_match_returns_none(self, db, create_user):
        """More than one WEB row shares the same order_code_1 under the
        same manufacturer, so it is never claimed automatically."""
        user = await create_user()
        supplier = await _supplier(db, user.id)
        await _bought_item(db, user.id, supplier.id, order_code_1="OC-DUP", gtin=None)
        await _bought_item(db, user.id, supplier.id, order_code_1="OC-DUP", gtin=None)

        result = await SqlAlchemyBoughtItemRepository(db).find_claim_candidate(
            gtin=None, manufacturer_id=supplier.id, order_code_1="OC-DUP"
        )

        assert result is None

    async def test_excludes_rows_already_linked_to_a_pdm_file(self, db, create_user):
        """Renamed from test_excludes_already_cad_owned_rows: the exclusion
        rule is pdm_file_id being set, not data_source == "CAD". See
        test_claims_cad_sourced_row_without_pdm_link below for the
        add-in-created, still-unlinked counterpart that must be claimed."""
        user = await create_user()
        supplier = await _supplier(db, user.id)
        await _bought_item(
            db,
            user.id,
            supplier.id,
            gtin="9999999999999",
            data_source=DataSource.CAD,
            part_number="PN-CAD-1",
            vault_id="V1",
            pdm_file_id=50,
        )

        result = await SqlAlchemyBoughtItemRepository(db).find_claim_candidate(
            gtin="9999999999999", manufacturer_id=None, order_code_1=None
        )

        assert result is None

    async def test_claims_cad_sourced_row_without_pdm_link(self, db, create_user):
        """A bought item created through the SolidWorks add-in (data_source
        == "CAD" from creation, never linked to a PDM file) can be claimed,
        because the rule filters on pdm_file_id being unset, not on
        data_source == "WEB"."""
        user = await create_user()
        supplier = await _supplier(db, user.id)
        target = await _bought_item(
            db,
            user.id,
            supplier.id,
            gtin="4052568044145",
            data_source=DataSource.CAD,
            part_number="CAD-1001",
        )

        result = await SqlAlchemyBoughtItemRepository(db).find_claim_candidate(
            gtin="4052568044145", manufacturer_id=None, order_code_1=None
        )

        assert result is not None
        assert result.id == target.id


def _made_item_orm(
    creator_id: int, *, revision: str, vault_id: str | None, pdm_file_id: int | None
):
    return MadeItemOrmModel(
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        revision=revision,
        revision_date=None,
        revision_note=None,
        article_name="Bracket",
        status="active",
        data_source="CAD",
        part_number=None,
        material=None,
        mass=None,
        base_size=None,
        note=None,
        weblink=None,
        creator_id=creator_id,
        approver_id=None,
        bought_item_id=None,
        source_item_id=None,
        successor_item_id=None,
        vault_id=vault_id,
        pdm_file_id=pdm_file_id,
    )


def _bought_item_orm(
    creator_id: int, manufacturer_id: int, *, vault_id: str | None, pdm_file_id: int | None
):
    return BoughtItemOrmModel(
        created=datetime(2026, 1, 1, tzinfo=UTC),
        changed=datetime(2026, 1, 1, tzinfo=UTC),
        changes=[],
        archived=False,
        order_code_1="OC-1",
        order_code_2=None,
        gtin=None,
        ean=None,
        tariff_number=None,
        status="active",
        article_name="Widget",
        data_source="CAD",
        part_number=None,
        mass=None,
        successor_item_id=None,
        note=None,
        weblink=None,
        creator_id=creator_id,
        approver_id=None,
        manufacturer_id=manufacturer_id,
        vault_id=vault_id,
        pdm_file_id=pdm_file_id,
    )


class TestMadeItemPdmFilePartialUniqueIndex:
    async def test_duplicate_vault_file_revision_rejected(self, db, create_user):
        user = await create_user()
        db.add(_made_item_orm(user.id, revision="A", vault_id="V1", pdm_file_id=1))
        await db.commit()

        with pytest.raises(IntegrityError):
            db.add(_made_item_orm(user.id, revision="A", vault_id="V1", pdm_file_id=1))
            await db.commit()
        await db.rollback()

    async def test_null_pdm_file_id_rows_repeat_freely(self, db, create_user):
        user = await create_user()
        db.add(_made_item_orm(user.id, revision="A", vault_id=None, pdm_file_id=None))
        db.add(_made_item_orm(user.id, revision="A", vault_id=None, pdm_file_id=None))
        await db.commit()

        count = await count_rows(
            db, select(MadeItemOrmModel).where(MadeItemOrmModel.pdm_file_id.is_(None))
        )
        assert count == 2


class TestBoughtItemPdmFilePartialUniqueIndex:
    async def test_duplicate_vault_file_rejected(self, db, create_user):
        user = await create_user()
        supplier = await _supplier(db, user.id)
        db.add(_bought_item_orm(user.id, supplier.id, vault_id="V1", pdm_file_id=1))
        await db.commit()

        with pytest.raises(IntegrityError):
            db.add(_bought_item_orm(user.id, supplier.id, vault_id="V1", pdm_file_id=1))
            await db.commit()
        await db.rollback()

    async def test_null_pdm_file_id_rows_repeat_freely(self, db, create_user):
        user = await create_user()
        supplier = await _supplier(db, user.id)
        db.add(_bought_item_orm(user.id, supplier.id, vault_id=None, pdm_file_id=None))
        db.add(_bought_item_orm(user.id, supplier.id, vault_id=None, pdm_file_id=None))
        await db.commit()

        count = await count_rows(
            db, select(BoughtItemOrmModel).where(BoughtItemOrmModel.pdm_file_id.is_(None))
        )
        assert count == 2
