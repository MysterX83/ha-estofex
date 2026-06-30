"""Data coordinator for ESTOFEX."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass, replace
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator

from .const import BASE_URL, DEFAULT_SCAN_INTERVAL_HOURS, LATEST_IMAGE_FILENAME, WWW_DIR
from .parser import (
    EstofexMesoscaleDiscussion,
    ParsedEstofexForecast,
    parse_estofex_forecast,
)
from .translator import async_summarize_to_dutch, async_translate_to_dutch

_LOGGER = logging.getLogger(__name__)

STATUS_OK = "OK"
STATUS_UPDATING = "Updating"
STATUS_NO_FORECAST = "No forecast"
STATUS_OFFLINE = "Offline"
STATUS_ERROR = "Error"


@dataclass(slots=True)
class EstofexForecastData:
    """Container for the latest ESTOFEX forecast data."""

    fcstfile: str | None
    image_url: str | None
    local_image_url: str | None
    local_map_path: str | None
    title: str | None
    issued_at: datetime | None
    valid_from: datetime | None
    valid_until: datetime | None
    forecast_number: str | None
    forecaster: str | None
    discussion_original: str | None
    discussion_nl: str | None
    summary_nl: str | None
    level_texts: tuple[str, ...]
    mesoscale_discussions: tuple[EstofexMesoscaleDiscussion, ...]
    status: str
    last_checked: datetime | None
    last_successful_update: datetime | None
    changed: bool
    map_available: bool

    @property
    def forecast_id(self) -> str | None:
        """Return the ESTOFEX forecast id."""
        return self.fcstfile

    @property
    def map_url(self) -> str | None:
        """Return the remote ESTOFEX map URL."""
        return self.image_url


class EstofexCoordinator(DataUpdateCoordinator[EstofexForecastData]):
    """Coordinator that fetches latest ESTOFEX forecast text and map."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ESTOFEX",
            update_interval=timedelta(hours=DEFAULT_SCAN_INTERVAL_HOURS),
        )
        self.status = STATUS_UPDATING
        self.last_checked: datetime | None = None
        self.last_successful_update: datetime | None = None
        self.last_changed: datetime | None = None
        self.image_downloaded = False
        self.last_image_downloaded: datetime | None = None
        self.last_http_status: int | None = None
        self.last_list_http_status: int | None = None
        self.last_forecast_http_status: int | None = None
        self.last_image_http_status: int | None = None
        self.last_error: str | None = None

    async def _async_update_data(self) -> EstofexForecastData:
        """Fetch latest data from ESTOFEX."""
        self.last_checked = datetime.now(timezone.utc)
        self.image_downloaded = False
        self.last_http_status = None
        self.last_list_http_status = None
        self.last_forecast_http_status = None
        self.last_image_http_status = None
        self.last_error = None
        self._set_status(STATUS_UPDATING, notify=True)

        try:
            fcstfile = await self._fetch_latest_fcstfile()
            if not fcstfile:
                return await self._handle_no_forecast()
            return await self._handle_forecast(fcstfile)
        except (ClientError, TimeoutError) as err:
            return self._handle_offline(err)
        except (OSError, ValueError) as err:
            return self._handle_error(err)

    @property
    def has_forecast_map(self) -> bool:
        """Return whether the coordinator has a forecast map to expose."""
        return bool(self.data and self.data.fcstfile and self.data.map_available)

    def _set_status(self, status: str, notify: bool = False) -> None:
        """Set integration status."""
        self.status = status
        if notify:
            self.async_update_listeners()

    async def _fetch_latest_fcstfile(self) -> str | None:
        """Fetch and parse the latest forecast id from ESTOFEX."""
        session = async_get_clientsession(self.hass)
        list_url = f"{BASE_URL}?list=yes"

        _LOGGER.debug("Checking ESTOFEX for latest forecast")
        async with session.get(list_url, timeout=20) as response:
            self.last_http_status = response.status
            self.last_list_http_status = response.status
            response.raise_for_status()
            html = await response.text()

        return self._extract_latest_fcstfile(html)

    async def _handle_no_forecast(self) -> EstofexForecastData:
        """Clear local forecast state when ESTOFEX has no active forecast."""
        _LOGGER.info("No active ESTOFEX forecast found")
        try:
            await self._remove_latest_image()
        except OSError as err:
            self.last_error = str(err)
            self._set_status(STATUS_ERROR)
            _LOGGER.error("Could not remove stale ESTOFEX forecast map: %s", err)
        else:
            self._set_status(STATUS_NO_FORECAST)
        return self._empty_forecast()

    async def _handle_forecast(self, fcstfile: str) -> EstofexForecastData:
        """Apply download policy for an active ESTOFEX forecast."""
        image_url = f"{BASE_URL}?lightningmap=yes&fcstfile={fcstfile}"
        previous_fcstfile = self.data.fcstfile if self.data else None
        changed = fcstfile != previous_fcstfile
        needs_image_download = changed or not (
            self.data and self.data.map_available
        )
        parsed = await self._fetch_forecast_text(fcstfile)
        discussion_original = parsed.discussion_text
        discussion_nl = await async_translate_to_dutch(
            self.hass, discussion_original
        )
        summary_nl = await async_summarize_to_dutch(self.hass, discussion_original)

        if needs_image_download:
            await self._download_image(image_url)
            self.image_downloaded = True
            downloaded_at = datetime.now(timezone.utc)
            if changed:
                self.last_changed = downloaded_at
            self.last_image_downloaded = downloaded_at
            map_available = True
            _LOGGER.info("Downloaded new ESTOFEX forecast map: %s", fcstfile)
        else:
            map_available = self.data.map_available if self.data else False
            _LOGGER.debug("ESTOFEX forecast unchanged: %s", fcstfile)

        issued_at, valid_until, forecast_number = self._parse_fcstfile(fcstfile)
        issued_at = parsed.issued_at or issued_at
        valid_until = parsed.valid_until or valid_until
        forecast_number = parsed.forecast_number or forecast_number
        self.last_successful_update = datetime.now(timezone.utc)
        self._set_status(STATUS_OK)

        return EstofexForecastData(
            fcstfile=fcstfile,
            image_url=image_url,
            local_image_url=(
                f"/local/estofex/{LATEST_IMAGE_FILENAME}" if map_available else None
            ),
            local_map_path=str(self._latest_image_path()) if map_available else None,
            title=parsed.title,
            issued_at=issued_at,
            valid_from=parsed.valid_from,
            valid_until=valid_until,
            forecast_number=forecast_number,
            forecaster=parsed.forecaster,
            discussion_original=discussion_original,
            discussion_nl=discussion_nl,
            summary_nl=summary_nl,
            level_texts=parsed.level_texts,
            mesoscale_discussions=parsed.mesoscale_discussions,
            status=self.status,
            last_checked=self.last_checked,
            last_successful_update=self.last_successful_update,
            changed=changed,
            map_available=map_available,
        )

    def _handle_offline(self, err: Exception) -> EstofexForecastData:
        """Keep previous forecast data when ESTOFEX cannot be reached."""
        self.last_error = str(err)
        self._set_status(STATUS_OFFLINE)
        _LOGGER.warning("ESTOFEX is unreachable: %s", err)
        return self._current_or_empty_forecast()

    def _handle_error(self, err: Exception) -> EstofexForecastData:
        """Expose unexpected update failures while keeping current data."""
        self.last_error = str(err)
        self._set_status(STATUS_ERROR)
        _LOGGER.error("Error while updating ESTOFEX: %s", err)
        return self._current_or_empty_forecast()

    def _current_or_empty_forecast(self) -> EstofexForecastData:
        """Return current forecast data with fresh runtime status."""
        return replace(
            self.data or self._empty_forecast(),
            status=self.status,
            last_checked=self.last_checked,
            last_successful_update=self.last_successful_update,
        )

    def _empty_forecast(self) -> EstofexForecastData:
        """Return an empty forecast payload."""
        return EstofexForecastData(
            fcstfile=None,
            image_url=None,
            local_image_url=None,
            local_map_path=None,
            title=None,
            issued_at=None,
            valid_from=None,
            valid_until=None,
            forecast_number=None,
            forecaster=None,
            discussion_original=None,
            discussion_nl=None,
            summary_nl=None,
            level_texts=(),
            mesoscale_discussions=(),
            status=self.status,
            last_checked=self.last_checked,
            last_successful_update=self.last_successful_update,
            changed=False,
            map_available=False,
        )

    @staticmethod
    def _extract_latest_fcstfile(html: str) -> str | None:
        """Extract the first stormforecast fcstfile from ESTOFEX list HTML."""
        matches = re.findall(r"fcstfile=([^\"'&<>]+stormforecast\.xml)", html)
        return matches[0] if matches else None

    @staticmethod
    def _parse_fcstfile(
        fcstfile: str,
    ) -> tuple[datetime | None, datetime | None, str | None]:
        """Parse timestamps from a fcstfile name.

        Example: 2026070106_202606291259_1_stormforecast.xml
        - 2026070106 = forecast valid-until timestamp in UTC
        - 202606291259 = issued timestamp in UTC
        - 1 = forecast number
        """
        match = re.match(
            r"(?P<valid>\d{10})_(?P<issued>\d{12})_(?P<number>\d+)_stormforecast\.xml",
            fcstfile,
        )
        if not match:
            return None, None, None

        valid_until = datetime.strptime(match.group("valid"), "%Y%m%d%H").replace(
            tzinfo=timezone.utc
        )
        issued_at = datetime.strptime(match.group("issued"), "%Y%m%d%H%M").replace(
            tzinfo=timezone.utc
        )
        return issued_at, valid_until, match.group("number")

    def _latest_image_path(self) -> Path:
        """Return the filesystem path for the latest map image."""
        return Path(self.hass.config.path(WWW_DIR)) / LATEST_IMAGE_FILENAME

    async def _download_image(self, image_url: str) -> None:
        """Download the latest forecast map into /config/www/estofex/latest.png."""
        session = async_get_clientsession(self.hass)
        out_file = self._latest_image_path()
        await self.hass.async_add_executor_job(self._ensure_latest_image_dir)

        async with session.get(image_url, timeout=20) as response:
            self.last_http_status = response.status
            self.last_image_http_status = response.status
            response.raise_for_status()
            data = await response.read()

        await self.hass.async_add_executor_job(out_file.write_bytes, data)

    async def _fetch_forecast_text(
        self, fcstfile: str
    ) -> ParsedEstofexForecast:
        """Fetch and parse the latest ESTOFEX forecast text."""
        session = async_get_clientsession(self.hass)
        forecast_url = f"{BASE_URL}?fcstfile={fcstfile}&text=yes"

        _LOGGER.debug("Fetching ESTOFEX forecast text: %s", fcstfile)
        async with session.get(forecast_url, timeout=20) as response:
            self.last_http_status = response.status
            self.last_forecast_http_status = response.status
            response.raise_for_status()
            html = await response.text()

        return parse_estofex_forecast(html, fcstfile)

    async def _remove_latest_image(self) -> None:
        """Remove the cached forecast map if it exists."""
        await self.hass.async_add_executor_job(self._remove_latest_image_file)

    def _ensure_latest_image_dir(self) -> None:
        """Create the cached forecast map directory."""
        self._latest_image_path().parent.mkdir(parents=True, exist_ok=True)

    def _remove_latest_image_file(self) -> None:
        """Remove the cached forecast map from disk."""
        image_path = self._latest_image_path()
        if image_path.exists():
            image_path.unlink()
