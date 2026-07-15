"""Data coordinator for ESTOFEX."""

from __future__ import annotations

import logging
import shutil
from dataclasses import replace
from datetime import UTC, datetime, timedelta
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
from .map_cache import forecast_image_filename, remove_inactive_forecast_maps
from .models import (
    EstofexDiagnostics,
    EstofexForecast,
    EstofexForecastReference,
    EstofexLocalWarning,
    EstofexUpdateData,
)
from .parser import PARSER_VERSION, parse_estofex_forecast, parse_forecast_entries
from .translator import async_summarize_to_dutch, async_translate_to_dutch

_LOGGER = logging.getLogger(__name__)

STATUS_OK = "OK"
STATUS_UPDATING = "Updating"
STATUS_NO_FORECAST = "No forecast"
STATUS_OFFLINE = "Offline"
STATUS_ERROR = "Error"


class EstofexCoordinator(DataUpdateCoordinator[EstofexUpdateData]):
    """Coordinator that refreshes all active ESTOFEX forecasts and state."""

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

    async def _async_update_data(self) -> EstofexUpdateData:
        """Fetch and combine all currently active data from ESTOFEX."""
        started = monotonic()
        previous = self.data
        now = self._utcnow()
        self._prepare_update_cycle(now)

        try:
            data = await self._async_refresh_forecasts(previous, now)
        except EstofexConnectionError as err:
            data = self._handle_offline(err, previous)
        except Exception as err:
            data = self._handle_error(err, previous)

        self.last_update_duration = round(monotonic() - started, 3)
        data = self._finalize_update_data(data, now)
        self._fire_transition_events(previous, data)
        return data

    @property
    def primary_forecast(self) -> EstofexForecast | None:
        """Return the newest active forecast."""
        return self.data.primary_forecast if self.data else None

    @property
    def has_forecast_map(self) -> bool:
        """Return whether the primary forecast has a cached map."""
        forecast = self.primary_forecast
        return bool(forecast and forecast.id and forecast.map_available)

    @property
    def local_warning(self) -> EstofexLocalWarning:
        """Return combined local warning data from every active forecast."""
        return self.data.local_warning if self.data else EstofexLocalWarning()

    @property
    def active_map_cache_count(self) -> int:
        """Return the number of active forecasts with a cached map."""
        if not self.data:
            return 0
        return sum(forecast.map_available for forecast in self.data.forecasts)

    def _prepare_update_cycle(self, now: datetime) -> None:
        """Reset per-cycle diagnostics."""
        self.last_checked = now
        self.image_downloaded = False
        self.last_http_status = None
        self.last_list_http_status = None
        self.last_forecast_http_status = None
        self.last_image_http_status = None
        self.last_error = None
        self._set_status(STATUS_UPDATING, notify=True)

    async def _async_refresh_forecasts(
        self,
        previous: EstofexUpdateData | None,
        now: datetime,
    ) -> EstofexUpdateData:
        """Refresh every forecast which may currently be active."""
        _LOGGER.debug("Checking ESTOFEX for active forecasts")
        list_response = await self._api.async_fetch_forecast_list()
        self.last_http_status = list_response.status
        self.last_list_http_status = list_response.status

        entries = self._parse_forecast_entries(list_response.body)
        active_entries = tuple(entry for entry in entries if entry.is_active(now))
        if not active_entries:
            return await self._async_handle_no_forecast(previous)

        previous_by_id = {
            forecast.id: forecast
            for forecast in (previous.forecasts if previous else ())
            if forecast.id
        }
        forecasts: list[EstofexForecast] = []
        failures: list[str] = []

        for entry in active_entries:
            previous_forecast = previous_by_id.get(entry.forecast_id)
            try:
                if previous_forecast and previous_forecast.is_active(now):
                    forecast = await self._async_prepare_existing_forecast(
                        previous_forecast
                    )
                else:
                    forecast = await self._async_fetch_forecast(entry, now)
            except (EstofexConnectionError, EstofexParseError, OSError) as err:
                failures.append(f"{entry.forecast_id}: {err}")
                _LOGGER.warning(
                    "Could not update ESTOFEX forecast %s: %s",
                    entry.forecast_id,
                    err,
                )
                if previous_forecast and previous_forecast.is_active(now):
                    forecasts.append(previous_forecast)
                continue

            if forecast is not None:
                forecasts.append(forecast)

        if not forecasts:
            message = "; ".join(failures) or "No active forecast could be parsed"
            usable_previous = self._active_previous(previous, now)
            if usable_previous.forecasts:
                return self._handle_error(EstofexParseError(message), usable_previous)
            self.last_error = message
            self._set_status(STATUS_ERROR)
            return EstofexUpdateData()

        candidate = EstofexUpdateData(forecasts=tuple(forecasts))
        old_ids = set(previous.active_forecast_ids if previous else ())
        new_ids = set(candidate.active_forecast_ids)
        added = tuple(
            forecast_id
            for forecast_id in candidate.active_forecast_ids
            if forecast_id not in old_ids
        )
        removed = tuple(
            forecast_id
            for forecast_id in (previous.active_forecast_ids if previous else ())
            if forecast_id not in new_ids
        )
        primary_changed = bool(
            previous and previous.primary_forecast_id != candidate.primary_forecast_id
        )
        changed = bool(added or removed or primary_changed)

        data = replace(
            candidate,
            added_forecast_ids=added,
            removed_forecast_ids=removed,
            changed=changed,
        )
        try:
            await self.hass.async_add_executor_job(self._sync_map_cache, data)
        except OSError as err:
            self.last_error = str(err)
            _LOGGER.error("Could not synchronize ESTOFEX map cache: %s", err)

        if failures:
            self.last_error = "; ".join(failures)
        self.last_successful_update = now
        if changed:
            self.last_changed = now
        self.forecast_source_url = (
            data.primary_forecast.source_url if data.primary_forecast else None
        )
        self._set_status(STATUS_OK)
        return data

    async def _async_handle_no_forecast(
        self,
        previous: EstofexUpdateData | None,
    ) -> EstofexUpdateData:
        """Clear active state after an authoritative empty forecast list."""
        _LOGGER.debug("No active forecast available")
        try:
            await self.hass.async_add_executor_job(self._clear_map_cache)
        except OSError as err:
            self.last_error = str(err)
            self._set_status(STATUS_ERROR)
            _LOGGER.error("Could not clear stale ESTOFEX forecast maps: %s", err)
        else:
            self._set_status(STATUS_NO_FORECAST)
        self.forecast_source_url = None
        removed = previous.active_forecast_ids if previous else ()
        if removed:
            self.last_changed = self._utcnow()
        self.last_successful_update = self._utcnow()
        return EstofexUpdateData(
            removed_forecast_ids=removed,
            changed=bool(removed),
        )

    async def _async_prepare_existing_forecast(
        self,
        previous: EstofexForecast,
    ) -> EstofexForecast:
        """Reuse parsed data and ensure its individual map is cached."""
        forecast_id = previous.id or ""
        path = self._forecast_image_path(forecast_id)
        map_available = await self.hass.async_add_executor_job(path.is_file)
        if not map_available:
            try:
                await self._async_download_map(forecast_id, path)
            except (EstofexConnectionError, OSError) as err:
                self.last_error = str(err)
                _LOGGER.warning(
                    "Could not restore map for ESTOFEX forecast %s: %s",
                    forecast_id,
                    err,
                )
            else:
                map_available = True

        return replace(
            previous,
            changed=False,
            map_url=self._api.forecast_map_url(forecast_id),
            local_map_url=(
                self._forecast_local_map_url(forecast_id) if map_available else None
            ),
            local_map_path=str(path) if map_available else None,
            map_available=map_available,
        )

    async def _async_fetch_forecast(
        self,
        entry: EstofexForecastReference,
        now: datetime,
    ) -> EstofexForecast | None:
        """Fetch, parse, enrich, and cache one forecast independently."""
        forecast_id = entry.forecast_id
        map_url = self._api.forecast_map_url(forecast_id)
        source_url = self._api.forecast_source_url(forecast_id)

        source_response = await self._api.async_fetch_forecast_source(forecast_id)
        self.last_http_status = source_response.status
        self.last_forecast_http_status = source_response.status
        source_url = source_response.url

        forecast = self._parse_forecast_source(
            source_response.body,
            forecast_id,
            map_url,
            source_url,
        )
        if not forecast.is_active(now):
            _LOGGER.debug("Forecast is not active: %s", forecast_id)
            return None

        if not forecast.discussion:
            forecast = await self._async_add_html_discussion(forecast)

        discussion_nl = await async_translate_to_dutch(self.hass, forecast.discussion)
        summary_nl = await async_summarize_to_dutch(self.hass, forecast.discussion)
        path = self._forecast_image_path(forecast_id)
        map_available = await self.hass.async_add_executor_job(path.is_file)
        if not map_available:
            try:
                await self._async_download_map(forecast_id, path)
            except (EstofexConnectionError, OSError) as err:
                self.last_error = str(err)
                _LOGGER.warning(
                    "Forecast %s is usable but its map could not be cached: %s",
                    forecast_id,
                    err,
                )
            else:
                map_available = True

        return replace(
            forecast,
            discussion_nl=discussion_nl,
            summary_nl=summary_nl,
            local_map_url=(
                self._forecast_local_map_url(forecast_id) if map_available else None
            ),
            local_map_path=str(path) if map_available else None,
            changed=True,
            map_available=map_available,
            last_successful_update=now,
        )

    async def _async_add_html_discussion(
        self,
        forecast: EstofexForecast,
    ) -> EstofexForecast:
        """Use the HTML endpoint as a non-fatal discussion fallback."""
        forecast_id = forecast.id or ""
        try:
            response = await self._api.async_fetch_forecast_page(forecast_id)
            html_forecast = self._parse_forecast_source(
                response.body,
                forecast_id,
                forecast.map_url or self._api.forecast_map_url(forecast_id),
                response.url,
            )
        except (EstofexConnectionError, EstofexParseError) as err:
            _LOGGER.debug(
                "No HTML discussion fallback for forecast %s: %s",
                forecast_id,
                err,
            )
            return forecast

        return replace(
            forecast,
            discussion=html_forecast.discussion,
            level_texts=forecast.level_texts or html_forecast.level_texts,
            hazards=forecast.hazards or html_forecast.hazards,
            forecaster=forecast.forecaster or html_forecast.forecaster,
        )

    async def _async_download_map(self, forecast_id: str, path: Path) -> None:
        """Download and cache one forecast map."""
        image_response = await self._api.async_fetch_forecast_map(forecast_id)
        await self.hass.async_add_executor_job(
            self._write_image, path, image_response.body
        )
        self.image_downloaded = True
        self.last_image_downloaded = self._utcnow()
        self.last_http_status = image_response.status
        self.last_image_http_status = image_response.status
        self.last_download_size = image_response.size

    def _handle_offline(
        self,
        err: Exception,
        previous: EstofexUpdateData | None,
    ) -> EstofexUpdateData:
        """Keep previous data and files when ESTOFEX cannot be reached."""
        self.last_error = str(err)
        self._set_status(STATUS_OFFLINE)
        _LOGGER.warning("Website unreachable: %s", err)
        usable_previous = self._active_previous(previous, self._utcnow())
        if usable_previous.forecasts:
            return replace(
                usable_previous,
                added_forecast_ids=(),
                removed_forecast_ids=(),
                changed=False,
            )
        return EstofexUpdateData()

    @staticmethod
    def _active_previous(
        previous: EstofexUpdateData | None,
        now: datetime,
    ) -> EstofexUpdateData:
        """Return only still-valid previously fetched forecasts."""
        if not previous:
            return EstofexUpdateData()
        return EstofexUpdateData(
            forecasts=tuple(
                forecast for forecast in previous.forecasts if forecast.is_active(now)
            ),
            primary_forecast_id=previous.primary_forecast_id,
        )

    def _handle_error(
        self,
        err: Exception,
        previous: EstofexUpdateData | None,
    ) -> EstofexUpdateData:
        """Keep previous data after an unexpected update failure."""
        self.last_error = str(err)
        self._set_status(STATUS_ERROR)
        _LOGGER.error("Error while updating ESTOFEX: %s", err)
        if previous:
            return replace(
                previous,
                added_forecast_ids=(),
                removed_forecast_ids=(),
                changed=False,
            )
        return EstofexUpdateData()

    def _finalize_update_data(
        self,
        data: EstofexUpdateData,
        now: datetime,
    ) -> EstofexUpdateData:
        """Attach local warning evaluation and runtime diagnostics."""
        forecasts = tuple(
            self._finalize_forecast(forecast, now) for forecast in data.forecasts
        )
        return replace(data, forecasts=forecasts)

    def _finalize_forecast(
        self,
        forecast: EstofexForecast,
        now: datetime,
    ) -> EstofexForecast:
        """Attach local evaluation and compact diagnostics to one forecast."""
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
                forecast_age_seconds=self._forecast_age_seconds(forecast, now),
                last_http_response=self.last_http_status,
                last_update_duration=self.last_update_duration,
                last_download_size=self.last_download_size,
                parser_version=PARSER_VERSION,
                forecast_source_url=forecast.source_url,
            ),
        )

    def _fire_transition_events(
        self,
        previous: EstofexUpdateData | None,
        data: EstofexUpdateData,
    ) -> None:
        """Fire events for active-set and combined local warning changes."""
        if data.changed:
            self.hass.bus.async_fire(
                EVENT_FORECAST_UPDATED,
                self._forecast_event_payload(data),
            )

        previous_warning = bool(previous and previous.local_warning.active)
        current_warning = data.local_warning.active
        if not previous_warning and current_warning:
            self.hass.bus.async_fire(
                EVENT_WARNING_STARTED,
                self._warning_event_payload(data),
            )
        elif previous_warning and not current_warning:
            self.hass.bus.async_fire(
                EVENT_WARNING_CLEARED,
                self._warning_event_payload(data),
            )

    def _forecast_event_payload(self, data: EstofexUpdateData) -> dict[str, object]:
        """Return a backwards-compatible active-set change payload."""
        forecast = data.primary_forecast
        return {
            "forecast_id": forecast.id if forecast else None,
            "active_forecast_ids": list(data.active_forecast_ids),
            "added_forecast_ids": list(data.added_forecast_ids),
            "removed_forecast_ids": list(data.removed_forecast_ids),
            "primary_forecast_id": data.primary_forecast_id,
            "issued_at": self._format_datetime(
                forecast.issued_at if forecast else None
            ),
            "valid_until": self._format_datetime(
                forecast.valid_until if forecast else None
            ),
            "levels_present": list(forecast.levels_present) if forecast else [],
            "hazards": [hazard.type for hazard in forecast.hazards] if forecast else [],
            "local_warning": data.local_warning.active,
        }

    def _warning_event_payload(self, data: EstofexUpdateData) -> dict[str, object]:
        """Return a payload based on the newest locally matching forecast."""
        forecast = next(
            (
                item
                for item in data.forecasts
                if item.id in data.local_warning.matching_forecast_ids
            ),
            data.primary_forecast,
        )
        return {
            "forecast_id": forecast.id if forecast else None,
            "active_forecast_ids": list(data.active_forecast_ids),
            "primary_forecast_id": data.primary_forecast_id,
            "issued_at": self._format_datetime(
                forecast.issued_at if forecast else None
            ),
            "valid_until": self._format_datetime(
                forecast.valid_until if forecast else None
            ),
            "level": data.local_warning.level,
            "hazards": [hazard.type for hazard in data.local_warning.hazards],
            "local_warning": data.local_warning.active,
        }

    def _sync_map_cache(self, data: EstofexUpdateData) -> None:
        """Remove inactive map files and update the primary latest alias."""
        expected = {
            self._forecast_image_path(forecast.id)
            for forecast in data.forecasts
            if forecast.id and forecast.map_available
        }
        cache_dir = self._cache_dir()
        remove_inactive_forecast_maps(cache_dir, expected)

        primary = data.primary_forecast
        latest = self._latest_image_path()
        if primary and primary.id and primary.map_available:
            source = self._forecast_image_path(primary.id)
            if source.is_file():
                self._copy_if_changed(source, latest)
                return
        if latest.exists():
            latest.unlink()

    def _clear_map_cache(self) -> None:
        """Remove only map files that are owned by this integration."""
        cache_dir = self._cache_dir()
        remove_inactive_forecast_maps(cache_dir, set())
        latest = self._latest_image_path()
        if latest.exists():
            latest.unlink()

    @staticmethod
    def _copy_if_changed(source: Path, target: Path) -> None:
        """Copy an image only when the alias content differs."""
        if target.is_file() and target.read_bytes() == source.read_bytes():
            return
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source, target)

    @staticmethod
    def _write_image(path: Path, data: bytes) -> None:
        """Write a forecast image to its deterministic cache path."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    def _cache_dir(self) -> Path:
        """Return the integration-owned public map cache directory."""
        return Path(self.hass.config.path(WWW_DIR))

    def _latest_image_path(self) -> Path:
        """Return the backwards-compatible primary map path."""
        return self._cache_dir() / LATEST_IMAGE_FILENAME

    def _forecast_image_path(self, forecast_id: str) -> Path:
        """Return the safe cache path for one forecast."""
        return self._cache_dir() / forecast_image_filename(forecast_id)

    @staticmethod
    def _forecast_local_map_url(forecast_id: str) -> str:
        """Return the public local URL for one forecast map."""
        filename = forecast_image_filename(forecast_id)
        return f"/local/estofex/{filename}"

    @staticmethod
    def _parse_forecast_entries(source: str) -> tuple[EstofexForecastReference, ...]:
        """Parse forecast-list entries and wrap unexpected parser failures."""
        try:
            return parse_forecast_entries(source)
        except Exception as err:
            raise EstofexParseError("Could not parse ESTOFEX forecast list") from err

    @staticmethod
    def _parse_forecast_source(
        source: str,
        forecast_id: str,
        map_url: str,
        source_url: str,
    ) -> EstofexForecast:
        """Parse one forecast source and wrap unexpected parser failures."""
        try:
            return parse_estofex_forecast(
                source,
                forecast_id,
                map_url=map_url,
                source_url=source_url,
            )
        except Exception as err:
            raise EstofexParseError(
                f"Could not parse ESTOFEX forecast source {forecast_id}"
            ) from err

    @staticmethod
    def _forecast_age_seconds(forecast: EstofexForecast, now: datetime) -> int | None:
        """Return forecast age in seconds."""
        if not forecast.issued_at:
            return None
        return int((now - forecast.issued_at).total_seconds())

    @staticmethod
    def _format_datetime(value: datetime | None) -> str | None:
        """Return an ISO formatted datetime for event payloads."""
        return value.isoformat() if value else None

    @staticmethod
    def _utcnow() -> datetime:
        """Return the current UTC time; isolated for deterministic tests."""
        return datetime.now(UTC)

    def _set_status(self, status: str, notify: bool = False) -> None:
        """Set integration status."""
        self.status = status
        if notify:
            self.async_update_listeners()
