"""The branded parts of the web app manifest an installed Glados is launched from."""

from src.modules.platform.application.dto.base import ResultModel


class WebAppManifestResult(ResultModel):
    """The app name and description from the branding settings, and the
    favicon as the install icon when it is large enough to serve as one.
    `favicon_type` and `favicon_sizes` are both set or both None."""

    name: str
    description: str | None
    favicon_type: str | None
    favicon_sizes: str | None
