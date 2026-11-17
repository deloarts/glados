"""
Finds the towns a weather widget may show, by name within one country, for
the location picker of the screen editor, which searches when asked and
never as the user types. It needs write:infoscreens, as
only someone setting up a screen picks a place, and answers 503 when an
admin switched the weather off, so the backend never calls the service
then.
"""

from src.modules.operations.application.dto.infoscreen_dto import WeatherPlaceResult
from src.modules.operations.domain.errors import WeatherUnavailableError
from src.modules.operations.domain.services import infoscreen_rules
from src.modules.operations.ports.outbound.operations_settings_repository import (
    IOperationsSettingsRepository,
)
from src.modules.operations.ports.outbound.weather_port import IWeatherService
from src.modules.operations.ports.outbound.weather_port import WeatherClientContact
from src.modules.platform.domain.entities.user import User
from src.modules.platform.domain.value_objects.language import Language
from src.modules.platform.ports.outbound.unit_of_work_port import IUnitOfWork

# The service names places in ISO 639-1 languages.
_SERVICE_LANGUAGE: dict[Language, str] = {Language.enGB: "en", Language.deAT: "de"}


class SearchWeatherPlaces:
    def __init__(
        self,
        weather: IWeatherService,
        settings_repo: IOperationsSettingsRepository,
        uow: IUnitOfWork,
    ) -> None:
        self._weather = weather
        self._settings = settings_repo
        self._uow = uow

    async def execute(
        self, actor: User, query: str, country_code: str, language: Language | None
    ) -> list[WeatherPlaceResult]:
        infoscreen_rules.assert_can_write(actor)
        if not (await self._settings.get_security()).enable_infoscreen_weather:
            raise WeatherUnavailableError("The weather is switched off.")
        general = await self._settings.get_general()
        contact = WeatherClientContact(
            email=general.contact_email or None,
            website=general.support_url or general.imprint_url or None,
        )
        # Nothing was written; the connection goes back to the pool before
        # the call to the weather service.
        await self._uow.commit()
        service_language = _SERVICE_LANGUAGE.get(language or Language.enGB, "en")
        places = await self._weather.search_places(
            query.strip(), country_code, service_language, contact
        )
        return [
            WeatherPlaceResult(
                name=place.name,
                region=place.region,
                country_code=place.country_code,
                latitude=place.latitude,
                longitude=place.longitude,
            )
            for place in places
        ]
