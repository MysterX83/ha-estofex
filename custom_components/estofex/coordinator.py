"""Data coordinator for ESTOFEX."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from time import monotonic

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import (
    BASE_URL,
    DEFAULT_SCAN_INTERVAL_HOURS,
    EVENT_FORECAST_UPDATED,
    EVENT_WARNING_CLEARED,
    EVENT_WARNING_STARTED,
    LATEST_IMAGE_FILENAME,
    WWW_DIR,
)
from .downloader import EstofexDownloader
from .geometry import point_in_polygon
from .models import (
    EstofexDiagnostics,
    EstofexForecast,
    EstofexHazard,
    EstofexLocalWarning,
    EstofexPolygon,
)
from .parser import PARSER_VERSION, parse_estofex_forecast, parse_latest_forecast_id
from .translator import async_summarize_to_dutch, async_translate_to_dutch

_LOGGER = logging.getLogger(__name__)

STATUS_OK = "OK"
STATUS_UPDATING = "Updating"
STATUS_NO_FORECAST = "No forecast"
STATUS_OFFLINE = "Offline"
STATUS_ERROR = "Error"


class EstofexCoordinator(DataUpdateCoordinator[EstofexForecast]):
    """Coordinator that refreshes ESTOFEX forecast data and state."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ESTOFEX",
            update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
        )
        self._downloader = EstofexDownloader(hass)
        self.status = STATUS_UPDATING
        self.last_checked: datetime | None = None
        self.last_successful_update: datetime | None = None
        self.last_changed: datetime | None = None
        self.last_update_duration: float | None = None
        self.image_downloaded = False
        self.last_image_downloaded: datetime | None = None
        self.last_download_size: int | None = None
        self.last_http_status: int | None = None
        self.last_list_http_status: int | None = None
        self.last_forecast_http_status: int | None = None
        self.last_image_http_status: int | None = None
        self.last_error: str | None = None
        self.forecast_source_url: str | None = None

    async def _async_update_data(self) -> EstofexForecast:
        """Fetch latest data from ESTOFEX."""
        started = monotonic()
        previous = self.data
        self._prepare_update_cycle()

        try:
            forecast = await self._async_refresh_forecast(previous)
        except (ClientError, TimeoutError) as err:
            forecast = self._handle_offline(err, previous)
        except Exception as err:
            forecast = self._handle_error(err, previous)

        self.last_update_duration = round(monotonic() - started, 3)
        forecast = self._finalize_forecast(forecast)
        self._fire_transition_events(previous, forecast)
        return forecast

    @property
    def has_forecast_map(self) -> bool:
        """Return whether the coordinator has a forecast map to expose."""
        return bool(self.data and self.data.id and self.data.map_available)

    @property
    def local_warning(self) -> EstofexLocalWarning:
        """Return the current local warning evaluation."""
        if not self.data:
            return EstofexLocalWarning()
        return self.data.local_warning

    def _prepare_update_cycle(self) -> None:
        """Reset per-cycle diagnostics."""
        self.last_checked = datetime.now(timezone.utc)
        self.image_downloaded = False
        self.last_http_status = None
        self.last_list_http_status = None
        self.last_forecast_http_status = None
        self.last_image_http_status = None
        self.last_error = None
        self._set_status(STATUS_UPDATING, notify=True)

    async def _async_refresh_forecast(
        self,
        previous: EstofexForecast | None,
    ) -> EstofexForecast:
        """Refresh the forecast from ESTOFEX."""
        _LOGGER.debug("Checking ESTOFEX for latest forecast")
        list_response = await self._downloader.async_get_text(self._list_url())
        self.last_http_status = list_response.status
        self.last_list_http_status = list_response.status

        fcstfile = parse_latest_forecast_id(list_response.body)
        if not fcstfile:
            return await self._async_handle_no_forecast()

        _LOGGER.debug("Forecast found: %s", fcstfile)
        if previous and previous.id == fcstfile:
            return await self._async_handle_unchanged_forecast(previous)

        return await self._async_handle_new_forecast(fcstfile)

    async def _async_handle_no_forecast(self) -> EstofexForecast:
        """Clear local forecast state when ESTOFEX has no active forecast."""
        _LOGGER.debug("No forecast available")
        try:
            await self._downloader.async_remove_file(self._latest_image_path())
        except OSError as err:
            self.last_error = str(err)
            self._set_status(STATUS_ERROR)
            _LOGGER.error("Could not remove stale ESTOFEX forecast map: %s", err)
        else:
            self._set_status(STATUS_NO_FORECAST)
        self.forecast_source_url = None
        return self._empty_forecast()

    async def _async_handle_unchanged_forecast(
        self,
        previous: EstofexForecast,
    ) -> EstofexForecast:
        """Reuse cached data when the forecast id did not change."""
        _LOGGER.debug("Forecast unchanged: %s", previous.id)
        map_available = previous.map_available
        self.forecast_source_url = (
            previous.diagnostics.forecast_source_url
            or self._forecast_source_url(previous.id or "")
        )

        if not map_available:
            _LOGGER.debug("Cached forecast map missing, downloading current map")
            await self._async_download_map(previous.id or "")
            now = datetime.now(timezone.utc)
            self.last_successful_update = now
            self.last_image_downloaded = now
            map_available = True

        self._set_status(STATUS_OK)
        return replace(
            previous,
            changed=False,
            status=self.status,
            map_available=map_available,
            local_map_url=self._local_map_url() if map_available else None,
            local_map_path=str(self._latest_image_path()) if map_available else None,
            map_url=self._map_url(previous.id) if previous.id else previous.map_url,
        )

    async def _async_handle_new_forecast(self, fcstfile: str) -> EstofexForecast:
        """Fetch, parse, and cache a new ESTOFEX forecast."""
        source_url = self._forecast_source_url(fcstfile)
        map_url = self._map_url(fcstfile)
        self.forecast_source_url = source_url

        _LOGGER.debug("Downloading new forecast source: %s", fcstfile)
        source_response = await self._downloader.async_get_text(source_url)
        self.last_http_status = source_response.status
        self.last_forecast_http_status = source_response.status

        forecast = parse_estofex_forecast(
            source_response.body,
            fcstfile,
            map_url=map_url,
            local_map_url=None,
            local_map_path=None,
        )

        discussion_nl = await async_translate_to_dutch(self.hass, forecast.discussion)
        summary_nl = await async_summarize_to_dutch(self.hass, forecast.discussion)

        _LOGGER.debug("Downloading new forecast map: %s", fcstfile)
        await self._async_download_map(fcstfile)
        now = datetime.now(timezone.utc)
        self.last_changed = now
        self.last_successful_update = now
        self.last_image_downloaded = now
        self._set_status(STATUS_OK)
        _LOGGER.debug("Forecast image updated: %s", fcstfile)

        return replace(
            forecast,
            discussion_nl=discussion_nl,
            summary_nl=summary_nl,
            local_map_url=self._local_map_url(),
            local_map_path=str(self._latest_image_path()),
            changed=True,
            map_available=True,
            status=self.status,
            last_successful_update=self.last_successful_update,
        )

    async def _async_download_map(self, fcstfile: str) -> None:
        """Download and cache the forecast map."""
        image_response = await self._downloader.async_download_file(
            self._map_url(fcstfile),
            self._latest_image_path(),
        )
        self.image_downloaded = True
        self.last_http_status = image_response.status
        self.last_image_http_status = image_response.status
        self.last_download_size = image_response.size

    def _handle_offline(
        self,
        err: Exception,
        previous: EstofexForecast | None,
    ) -> EstofexForecast:
        """Keep previous forecast data when ESTOFEX cannot be reached."""
        self.last_error = str(err)
        self._set_status(STATUS_OFFLINE)
        _LOGGER.warning("Website unreachable: %s", err)
        return replace(previous, changed=False) if previous else self._empty_forecast()

    def _handle_error(
        self,
        err: Exception,
        previous: EstofexForecast | None,
    ) -> EstofexForecast:
        """Expose unexpected update failures while keeping current data."""
        self.last_error = str(err)
        self._set_status(STATUS_ERROR)
        _LOGGER.exception("Unexpected exception while updating ESTOFEX")
        return replace(previous, changed=False) if previous else self._empty_forecast()

    def _finalize_forecast(self, forecast: EstofexForecast) -> EstofexForecast:
        """Attach local warning evaluation and runtime diagnostics."""
        forecast = replace(
            forecast,
            local_warning=self._evaluate_local_warning(forecast),
        )
        return replace(
            forecast,
            status=self.status,
            last_checked=self.last_checked,
            last_successful_update=self.last_successful_update,
            diagnostics=EstofexDiagnostics(
                forecast_age_seconds=self._forecast_age_seconds(forecast),
                last_http_response=self.last_http_status,
                last_update_duration=self.last_update_duration,
                last_download_size=self.last_download_size,
                parser_version=PARSER_VERSION,
                forecast_source_url=self.forecast_source_url,
            ),
        )

    def _evaluate_local_warning(self, forecast: EstofexForecast) -> EstofexLocalWarning:
        """Evaluate the Home Assistant location against forecast polygons."""
        if not forecast.id:
            return EstofexLocalWarning()

        latitude = self.hass.config.latitude
        longitude = self.hass.config.longitude
        if latitude is None or longitude is None:
            return EstofexLocalWarning()

        matching = [
            polygon
            for polygon in forecast.polygons
            if point_in_polygon(latitude, longitude, polygon.coordinates)
        ]
        if not matching:
            return EstofexLocalWarning()

        best_polygon = max(
            matching,
            key=lambda polygon: (polygon.level_number, len(polygon.hazards)),
        )
        return EstofexLocalWarning(
            active=True,
            level=best_polygon.level,
            hazards=self._unique_hazards(matching),
            polygon=best_polygon,
        )

    @staticmethod
    def _unique_hazards(
        polygons: list[EstofexPolygon],
    ) -> tuple[EstofexHazard, ...]:
        """Return de-duplicated hazards from matching polygons."""
        hazards: dict[str, EstofexHazard] = {}
        for polygon in polygons:
            for hazard in polygon.hazards:
                hazards.setdefault(hazard.type, hazard)
        return tuple(hazards.values())

    def _fire_transition_events(
        self,
        previous: EstofexForecast | None,
        forecast: EstofexForecast,
    ) -> None:
        """Fire Home Assistant events for forecast and local warning changes."""
        if forecast.id and forecast.changed:
            self.hass.bus.async_fire(
                EVENT_FORECAST_UPDATED,
                self._forecast_event_payload(forecast),
            )

        previous_warning = bool(previous and previous.local_warning.active)
        current_warning = forecast.local_warning.active

        if not previous_warning and current_warning:
            self.hass.bus.async_fire(
                EVENT_WARNING_STARTED,
                self._warning_event_payload(forecast),
            )
        elif previous_warning and not current_warning:
            self.hass.bus.async_fire(
                EVENT_WARNING_CLEARED,
                self._warning_event_payload(forecast),
            )

    def _forecast_event_payload(self, forecast: EstofexForecast) -> dict[str, object]:
        """Return event payload for a newly detected forecast."""
        return {
            "forecast_id": forecast.id,
            "issued_at": self._format_datetime(forecast.issued_at),
            "valid_until": self._format_datetime(forecast.valid_until),
            "levels_present": list(forecast.levels_present),
            "hazards": [hazard.type for hazard in forecast.hazards],
            "local_warning": forecast.local_warning.active,
        }

    def _warning_event_payload(self, forecast: EstofexForecast) -> dict[str, object]:
        """Return event payload for local warning transitions."""
        return {
            "forecast_id": forecast.id,
            "issued_at": self._format_datetime(forecast.issued_at),
            "valid_until": self._format_datetime(forecast.valid_until),
            "level": forecast.local_warning.level,
            "hazards": [hazard.type for hazard in forecast.local_warning.hazards],
            "local_warning": forecast.local_warning.active,
        }

    def _empty_forecast(self) -> EstofexForecast:
        """Return an empty forecast payload."""
        return EstofexForecast(
            id=None,
            issued_at=None,
            valid_from=None,
            valid_until=None,
            forecaster=None,
            forecast_number=None,
            discussion=None,
            discussion_nl=None,
            summary_nl=None,
            map_url=None,
            local_map_url=None,
            local_map_path=None,
            status=self.status,
            last_checked=self.last_checked,
            last_successful_update=self.last_successful_update,
        )

    def _set_status(self, status: str, notify: bool = False) -> None:
        """Set integration status."""
        self.status = status
        if notify:
            self.async_update_listeners()

    def _latest_image_path(self) -> Path:
        """Return the filesystem path for the latest map image."""
        return Path(self.hass.config.path(WWW_DIR)) / LATEST_IMAGE_FILENAME

    @staticmethod
    def _list_url() -> str:
        """Return the ESTOFEX forecast list URL."""
        return f"{BASE_URL}?list=yes"

    @staticmethod
    def _forecast_source_url(fcstfile: str) -> str:
        """Return the ESTOFEX XML source URL."""
        return f"{BASE_URL}?xml=yes&fcstfile={fcstfile}"

    @staticmethod
    def _map_url(fcstfile: str) -> str:
        """Return the ESTOFEX map URL."""
        return f"{BASE_URL}?lightningmap=yes&fcstfile={fcstfile}"

    @staticmethod
    def _local_map_url() -> str:
        """Return the local Home Assistant map URL."""
        return f"/local/estofex/{LATEST_IMAGE_FILENAME}"

    @staticmethod
    def _forecast_age_seconds(forecast: EstofexForecast) -> int | None:
        """Return forecast age in seconds."""
        if not forecast.issued_at:
            return None
        return int((datetime.now(timezone.utc) - forecast.issued_at).total_seconds())

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        """Return an ISO formatted datetime for event payloads."""
        return value.isoformat() if value else None
