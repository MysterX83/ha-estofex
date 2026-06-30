"""Base entities for ESTOFEX."""
from __future__ import annotations

from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .coordinator import EstofexCoordinator


class EstofexEntity(CoordinatorEntity[EstofexCoordinator]):
    """Base class for ESTOFEX entities."""

    _attr_attribution = "Data provided by ESTOFEX"
    _attr_has_entity_name = True
