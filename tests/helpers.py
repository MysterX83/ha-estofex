"""Test helpers for loading ESTOFEX modules without Home Assistant."""

from __future__ import annotations

import importlib.util
import sys
import types
from pathlib import Path
from types import ModuleType

ROOT = Path(__file__).resolve().parents[1]
PACKAGE_NAME = "custom_components.estofex"


def load_estofex_module(module_name: str) -> ModuleType:
    """Load an ESTOFEX module without importing the integration package."""
    _ensure_package()
    full_name = f"{PACKAGE_NAME}.{module_name}"
    if full_name in sys.modules:
        return sys.modules[full_name]

    module_path = ROOT / "custom_components" / "estofex" / f"{module_name}.py"
    spec = importlib.util.spec_from_file_location(full_name, module_path)
    if spec is None or spec.loader is None:
        raise RuntimeError(f"Could not load module {module_name}")

    module = importlib.util.module_from_spec(spec)
    sys.modules[full_name] = module
    spec.loader.exec_module(module)
    return module


def _ensure_package() -> None:
    """Create package placeholders without executing integration __init__."""
    sys.modules.setdefault("custom_components", types.ModuleType("custom_components"))
    package = sys.modules.get(PACKAGE_NAME)
    if package is None:
        package = types.ModuleType(PACKAGE_NAME)
        package.__path__ = []  # type: ignore[attr-defined]
        sys.modules[PACKAGE_NAME] = package


def install_homeassistant_stubs() -> None:
    """Install the small Home Assistant surface needed by unit tests."""
    if "homeassistant.core" in sys.modules:
        return

    homeassistant = types.ModuleType("homeassistant")
    components = types.ModuleType("homeassistant.components")
    binary_sensor_module = types.ModuleType("homeassistant.components.binary_sensor")
    camera_module = types.ModuleType("homeassistant.components.camera")
    sensor_module = types.ModuleType("homeassistant.components.sensor")
    config_entries = types.ModuleType("homeassistant.config_entries")
    core = types.ModuleType("homeassistant.core")
    helpers = types.ModuleType("homeassistant.helpers")
    aiohttp_client = types.ModuleType("homeassistant.helpers.aiohttp_client")
    entity = types.ModuleType("homeassistant.helpers.entity")
    entity_platform = types.ModuleType("homeassistant.helpers.entity_platform")
    entity_registry = types.ModuleType("homeassistant.helpers.entity_registry")
    update_coordinator = types.ModuleType("homeassistant.helpers.update_coordinator")
    aiohttp = types.ModuleType("aiohttp")

    class ClientError(Exception):
        pass

    class HomeAssistant:
        pass

    class ConfigEntry:
        pass

    class Camera:
        def __init__(self) -> None:
            pass

    class BinarySensorEntity:
        pass

    class SensorEntity:
        pass

    class SensorDeviceClass:
        TIMESTAMP = "timestamp"

    class DeviceInfo(dict):
        pass

    class EntityCategory:
        DIAGNOSTIC = "diagnostic"
        CONFIG = "config"

    class DataUpdateCoordinator:
        @classmethod
        def __class_getitem__(cls, item):
            return cls

        def __init__(self, hass, logger, *, name, update_interval) -> None:
            self.hass = hass
            self.data = None
            self._listeners = []

        def async_add_listener(self, listener):
            self._listeners.append(listener)

            def remove_listener() -> None:
                if listener in self._listeners:
                    self._listeners.remove(listener)

            return remove_listener

        def async_update_listeners(self) -> None:
            for listener in tuple(self._listeners):
                listener()

    class CoordinatorEntity:
        def __init__(self, coordinator) -> None:
            self.coordinator = coordinator
            self.entity_id = None
            self.hass = None
            self.removed = False

        @classmethod
        def __class_getitem__(cls, item):
            return cls

        @property
        def available(self) -> bool:
            return True

        @property
        def unique_id(self):
            return getattr(self, "_attr_unique_id", None)

        async def async_remove(self) -> None:
            self.removed = True

    class Registry:
        def __init__(self) -> None:
            self.entities = {}

        def async_get_entity_id(self, platform, domain, unique_id):
            return self.entities.get((platform, domain, unique_id))

        def async_remove(self, entity_id) -> None:
            for key, value in tuple(self.entities.items()):
                if value == entity_id:
                    del self.entities[key]

    registry = Registry()

    aiohttp.ClientError = ClientError
    core.HomeAssistant = HomeAssistant
    config_entries.ConfigEntry = ConfigEntry
    camera_module.Camera = Camera
    binary_sensor_module.BinarySensorEntity = BinarySensorEntity
    sensor_module.SensorEntity = SensorEntity
    sensor_module.SensorDeviceClass = SensorDeviceClass
    entity.DeviceInfo = DeviceInfo
    entity.EntityCategory = EntityCategory
    entity_platform.AddEntitiesCallback = object
    update_coordinator.DataUpdateCoordinator = DataUpdateCoordinator
    update_coordinator.CoordinatorEntity = CoordinatorEntity
    aiohttp_client.async_get_clientsession = lambda hass: None
    entity_registry.async_get = lambda hass: registry
    entity_registry._test_registry = registry
    helpers.entity_registry = entity_registry

    sys.modules.update(
        {
            "aiohttp": aiohttp,
            "homeassistant": homeassistant,
            "homeassistant.components": components,
            "homeassistant.components.binary_sensor": binary_sensor_module,
            "homeassistant.components.camera": camera_module,
            "homeassistant.components.sensor": sensor_module,
            "homeassistant.config_entries": config_entries,
            "homeassistant.core": core,
            "homeassistant.helpers": helpers,
            "homeassistant.helpers.aiohttp_client": aiohttp_client,
            "homeassistant.helpers.entity": entity,
            "homeassistant.helpers.entity_platform": entity_platform,
            "homeassistant.helpers.entity_registry": entity_registry,
            "homeassistant.helpers.update_coordinator": update_coordinator,
        }
    )
