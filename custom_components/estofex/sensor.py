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


def _format_timestamp(value: datetime | None) -> str | None:
    """Format a timestamp for entity attributes."""
    return value.isoformat() if value else None


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
    _attr_icon = "mdi:weather-lightning-rainy"

    @property
    def native_value(self) -> str | None:
        """Return forecast id."""
        return self.coordinator.data.fcstfile if self.coordinator.data else None

    @property
    def extra_state_attributes(self) -> dict[str, str | bool | None]:
        """Return forecast attributes."""
        if not self.coordinator.data:
            return {}
        return {
            "image_url": self.coordinator.data.image_url,
            "local_image_url": self.coordinator.data.local_image_url,
            "local_map_path": self.coordinator.data.local_map_path,
            "changed": self.coordinator.data.changed,
            "map_available": self.coordinator.data.map_available,
        }


class EstofexIssuedAtSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast issue timestamp."""

    _attr_name = "Issued At"
    _attr_unique_id = "estofex_issued_at"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return issued timestamp."""
        return self.coordinator.data.issued_at if self.coordinator.data else None


class EstofexValidUntilSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast valid-until timestamp."""

    _attr_name = "Valid Until"
    _attr_unique_id = "estofex_valid_until"
    _attr_device_class = SensorDeviceClass.TIMESTAMP

    @property
    def native_value(self):
        """Return valid-until timestamp."""
        return self.coordinator.data.valid_until if self.coordinator.data else None


class EstofexForecastNumberSensor(EstofexEntity, SensorEntity):
    """Latest ESTOFEX forecast number."""

    _attr_name = "Forecast Number"
    _attr_unique_id = "estofex_forecast_number"
    _attr_icon = "mdi:numeric"

    @property
    def native_value(self) -> str | None:
        """Return forecast number."""
        return self.coordinator.data.forecast_number if self.coordinator.data else None


class EstofexMapUrlSensor(EstofexEntity, SensorEntity):
    """Local ESTOFEX map url."""

    _attr_name = "Map URL"
    _attr_unique_id = "estofex_map_url"
    _attr_icon = "mdi:map"

    @property
    def native_value(self) -> str | None:
        """Return local image url."""
        return self.coordinator.data.local_image_url if self.coordinator.data else None


class EstofexDiscussionSensor(EstofexEntity, SensorEntity):
    """Original ESTOFEX forecast discussion text."""

    _attr_name = "Discussion"
    _attr_unique_id = "estofex_discussion"
    _attr_icon = "mdi:text-box-outline"

    @property
    def native_value(self) -> str:
        """Return a short discussion availability state."""
        data = self.coordinator.data
        if not data or not data.fcstfile:
            return "No forecast"
        if data.discussion_original:
            return "Available"
        return "Unavailable"

    @property
    def extra_state_attributes(self):
        """Return parsed forecast discussion attributes."""
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "original_text": data.discussion_original,
            "level_texts": list(data.level_texts),
            "forecaster": data.forecaster,
            "issued_at": _format_timestamp(data.issued_at),
            "valid_from": _format_timestamp(data.valid_from),
            "valid_until": _format_timestamp(data.valid_until),
            "forecast_number": data.forecast_number,
            "forecast_id": data.forecast_id,
        }


class EstofexLocalLevelSensor(EstofexEntity, SensorEntity):
    """Highest ESTOFEX warning level for the configured Home Assistant location."""

    _attr_name = "Local Level"
    _attr_unique_id = "estofex_local_level"
    _attr_icon = "mdi:alert"

    @property
    def native_value(self) -> str:
        """Return the highest local warning level."""
        data = self.coordinator.data
        if not data or not data.id:
            return "None"
        return data.local_level or "None"

    @property
    def extra_state_attributes(self):
        """Return local level context."""
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "forecast_id": data.id,
            "highest_forecast_level": data.highest_level,
            "local_warning": data.local_warning.active,
            "hazards": data.local_warning.hazard_labels,
            "issued_at": _format_timestamp(data.issued_at),
            "valid_until": _format_timestamp(data.valid_until),
        }


class EstofexLocalSummarySensor(EstofexEntity, SensorEntity):
    """Concise local ESTOFEX forecast summary."""

    _attr_name = "Local Summary"
    _attr_unique_id = "estofex_local_summary"
    _attr_icon = "mdi:text-box-search-outline"

    @property
    def native_value(self) -> str:
        """Return a concise local forecast summary."""
        data = self.coordinator.data
        if not data or not data.id:
            return "No forecast"
        return data.local_summary()

    @property
    def extra_state_attributes(self):
        """Return local summary context."""
        data = self.coordinator.data
        if not data:
            return {}
        return {
            "forecast_id": data.id,
            "level": data.local_level,
            "hazards": data.local_warning.hazard_labels,
            "valid_until": _format_timestamp(data.valid_until),
            "summary_nl_available": bool(data.summary_nl),
        }


class EstofexSummaryNlSensor(EstofexEntity, SensorEntity):
    """Dutch practical summary of the ESTOFEX discussion."""

    _attr_name = "Summary NL"
    _attr_unique_id = "estofex_summary_nl"
    _attr_icon = "mdi:text-box-check-outline"

    @property
    def native_value(self) -> str:
        """Return a short Dutch summary availability state."""
        data = self.coordinator.data
        if not data or not data.fcstfile:
            return "No forecast"
        if data.summary_nl:
            return "Available"
        return "Unavailable"

    @property
    def extra_state_attributes(self):
        """Return Dutch summary attributes."""
        data = self.coordinator.data
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
    _attr_icon = "mdi:translate"

    @property
    def native_value(self) -> str:
        """Return a short Dutch discussion availability state."""
        data = self.coordinator.data
        if not data or not data.fcstfile:
            return "No forecast"
        if data.discussion_nl:
            return "Available"
        return "Unavailable"

    @property
    def extra_state_attributes(self):
        """Return Dutch discussion attributes."""
        data = self.coordinator.data
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
                self.coordinator.data.diagnostics.forecast_age_seconds
                if self.coordinator.data
                else None
            ),
            "last_update_duration": self.coordinator.last_update_duration,
            "last_download_size": self.coordinator.last_download_size,
            "parser_version": (
                self.coordinator.data.diagnostics.parser_version
                if self.coordinator.data
                else None
            ),
            "forecast_source_url": self.coordinator.forecast_source_url,
        }
