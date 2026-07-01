"""Domain models for ESTOFEX forecasts."""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime


HAZARD_LARGE_HAIL = "large_hail"
HAZARD_SEVERE_WIND = "severe_wind"
HAZARD_EXCESSIVE_RAIN = "excessive_rain"
HAZARD_TORNADO = "tornado"
HAZARD_FLASH_FLOOD = "flash_flood"

HAZARD_LABELS = {
    HAZARD_LARGE_HAIL: "Large hail",
    HAZARD_SEVERE_WIND: "Severe wind gusts",
    HAZARD_EXCESSIVE_RAIN: "Heavy rainfall",
    HAZARD_TORNADO: "Tornado risk",
    HAZARD_FLASH_FLOOD: "Flash flooding",
}


@dataclass(frozen=True, slots=True)
class EstofexHazard:
    """A normalized forecast hazard."""

    type: str
    severity: str | None = None
    probability: str | None = None

    @property
    def label(self) -> str:
        """Return a human-readable hazard label."""
        return HAZARD_LABELS.get(self.type, self.type.replace("_", " ").title())


@dataclass(frozen=True, slots=True)
class EstofexPolygon:
    """A forecast polygon with optional hazard interpretation."""

    level: str | None
    coordinates: tuple[tuple[float, float], ...]
    hazards: tuple[EstofexHazard, ...] = ()
    region: str | None = None
    description: str | None = None
    risk_type: str | None = None

    @property
    def level_number(self) -> int:
        """Return the numeric ESTOFEX warning level."""
        if not self.level or not self.level.lower().startswith("level "):
            return 0
        try:
            return int(self.level.split()[1])
        except (IndexError, ValueError):
            return 0

    def as_attribute(self) -> dict[str, object]:
        """Return a Home Assistant attribute-safe representation."""
        return {
            "level": self.level,
            "risk_type": self.risk_type,
            "region": self.region,
            "description": self.description,
            "hazards": [hazard.label for hazard in self.hazards],
            "coordinates": [
                {"latitude": lat, "longitude": lon}
                for lat, lon in self.coordinates
            ],
        }


@dataclass(frozen=True, slots=True)
class EstofexDiscussion:
    """A forecast discussion and optional translated forms."""

    original: str | None = None
    discussion_nl: str | None = None
    summary_nl: str | None = None
    level_texts: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class EstofexMesoscaleDiscussion:
    """A future-ready ESTOFEX Mesoscale Discussion model."""

    id: str | None = None
    issued: datetime | None = None
    area: str | None = None
    discussion: str | None = None
    discussion_nl: str | None = None
    summary_nl: str | None = None


@dataclass(frozen=True, slots=True)
class EstofexLocalWarning:
    """Local warning evaluation for the Home Assistant configured location."""

    active: bool = False
    level: str | None = None
    hazards: tuple[EstofexHazard, ...] = ()
    polygon: EstofexPolygon | None = None

    @property
    def hazard_types(self) -> set[str]:
        """Return active hazard type identifiers."""
        return {hazard.type for hazard in self.hazards}

    @property
    def hazard_labels(self) -> list[str]:
        """Return active hazard labels."""
        return [hazard.label for hazard in self.hazards]


@dataclass(frozen=True, slots=True)
class EstofexUpdateResult:
    """Result of a coordinator update cycle."""

    forecast: EstofexForecast
    downloaded_map: bool = False
    forecast_changed: bool = False
    status: str = "Updating"
    error: str | None = None


@dataclass(frozen=True, slots=True)
class EstofexDiagnostics:
    """Runtime diagnostics for the forecast update cycle."""

    forecast_age_seconds: int | None = None
    last_http_response: int | None = None
    last_update_duration: float | None = None
    last_download_size: int | None = None
    parser_version: str | None = None
    forecast_source_url: str | None = None


@dataclass(frozen=True, slots=True)
class EstofexForecast:
    """Rich internal ESTOFEX forecast model."""

    id: str | None
    issued_at: datetime | None
    valid_from: datetime | None
    valid_until: datetime | None
    forecaster: str | None
    forecast_number: str | None
    discussion: str | None
    discussion_nl: str | None
    summary_nl: str | None
    map_url: str | None
    local_map_url: str | None
    local_map_path: str | None
    polygons: tuple[EstofexPolygon, ...] = ()
    hazards: tuple[EstofexHazard, ...] = ()
    mesoscale_discussions: tuple[EstofexMesoscaleDiscussion, ...] = ()
    level_texts: tuple[str, ...] = ()
    status: str = "Updating"
    last_checked: datetime | None = None
    last_successful_update: datetime | None = None
    changed: bool = False
    map_available: bool = False
    local_warning: EstofexLocalWarning = field(default_factory=EstofexLocalWarning)
    diagnostics: EstofexDiagnostics = field(default_factory=EstofexDiagnostics)

    @property
    def forecast_id(self) -> str | None:
        """Return the forecast id."""
        return self.id

    @property
    def fcstfile(self) -> str | None:
        """Return the ESTOFEX forecast filename for backward compatibility."""
        return self.id

    @property
    def image_url(self) -> str | None:
        """Return the remote ESTOFEX map URL."""
        return self.map_url

    @property
    def local_image_url(self) -> str | None:
        """Return the local Home Assistant map URL."""
        return self.local_map_url

    @property
    def discussion_original(self) -> str | None:
        """Return the original ESTOFEX discussion text."""
        return self.discussion

    @property
    def levels_present(self) -> tuple[str, ...]:
        """Return warning levels present in the forecast."""
        levels = {
            polygon.level
            for polygon in self.polygons
            if polygon.level and polygon.level_number > 0
        }
        return tuple(sorted(levels, key=_level_sort_key))

    @property
    def highest_level(self) -> str | None:
        """Return the highest ESTOFEX warning level in the forecast."""
        return _highest_level(self.polygons)

    @property
    def local_level(self) -> str | None:
        """Return the highest local ESTOFEX warning level."""
        if self.local_warning.polygon:
            level = self.local_warning.polygon.level
            if level and self.local_warning.polygon.level_number > 0:
                return level
        return None

    def local_summary(self) -> str:
        """Return a concise local forecast summary."""
        if not self.local_warning.active:
            return "No local ESTOFEX warning."

        level = self.local_level or self.local_warning.level or "Thunderstorm area"
        lines = [level]
        if self.local_warning.hazards:
            lines.append("Main risks")
            lines.extend(f"- {hazard.label}" for hazard in self.local_warning.hazards)
        else:
            lines.append("No specific severe hazard parsed.")

        if self.valid_until:
            lines.append(f"Valid until {self.valid_until:%H} UTC")
        return "\n".join(lines)


def _highest_level(polygons: tuple[EstofexPolygon, ...]) -> str | None:
    """Return the highest warning level from a sequence of polygons."""
    level_polygon = max(polygons, key=lambda polygon: polygon.level_number, default=None)
    if not level_polygon or level_polygon.level_number == 0:
        return None
    return level_polygon.level


def _level_sort_key(level: str | None) -> int:
    """Sort Level 1, Level 2, Level 3 in natural order."""
    if not level:
        return 0
    try:
        return int(level.split()[1])
    except (IndexError, ValueError):
        return 0
