"""Sensor platform for ESTOFEX."""

from __future__ import annotations

from datetime import datetime

from homeassistant.components.sensor import SensorDeviceClass, SensorEntity
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from .const import DOMAIN
from .coordinator import EstofexCoordinator
from .entity import EstofexEntity
from .models import EstofexForecast


def _format_timestamp(value: datetime | None) -> str | None:
    """Format a timestamp for entity attributes."""
    return value.isoformat() if value else None


def _primary(coordinator: EstofexCoordinator) -> EstofexForecast | None:
    """Return the primary forecast for backwards-compatible sensors."""
    return coordinator.primary_forecast


async def async_setup_entry(
    hass: HomeAssistant,
    entry: ConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up ESTOFEX sensors."""
    coordinator: EstofexCoordinator = hass.data[DOMAIN][entry.entry_id]

    async_add_entities(
        [
            EstofexForecastIdSensor(coordinator),
            EstofexActiveForecastsSensor(coordinator),
            EstofexIssuedAtSensor(coordinator),
            EstofexValidUntilSensor(coordinator),
            EstofexForecastNumberSensor(coordinator),
            EstofexMapUrlSensor(coordinator),
            EstofexLocalLevelSensor(coordinator),
            EstofexLocalSummarySensor(coordinator),
            EstofexDiscussionSensor(coordinator),
            EstofexSummaryNlSensor(coordinator),
            EstofexDiscussionNlSensor(coordinator),
            EstofexLastCheckedSensor(coordinator),
            EstofexLastSuccessfulUpdateSensor(coordinator),
            EstofexLastChangedSensor(coordinator),
            EstofexImageDownloadedSensor(coordinator),
            EstofexHttpStatusSensor(coordinator),
            EstofexStatusSensor(coordinator),
        ]
    )


class EstofexForecastIdSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast id."""

    _attr_name = "Forecast ID"
    _attr_unique_id = "estofex_forecast_id"
    _attr_translation_key = "forecast_id"
    _attr_icon = "mdi:weather-lightning-rainy"

    @property
    def native_value(self) -> str | None:
        """Return forecast id."""
        forecast = _primary(self.coordinator)
        return forecast.fcstfile if forecast else None

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        """Return forecast attributes."""
        forecast = _primary(self.coordinator)
        if not forecast:
            return {}
        return {
            "image_url": forecast.image_url,
            "local_image_url": forecast.local_image_url,
            "changed": bool(self.coordinator.data and self.coordinator.data.changed),
            "map_available": forecast.map_available,
        }


class EstofexActiveForecastsSensor(EstofexEntity, SensorEntity):
    """Number and compact metadata of all active forecasts."""

    _attr_name = "Active Forecasts"
    _attr_unique_id = "estofex_active_forecasts"
    _attr_translation_key = "active_forecasts"
    _attr_icon = "mdi:weather-lightning-rainy"

    @property
    def native_value(self) -> int:
        """Return the number of active forecasts."""
        return self.coordinator.data.forecast_count if self.coordinator.data else 0

    @property
    def extra_state_attributes(self):
        """Return compact active forecast metadata only."""
        data = self.coordinator.data
        if not data:
            return {
                "forecast_ids": [],
                "forecast_count": 0,
                "primary_forecast_id": None,
                "forecasts": [],
            }
        return {
            "forecast_ids": list(data.active_forecast_ids),
            "forecast_count": data.forecast_count,
            "primary_forecast_id": data.primary_forecast_id,
            "forecasts": [
                {
                    "forecast_id": forecast.id,
                    "forecast_number": forecast.forecast_number,
                    "issued_at": _format_timestamp(forecast.issued_at),
                    "valid_until": _format_timestamp(forecast.valid_until),
                    "map_url": forecast.local_map_url,
                    "is_primary": forecast.id == data.primary_forecast_id,
                }
                for forecast in data.forecasts
            ],
        }


class EstofexIssuedAtSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast issue timestamp."""

    _attr_name = "Issued At"
    _attr_unique_id = "estofex_issued_at"
    _attr_translation_key = "issued_at"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return issued timestamp."""
        forecast = _primary(self.coordinator)
        return forecast.issued_at if forecast else None


class EstofexValidUntilSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast valid-until timestamp."""

    _attr_name = "Valid Until"
    _attr_unique_id = "estofex_valid_until"
    _attr_translation_key = "valid_until"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return valid-until timestamp."""
        forecast = _primary(self.coordinator)
        return forecast.valid_until if forecast else None


class EstofexForecastNumberSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast number."""

    _attr_name = "Forecast Number"
    _attr_unique_id = "estofex_forecast_number"
    _attr_translation_key = "forecast_number"
    _attr_icon = "mdi:numeric"

    @property
    def native_value(self) -> str | None:
        """Return forecast number."""
        forecast = _primary(self.coordinator)
        return forecast.forecast_number if forecast else None


class EstofexMapUrlSensor(EstofexEntity, SensorEntity):
    """Local ESTOFEX map url."""

    _attr_name = "Map URL"
    _attr_unique_id = "estofex_map_url"
    _attr_translation_key = "map_url"
    _attr_icon = "mdi:map"

    @property
    def native_value(self) -> str | None:
        """Return local image url."""
        forecast = _primary(self.coordinator)
        return forecast.local_image_url if forecast else None


class EstofexDiscussionSensor(EstofexEntity, SensorEntity):
    """Original ESTOFEX forecast discussion text."""

    _attr_name = "Discussion"
    _attr_unique_id = "estofex_discussion"
    _attr_translation_key = "discussion"
    _attr_icon = "mdi:text-box-outline"

    @property
    def native_value(self) -> str:
        """Return a short discussion availability state."""
        data = _primary(self.coordinator)
        if not data or not data.fcstfile:
            return "No forecast"
        if data.discussion_original:
            return "Available"
        return "Unavailable"

    @property
    def extra_state_attributes(self):
        """Return parsed forecast discussion attributes."""
        data = _primary(self.coordinator)
        if not data:
            return {}
        return {
            "discussion": data.discussion_original,
            "discussion_markdown": data.discussion_markdown,
            "text": data.discussion_original,
            "original_text": data.discussion_original,
            "forecaster": data.forecaster,
            "issued_at": _format_timestamp(data.issued_at),
            "valid_until": _format_timestamp(data.valid_until),
            "forecast_number": data.forecast_number,
            "forecast_id": data.forecast_id,
            "source_url": data.source_url,
            "character_count": len(data.discussion_original or ""),
        }


class EstofexLocalLevelSensor(EstofexEntity, SensorEntity):
    """Highest ESTOFEX warning level for the configured Home Assistant location."""

    _attr_name = "Local Level"
    _attr_unique_id = "estofex_local_level"
    _attr_translation_key = "local_level"
    _attr_icon = "mdi:alert"

    @property
    def native_value(self) -> str:
        """Return the highest local warning level."""
        data = self.coordinator.data
        if not data or not data.primary_forecast:
            return "None"
        return data.local_warning.level or "None"

    @property
    def extra_state_attributes(self):
        """Return local level context."""
        data = self.coordinator.data
        forecast = _primary(self.coordinator)
        if not data:
            return {}
        return {
            "forecast_id": forecast.id if forecast else None,
            "matching_forecast_ids": list(data.local_warning.matching_forecast_ids),
            "highest_forecast_level": forecast.highest_level if forecast else None,
            "local_warning": data.local_warning.active,
            "hazards": data.local_warning.hazard_labels,
            "issued_at": _format_timestamp(forecast.issued_at if forecast else None),
            "valid_until": _format_timestamp(
                forecast.valid_until if forecast else None
            ),
        }


class EstofexLocalSummarySensor(EstofexEntity, SensorEntity):
    """Concise local ESTOFEX forecast summary."""

    _attr_name = "Local Summary"
    _attr_unique_id = "estofex_local_summary"
    _attr_translation_key = "local_summary"
    _attr_icon = "mdi:text-box-search-outline"

    @property
    def native_value(self) -> str:
        """Return a concise local forecast summary."""
        data = self.coordinator.data
        if not data or not data.primary_forecast:
            return "No forecast"
        warning = data.local_warning
        if not warning.active:
            return "No local ESTOFEX warning."
        return warning.level or "Thunderstorm area"

    @property
    def extra_state_attributes(self):
        """Return local summary context."""
        data = self.coordinator.data
        forecast = _primary(self.coordinator)
        if not data:
            return {}
        return {
            "forecast_id": forecast.id if forecast else None,
            "matching_forecast_ids": list(data.local_warning.matching_forecast_ids),
            "level": data.local_warning.level,
            "hazards": data.local_warning.hazard_labels,
            "valid_until": _format_timestamp(
                forecast.valid_until if forecast else None
            ),
            "summary_nl_available": bool(forecast and forecast.summary_nl),
        }


class EstofexSummaryNlSensor(EstofexEntity, SensorEntity):
    """Dutch practical summary of the ESTOFEX discussion."""

    _attr_name = "Summary NL"
    _attr_unique_id = "estofex_summary_nl"
    _attr_translation_key = "summary_nl"
    _attr_icon = "mdi:text-box-check-outline"

    @property
    def native_value(self) -> str:
        """Return a short Dutch summary availability state."""
        data = _primary(self.coordinator)
        if not data or not data.fcstfile:
            return "No forecast"
        if data.summary_nl:
            return "Available"
        return "Unavailable"

    @property
    def extra_state_attributes(self):
        """Return Dutch summary attributes."""
        data = _primary(self.coordinator)
        if not data:
            return {}
        return {
            "summary_text": data.summary_nl,
            "source_available": bool(data.discussion_original),
            "forecast_id": data.forecast_id,
            "issued_at": _format_timestamp(data.issued_at),
            "valid_until": _format_timestamp(data.valid_until),
        }


class EstofexDiscussionNlSensor(EstofexEntity, SensorEntity):
    """Dutch translation of the ESTOFEX discussion."""

    _attr_name = "Discussion NL"
    _attr_unique_id = "estofex_discussion_nl"
    _attr_translation_key = "discussion_nl"
    _attr_icon = "mdi:translate"

    @property
    def native_value(self) -> str:
        """Return a short Dutch discussion availability state."""
        data = _primary(self.coordinator)
        if not data or not data.fcstfile:
            return "No forecast"
        if data.discussion_nl:
            return "Available"
        return "Unavailable"

    @property
    def extra_state_attributes(self):
        """Return Dutch discussion attributes."""
        data = _primary(self.coordinator)
        if not data:
            return {}
        return {
            "translated_text": data.discussion_nl,
            "source_available": bool(data.discussion_original),
            "forecast_id": data.forecast_id,
            "issued_at": _format_timestamp(data.issued_at),
            "valid_until": _format_timestamp(data.valid_until),
        }


class EstofexLastCheckedSensor(EstofexEntity, SensorEntity):
    """Timestamp of the last ESTOFEX update attempt."""

    _attr_name = "Last Checked"
    _attr_unique_id = "estofex_last_checked"
    _attr_translation_key = "last_checked"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Return last checked timestamp."""
        return self.coordinator.last_checked


class EstofexLastSuccessfulUpdateSensor(EstofexEntity, SensorEntity):
    """Timestamp of the last successful ESTOFEX update."""

    _attr_name = "Last Successful Update"
    _attr_unique_id = "estofex_last_successful_update"
    _attr_translation_key = "last_successful_update"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Return last successful update timestamp."""
        return self.coordinator.last_successful_update


class EstofexLastChangedSensor(EstofexEntity, SensorEntity):
    """Timestamp of the last detected forecast change."""

    _attr_name = "Last Changed"
    _attr_unique_id = "estofex_last_changed"
    _attr_translation_key = "last_changed"
    _attr_device_class = SensorDeviceClass.TIMESTAMP
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self):
        """Return last changed timestamp."""
        return self.coordinator.last_changed


class EstofexImageDownloadedSensor(EstofexEntity, SensorEntity):
    """Whether the latest update downloaded a map image."""

    _attr_name = "Image Downloaded"
    _attr_unique_id = "estofex_image_downloaded"
    _attr_translation_key = "image_downloaded"
    _attr_icon = "mdi:image-sync"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return whether an image was downloaded during the latest update."""
        return "yes" if self.coordinator.image_downloaded else "no"

    @property
    def extra_state_attributes(self):
        """Return image download diagnostics."""
        return {
            "last_image_downloaded": _format_timestamp(
                self.coordinator.last_image_downloaded
            ),
        }


class EstofexHttpStatusSensor(EstofexEntity, SensorEntity):
    """HTTP status from the latest ESTOFEX request."""

    _attr_name = "HTTP Status"
    _attr_unique_id = "estofex_http_status"
    _attr_translation_key = "http_status"
    _attr_icon = "mdi:web-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> int | None:
        """Return last HTTP status."""
        return self.coordinator.last_http_status

    @property
    def extra_state_attributes(self):
        """Return detailed HTTP status diagnostics."""
        return {
            "list_http_status": self.coordinator.last_list_http_status,
            "forecast_http_status": self.coordinator.last_forecast_http_status,
            "image_http_status": self.coordinator.last_image_http_status,
        }


class EstofexStatusSensor(EstofexEntity, SensorEntity):
    """Status of the latest ESTOFEX update."""

    _attr_name = "Status"
    _attr_unique_id = "estofex_status"
    _attr_translation_key = "status"
    _attr_icon = "mdi:cloud-sync"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def native_value(self) -> str:
        """Return update status."""
        return self.coordinator.status

    @property
    def extra_state_attributes(self):
        """Return update diagnostics."""
        return {
            "last_error": self.coordinator.last_error,
            "last_checked": _format_timestamp(self.coordinator.last_checked),
            "last_successful_update": _format_timestamp(
                self.coordinator.last_successful_update
            ),
            "last_changed": _format_timestamp(self.coordinator.last_changed),
            "image_downloaded": self.coordinator.image_downloaded,
            "last_image_downloaded": _format_timestamp(
                self.coordinator.last_image_downloaded
            ),
            "last_http_status": self.coordinator.last_http_status,
            "list_http_status": self.coordinator.last_list_http_status,
            "forecast_http_status": self.coordinator.last_forecast_http_status,
            "image_http_status": self.coordinator.last_image_http_status,
            "forecast_age_seconds": (
                self.coordinator.primary_forecast.diagnostics.forecast_age_seconds
                if self.coordinator.primary_forecast
                else None
            ),
            "last_update_duration": self.coordinator.last_update_duration,
            "last_download_size": self.coordinator.last_download_size,
            "parser_version": (
                self.coordinator.primary_forecast.diagnostics.parser_version
                if self.coordinator.primary_forecast
                else None
            ),
            "forecast_source_url": self.coordinator.forecast_source_url,
        }
