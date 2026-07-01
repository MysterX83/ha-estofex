"""Data coordinator for ESTOFEX."""
from __future__ import annotations

from dataclasses import replace
from datetime import datetime, timedelta, timezone
import logging
from pathlib import Path
from time import monotonic

from homeassistant.core import HomeAssistant
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .api import EstofexApiClient
from .const import (
    DEFAULT_SCAN_INTERVAL_HOURS,
    EVENT_FORECAST_UPDATED,
    EVENT_WARNING_CLEARED,
    EVENT_WARNING_STARTED,
    LATEST_IMAGE_FILENAME,
    WWW_DIR,
)
from .exceptions import EstofexConnectionError, EstofexParseError
from .geometry import evaluate_location_warning
from .models import (
    EstofexDiagnostics,
    EstofexForecast,
    EstofexLocalWarning,
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
        self._api = EstofexApiClient(hass)
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
        except EstofexConnectionError as err:
            forecast = self._handle_offline(err, previous)
        except EstofexParseError as err:
            forecast = self._handle_error(err, previous)
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
        list_response = await self._api.async_fetch_forecast_list()
        self.last_http_status = list_response.status
        self.last_list_http_status = list_response.status

        fcstfile = self._parse_latest_forecast_id(list_response.body)
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
            await self._async_remove_latest_image()
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
            or self._api.forecast_source_url(previous.id or "")
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
            map_url=(
                self._api.forecast_map_url(previous.id)
                if previous.id
                else previous.map_url
            ),
        )

    async def _async_handle_new_forecast(self, fcstfile: str) -> EstofexForecast:
        """Fetch, parse, and cache a new ESTOFEX forecast."""
        map_url = self._api.forecast_map_url(fcstfile)
        self.forecast_source_url = self._api.forecast_source_url(fcstfile)

        _LOGGER.debug("Downloading new forecast source: %s", fcstfile)
        source_response = await self._api.async_fetch_forecast_source(fcstfile)
        self.last_http_status = source_response.status
        self.last_forecast_http_status = source_response.status
        self.forecast_source_url = source_response.url

        forecast = self._parse_forecast_source(source_response.body, fcstfile, map_url)

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
        image_response = await self._api.async_fetch_forecast_map(fcstfile)
        await self.hass.async_add_executor_job(
            self._write_latest_image,
            image_response.body,
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
            local_warning=evaluate_location_warning(
                self.hass.config.latitude,
                self.hass.config.longitude,
                forecast.polygons,
            ),
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
    def _local_map_url() -> str:
        """Return the local Home Assistant map URL."""
        return f"/local/estofex/{LATEST_IMAGE_FILENAME}"

    async def _async_remove_latest_image(self) -> None:
        """Remove the cached forecast map if it exists."""
        await self.hass.async_add_executor_job(self._remove_latest_image_file)

    def _write_latest_image(self, data: bytes) -> None:
        """Write the latest forecast map to disk."""
        image_path = self._latest_image_path()
        image_path.parent.mkdir(parents=True, exist_ok=True)
        image_path.write_bytes(data)

    def _remove_latest_image_file(self) -> None:
        """Remove the cached forecast map from disk."""
        image_path = self._latest_image_path()
        if image_path.exists():
            image_path.unlink()

    @staticmethod
    def _parse_latest_forecast_id(html: str) -> str | None:
        """Parse the latest forecast id, raising a domain error on failure."""
        try:
            return parse_latest_forecast_id(html)
        except Exception as err:
            raise EstofexParseError("Could not parse ESTOFEX forecast list") from err

    @staticmethod
    def _parse_forecast_source(
        source: str,
        fcstfile: str,
        map_url: str,
    ) -> EstofexForecast:
        """Parse a forecast source, raising a domain error on failure."""
        try:
            return parse_estofex_forecast(
                source,
                fcstfile,
                map_url=map_url,
                local_map_url=None,
                local_map_path=None,
            )
        except Exception as err:
            raise EstofexParseError(
                f"Could not parse ESTOFEX forecast source {fcstfile}"
            ) from err

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
