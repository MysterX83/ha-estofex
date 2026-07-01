"""Base entities for ESTOFEX."""
from __future__ import annotations

from typing import TYPE_CHECKING

from homeassistant.helpers.entity import DeviceInfo
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN

if TYPE_CHECKING:
    from .coordinator import EstofexCoordinator


class EstofexEntity(CoordinatorEntity[EstofexCoordinator]):
    """Base class for ESTOFEX entities."""

    _attr_attribution = "Data provided by ESTOFEX"
    _attr_has_entity_name = True

    @property
    def device_info(self) -> DeviceInfo:
        """Return ESTOFEX device information."""
        return DeviceInfo(
            identifiers={(DOMAIN, "estofex")},
            manufacturer="ESTOFEX",
            name="ESTOFEX",
        )
