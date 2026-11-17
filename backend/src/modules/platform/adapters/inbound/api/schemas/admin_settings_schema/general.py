"""
HTTP request and response schemas for the cross-cutting general settings.
"""

import re
from urllib.parse import urlparse

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.adapters.inbound.api.schemas.base import EntityResponse
from src.modules.platform.domain.services.number_pattern import MAX_PATTERN_LENGTH
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.timezone import Timezone


class UpdateGeneralSettingsRequest(BaseModel):
    company_name: str | None = None
    company_legal_name: str | None = None
    contact_email: str | None = None
    imprint_url: str | None = None
    privacy_url: str | None = None
    support_url: str | None = None
    product_number_pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    project_number_pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    allow_headless_projects: bool | None = None
    empty_value_placeholder: str | None = Field(default=None, max_length=16)
    office_launcher_enabled: bool | None = None
    # None = leave as-is; "" clears the SharePoint tile without disabling
    # the launcher, see UpdateGeneralSettingsCommand.
    office_sharepoint_url: str | None = None

    @field_validator("office_sharepoint_url")
    @classmethod
    def validate_office_sharepoint_url_scheme(cls, v: str | None) -> str | None:
        """The value is admin-supplied and lands in an `href`; rejecting a
        non-http(s) scheme (e.g. "javascript:...") here, as a Pydantic
        field_validator, yields a proper 422. A bare `raise ValueError`
        inside the use case would NOT be caught by exception_handlers.py,
        which only registers a handler for DomainError, and would fall
        through to an unhandled-exception 500 instead. Empty string is
        always allowed, it means "no SharePoint tile". Mirrored on
        UpdateGeneralSettingsCommand per the package's docstring.
        """
        if v and urlparse(v).scheme not in ("http", "https"):
            raise ValueError("office_sharepoint_url must be an http(s) URL, or empty.")
        return v

    # None = leave as-is, like every field above. Presentation only, see
    # AdminGeneralSettings.currency.
    currency: str | None = None

    @field_validator("currency")
    @classmethod
    def validate_currency(cls, v: str | None) -> str | None:
        """Mirrored on UpdateGeneralSettingsCommand per the package's
        docstring. No case normalisation: "eur" and "EURO" are both
        rejected outright rather than coerced.
        """
        if v is not None and not re.fullmatch(r"[A-Z]{3}", v):
            raise ValueError(f"{v!r} is not a valid 3-letter ISO 4217 currency code, e.g. 'EUR'.")
        return v

    # None = leave as-is, like every field above. No "" sentinel here (unlike
    # office_sharepoint_url): a tenant always has *some* default locale.
    default_language: Language | None = None
    default_timezone: str | None = None
    default_date_format: DateFormat | None = None

    @field_validator("default_timezone")
    @classmethod
    def validate_default_timezone(cls, v: str | None) -> str | None:
        """Not an Enum like Language/DateFormat: the valid set is the
        platform's tz database, so it's checked at call time (see
        value_objects/timezone.py). Mirrored on
        UpdateGeneralSettingsCommand per the package's docstring.
        """
        if v is not None and not Timezone.is_valid(v):
            raise ValueError(f"{v!r} is not a valid IANA timezone name (e.g. 'Europe/Vienna').")
        return v


class AdminGeneralSettingsResponse(EntityResponse):
    company_name: str | None
    company_legal_name: str | None
    has_company_logo: bool
    contact_email: str | None
    imprint_url: str | None
    privacy_url: str | None
    support_url: str | None
    product_number_pattern: str
    project_number_pattern: str
    allow_headless_projects: bool
    empty_value_placeholder: str
    office_launcher_enabled: bool
    office_sharepoint_url: str
    currency: str
    default_language: Language
    default_timezone: str
    default_date_format: DateFormat
