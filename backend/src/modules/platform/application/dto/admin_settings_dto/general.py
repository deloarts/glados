"""
Commands and results for the cross-cutting general settings.
"""

import re
from urllib.parse import urlparse

from pydantic import BaseModel
from pydantic import Field
from pydantic import field_validator

from src.modules.platform.application.dto.base import ResultBase
from src.modules.platform.domain.services.number_pattern import MAX_PATTERN_LENGTH
from src.modules.platform.domain.value_objects.date_format import DateFormat
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.domain.value_objects.timezone import Timezone


class UpdateGeneralSettingsCommand(BaseModel):
    company_name: str | None = None
    company_legal_name: str | None = None
    contact_email: str | None = None
    imprint_url: str | None = None
    privacy_url: str | None = None
    support_url: str | None = None
    """Partial update, None means "leave as-is".

    Unlike UpdateFeatureSettingsCommand, which is a full replace, this domain is
    written by two different admin tabs (Numbering owns the patterns, General
    owns the rest), so each must be able to save without clobbering the other's
    fields.
    """

    product_number_pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    project_number_pattern: str | None = Field(default=None, max_length=MAX_PATTERN_LENGTH)
    allow_headless_projects: bool | None = None
    empty_value_placeholder: str | None = Field(default=None, max_length=16)
    office_launcher_enabled: bool | None = None
    # None = leave as-is; "" (not None) clears the SharePoint tile without
    # disabling the launcher, see AdminGeneralSettings.office_sharepoint_url.
    office_sharepoint_url: str | None = None

    @field_validator("office_sharepoint_url")
    @classmethod
    def validate_office_sharepoint_url_scheme(cls, v: str | None) -> str | None:
        """Rejects anything but http(s), mirrored on
        UpdateGeneralSettingsRequest per the schema package's docstring. Raising
        ValueError here (inside a field_validator) becomes a 422 through
        Pydantic/FastAPI's own validation-error handling, unlike a bare
        `raise ValueError` inside a use case, which exception_handlers.py
        has no handler for and would fall through to an unhandled 500.
        Empty string is always allowed, it means "no SharePoint tile".
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
        """ISO 4217 alphabetic code shape, mirrored on
        UpdateGeneralSettingsRequest per the schema package's docstring. No case
        normalisation: "eur" and "EURO" are both rejected outright rather
        than coerced, same reasoning as validate_office_sharepoint_url_scheme
        above for raising here instead of in the use case.
        """
        if v is not None and not re.fullmatch(r"[A-Z]{3}", v):
            raise ValueError(f"{v!r} is not a valid 3-letter ISO 4217 currency code, e.g. 'EUR'.")
        return v

    # None = leave as-is, like every field above. There is deliberately no ""
    # sentinel here (unlike office_sharepoint_url): a tenant always has *some*
    # default locale, "clearing" one back to empty is not a meaningful state.
    default_language: Language | None = None
    default_timezone: str | None = None
    default_date_format: DateFormat | None = None

    @field_validator("default_timezone")
    @classmethod
    def validate_default_timezone(cls, v: str | None) -> str | None:
        """Not an Enum like Language/DateFormat: the valid set is the
        platform's tz database, so it's checked at call time rather than
        declared as a closed set of choices (see value_objects/timezone.py)."""
        if v is not None and not Timezone.is_valid(v):
            raise ValueError(f"{v!r} is not a valid IANA timezone name (e.g. 'Europe/Vienna').")
        return v


class AdminGeneralSettingsResult(ResultBase):
    company_name: str | None
    company_legal_name: str | None
    # Presence flag rather than the key, matching the branding result: the
    # storage key is an internal detail and the UI only needs to know whether
    # to show the image or the upload prompt.
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
