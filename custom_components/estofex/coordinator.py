"""Data coordinator for ESTOFEX."""
from __future__ import annotations

import logging
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.update_coordinator import DataUpdateCoordinator, UpdateFailed

from .const import BASE_URL, DEFAULT_SCAN_INTERVAL_MINUTES, LATEST_IMAGE_FILENAME, WWW_DIR

_LOGGER = logging.getLogger(__name__)


@dataclass(slots=True)
class EstofexForecast:
    """Container for the latest ESTOFEX forecast metadata."""

    fcstfile: str | None
    image_url: str | None
    local_image_url: str | None
    issued_at: datetime | None
    valid_until: datetime | None
    forecast_number: str | None
    changed: bool


class EstofexCoordinator(DataUpdateCoordinator[EstofexForecast]):
    """Coordinator that fetches latest ESTOFEX forecast metadata and map."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the coordinator."""
        super().__init__(
            hass,
            _LOGGER,
            name="ESTOFEX",
            update_interval=timedelta(minutes=DEFAULT_SCAN_INTERVAL_MINUTES),
        )
        self._last_fcstfile: str | None = None
        self._force_download = False
        self.last_checked: datetime | None = None
        self.last_successful_update: datetime | None = None
        self.last_changed: datetime | None = None
        self.image_downloaded = False
        self.last_image_downloaded: datetime | None = None
        self.last_http_status: int | None = None
        self.last_list_http_status: int | None = None
        self.last_image_http_status: int | None = None
        self.last_error: str | None = None

    async def async_force_refresh(self) -> None:
        """Request an immediate update and force the map image to download."""
        self._force_download = True
        try:
            await self.async_request_refresh()
        finally:
            self._force_download = False

    async def _async_update_data(self) -> EstofexForecast:
        """Fetch latest data from ESTOFEX."""
        self.last_checked = datetime.now(timezone.utc)
        self.image_downloaded = False
        self.last_http_status = None
        self.last_list_http_status = None
        self.last_image_http_status = None
        self.last_error = None

        try:
            data = await self._fetch_latest_forecast()
        except (ClientError, TimeoutError, OSError, ValueError) as err:
            self.last_error = str(err)
            raise UpdateFailed(f"Error while updating ESTOFEX: {err}") from err

        self.last_successful_update = datetime.now(timezone.utc)
        return data

    async def _fetch_latest_forecast(self) -> EstofexForecast:
        """Fetch the latest forecast id and download its map when needed."""
        session = async_get_clientsession(self.hass)
        list_url = f"{BASE_URL}?list=yes"

        _LOGGER.debug("Checking ESTOFEX for latest forecast")
        async with session.get(list_url, timeout=20) as response:
            self.last_http_status = response.status
            self.last_list_http_status = response.status
            response.raise_for_status()
            html = await response.text()

        fcstfile = self._extract_latest_fcstfile(html)

        if not fcstfile:
            _LOGGER.warning("No ESTOFEX fcstfile found")
            return EstofexForecast(
                fcstfile=None,
                image_url=None,
                local_image_url=None,
                issued_at=None,
                valid_until=None,
                forecast_number=None,
                changed=False,
            )

        image_url = f"{BASE_URL}?lightningmap=yes&fcstfile={fcstfile}"
        changed = fcstfile != self._last_fcstfile
        if changed:
            self.last_changed = datetime.now(timezone.utc)

        should_download = changed or self._force_download or not self._latest_image_exists()

        if should_download:
            await self._download_image(image_url)
            self._last_fcstfile = fcstfile
            self.image_downloaded = True
            self.last_image_downloaded = datetime.now(timezone.utc)
            if self._force_download and not changed:
                _LOGGER.info("Downloaded ESTOFEX forecast map on demand: %s", fcstfile)
            else:
                _LOGGER.info("Downloaded new ESTOFEX forecast map: %s", fcstfile)
        else:
            _LOGGER.debug("ESTOFEX forecast unchanged: %s", fcstfile)

        issued_at, valid_until, forecast_number = self._parse_fcstfile(fcstfile)

        return EstofexForecast(
            fcstfile=fcstfile,
            image_url=image_url,
            local_image_url=f"/local/estofex/{LATEST_IMAGE_FILENAME}",
            issued_at=issued_at,
            valid_until=valid_until,
            forecast_number=forecast_number,
            changed=changed,
        )

    @staticmethod
    def _extract_latest_fcstfile(html: str) -> str | None:
        """Extract the first stormforecast fcstfile from ESTOFEX list HTML."""
        matches = re.findall(r"fcstfile=([^\"'&<>]+stormforecast\.xml)", html)
        return matches[0] if matches else None

    @staticmethod
    def _parse_fcstfile(fcstfile: str) -> tuple[datetime | None, datetime | None, str | None]:
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

    def _latest_image_exists(self) -> bool:
        """Return whether the latest map image exists."""
        return self._latest_image_path().exists()

    async def _download_image(self, image_url: str) -> None:
        """Download the latest forecast map into /config/www/estofex/latest.png."""
        session = async_get_clientsession(self.hass)
        out_file = self._latest_image_path()
        out_file.parent.mkdir(parents=True, exist_ok=True)

        async with session.get(image_url, timeout=20) as response:
            self.last_http_status = response.status
            self.last_image_http_status = response.status
            response.raise_for_status()
            data = await response.read()

        out_file.write_bytes(data)
