"""
Smoke test for the unauthenticated public surface. `public/router.py`
mounts branding.py with no auth dependency at all, used pre-login by the
login screen. `_seed_admin_settings` (conftest.py) does not seed the
branding domain, so this seeds it directly, same pattern as the
security-settings seeding in test_api_key_surface.py.

Also covers default_language (the "Locales" feature): the login screen has
no token and no user yet, so this endpoint is the only place it can learn
which language to render in before anyone signs in, see
branding.py's PublicBrandingResponse docstring comment.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from src.bootstrap.adapters.outbound.persistence.repositories.admin_settings_repository import (
    SqlAlchemyAdminSettingsRepository,
)
from src.modules.platform.domain.entities.admin_settings.branding import AdminBrandingSettings
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.infrastructure.config.settings import cfg


@pytest.mark.smoke
async def test_public_branding_returns_200(db: Session, client: TestClient) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_branding(
        AdminBrandingSettings(
            id=1,
            app_name="Glados",
            app_description=None,
            footer_text=None,
            logo_url=None,
            favicon_url=None,
            logo_key=None,
            favicon_key=None,
            login_background_video_key=None,
        )
    )
    await db.commit()

    resp = await client.get("/api/v1/public/branding")

    assert resp.status_code == 200
    body = resp.json()
    assert body["app_name"] == "Glados"
    assert body["app_description"] is None
    assert body["has_logo"] is False
    # The "Contact & Legal" fields ride along for the footer's link row; the
    # seed leaves them unset, which the footer must read as "no links".
    assert body["contact_email"] is None
    assert body["support_url"] is None
    assert body["imprint_url"] is None
    assert body["privacy_url"] is None
    # `_seed_admin_settings` (conftest.py) seeds admin_general_settings
    # without this column, so this is the migration's server_default path,
    # the same baseline as src/modules/platform/const.py's SERVER_DEFAULT_LANGUAGE.
    assert body["default_language"] == "enGB"
    # Reports put QR codes on their pages that point to this address.
    assert body["domain"] == cfg.domain


async def test_public_branding_reflects_the_configured_default_language(
    db: Session, client: TestClient
) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_branding(
        AdminBrandingSettings(
            id=1,
            app_name="Glados",
            app_description=None,
            footer_text=None,
            logo_url=None,
            favicon_url=None,
            logo_key=None,
            favicon_key=None,
            login_background_video_key=None,
        )
    )
    await db.commit()
    general_repo = SqlAlchemyAdminSettingsRepository(db)
    general = await general_repo.get_general()
    general.default_language = Language.deAT
    await general_repo.save_general(general)
    await db.commit()

    resp = await client.get("/api/v1/public/branding")

    assert resp.status_code == 200
    assert resp.json()["default_language"] == "deAT"


async def test_public_branding_exposes_the_app_description(db: Session, client: TestClient) -> None:
    # The header renders the description as a tagline under the app name, and
    # the header is part of the shell that exists before/without a token, so
    # it has to travel on this unauthenticated call like app_name does.
    await SqlAlchemyAdminSettingsRepository(db).save_branding(
        AdminBrandingSettings(
            id=1,
            app_name="Glados",
            app_description="Production planning for Aperture Science",
            footer_text=None,
            logo_url=None,
            favicon_url=None,
            logo_key=None,
            favicon_key=None,
            login_background_video_key=None,
        )
    )
    await db.commit()

    resp = await client.get("/api/v1/public/branding")

    assert resp.status_code == 200
    assert resp.json()["app_description"] == "Production planning for Aperture Science"


async def test_public_branding_exposes_the_contact_and_legal_fields(
    db: Session, client: TestClient
) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_branding(
        AdminBrandingSettings(
            id=1,
            app_name="Glados",
            app_description=None,
            footer_text=None,
            logo_url=None,
            favicon_url=None,
            logo_key=None,
            favicon_key=None,
            login_background_video_key=None,
        )
    )
    await db.commit()
    general_repo = SqlAlchemyAdminSettingsRepository(db)
    general = await general_repo.get_general()
    general.contact_email = "office@example.com"
    general.support_url = "https://example.com/support"
    general.imprint_url = "https://example.com/imprint"
    general.privacy_url = "https://example.com/privacy"
    await general_repo.save_general(general)
    await db.commit()

    resp = await client.get("/api/v1/public/branding")

    assert resp.status_code == 200
    body = resp.json()
    assert body["contact_email"] == "office@example.com"
    assert body["support_url"] == "https://example.com/support"
    assert body["imprint_url"] == "https://example.com/imprint"
    assert body["privacy_url"] == "https://example.com/privacy"


async def test_public_branding_reports_whether_a_company_logo_exists(
    db: Session, client: TestClient
) -> None:
    # Reports rendered in the browser put the company logo in their header,
    # so the shell needs to know whether one exists before fetching it.
    repo = SqlAlchemyAdminSettingsRepository(db)
    await repo.save_branding(
        AdminBrandingSettings(
            id=1,
            app_name="Glados",
            app_description=None,
            footer_text=None,
            logo_url=None,
            favicon_url=None,
            logo_key=None,
            favicon_key=None,
            login_background_video_key=None,
        )
    )
    await db.commit()

    without = await client.get("/api/v1/public/branding")

    general = await repo.get_general()
    general.company_logo_key = "public/company-logo.png"
    await repo.save_general(general)
    await db.commit()

    with_logo = await client.get("/api/v1/public/branding")

    assert without.json()["has_company_logo"] is False
    assert with_logo.json()["has_company_logo"] is True
    assert with_logo.json()["has_logo"] is False


async def test_the_web_app_manifest_takes_the_branding_name(
    db: Session, client: TestClient
) -> None:
    await SqlAlchemyAdminSettingsRepository(db).save_branding(
        AdminBrandingSettings(
            id=1,
            app_name="Werkstatt",
            app_description=None,
            footer_text=None,
            logo_url=None,
            favicon_url=None,
            logo_key=None,
            favicon_key=None,
            login_background_video_key=None,
        )
    )
    await db.commit()

    resp = await client.get("/api/v1/public/branding/manifest.webmanifest")

    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/manifest+json")
    body = resp.json()
    assert body["name"] == "Werkstatt"
    assert body["start_url"] == "/"
    assert body["display"] == "standalone"
    # Without a description the key is left out rather than sent as null.
    assert "description" not in body
    # No favicon is configured, so the Glados icons stand in.
    assert [icon["sizes"] for icon in body["icons"]] == ["192x192", "512x512"]
