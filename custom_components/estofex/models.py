"""Domain models for ESTOFEX forecasts."""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from datetime import UTC, datetime

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
                {"latitude": lat, "longitude": lon} for lat, lon in self.coordinates
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
    matching_forecast_ids: tuple[str, ...] = ()

    @property
    def is_warning(self) -> bool:
        """Return the warning state using domain terminology."""
        return self.active

    @property
    def level_number(self) -> int:
        """Return the normalized numeric warning level."""
        if self.polygon:
            return self.polygon.level_number
        return _level_number(self.level)

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
    source_url: str | None = None
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
    def discussion_markdown(self) -> str | None:
        """Return safe Markdown derived from the normalized plain text."""
        if not self.discussion:
            return None
        lines = [
            f"## {line.title()}" if line.upper() in {"SYNOPSIS", "DISCUSSION"} else line
            for line in self.discussion.splitlines()
        ]
        return "\n".join(lines)

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

    def is_expired(self, now: datetime | None = None) -> bool:
        """Return whether the forecast validity period has ended."""
        if not self.valid_until:
            return False
        return _as_utc(self.valid_until) <= _as_utc(now or datetime.now(UTC))

    def is_active(self, now: datetime | None = None) -> bool:
        """Return whether this forecast is active at the supplied UTC time."""
        if not self.valid_until:
            return False
        current = _as_utc(now or datetime.now(UTC))
        if current >= _as_utc(self.valid_until):
            return False
        return self.issued_at is None or _as_utc(self.issued_at) <= current

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


@dataclass(frozen=True, slots=True)
class EstofexForecastReference:
    """A forecast-list entry with enough metadata for activity filtering."""

    forecast_id: str
    issued_at: datetime | None
    valid_until: datetime | None

    def is_active(self, now: datetime | None = None) -> bool:
        """Return whether the referenced forecast may currently be active."""
        if not self.valid_until:
            return False
        current = _as_utc(now or datetime.now(UTC))
        if current >= _as_utc(self.valid_until):
            return False
        return self.issued_at is None or _as_utc(self.issued_at) <= current


@dataclass(frozen=True, slots=True)
class EstofexUpdateData:
    """Immutable data for all active ESTOFEX forecasts in one update cycle."""

    forecasts: tuple[EstofexForecast, ...] = ()
    primary_forecast_id: str | None = None
    added_forecast_ids: tuple[str, ...] = ()
    removed_forecast_ids: tuple[str, ...] = ()
    changed: bool = False

    def __post_init__(self) -> None:
        """Normalize forecast order and primary selection."""
        forecasts = tuple(sorted(self.forecasts, key=_forecast_sort_key, reverse=True))
        if forecasts != self.forecasts:
            object.__setattr__(self, "forecasts", forecasts)

        ids = {forecast.id for forecast in forecasts if forecast.id}
        primary_id = self.primary_forecast_id
        if primary_id not in ids:
            primary_id = forecasts[0].id if forecasts else None
            object.__setattr__(self, "primary_forecast_id", primary_id)

    @property
    def primary_forecast(self) -> EstofexForecast | None:
        """Return the newest active forecast."""
        return self.get_forecast(self.primary_forecast_id)

    def get_forecast(self, forecast_id: str | None) -> EstofexForecast | None:
        """Find an active forecast by id."""
        if not forecast_id:
            return None
        return next(
            (forecast for forecast in self.forecasts if forecast.id == forecast_id),
            None,
        )

    @property
    def forecast_count(self) -> int:
        """Return the number of active forecasts."""
        return len(self.forecasts)

    @property
    def active_forecast_ids(self) -> tuple[str, ...]:
        """Return all active forecast ids in deterministic order."""
        return tuple(forecast.id for forecast in self.forecasts if forecast.id)

    @property
    def local_warning(self) -> EstofexLocalWarning:
        """Combine local warnings across all active forecasts."""
        matching = [
            forecast for forecast in self.forecasts if forecast.local_warning.active
        ]
        if not matching:
            return EstofexLocalWarning()

        best = max(
            matching,
            key=lambda forecast: (
                forecast.local_warning.level_number,
                len(forecast.local_warning.hazards),
            ),
        )
        hazards: dict[str, EstofexHazard] = {}
        for forecast in matching:
            for hazard in forecast.local_warning.hazards:
                hazards.setdefault(hazard.type, hazard)

        return EstofexLocalWarning(
            active=True,
            level=best.local_warning.level,
            hazards=tuple(hazards.values()),
            polygon=best.local_warning.polygon,
            matching_forecast_ids=tuple(
                forecast.id for forecast in matching if forecast.id
            ),
        )

    @property
    def thunderstorm_forecasts(self) -> tuple[EstofexForecast, ...]:
        """Return locally matching level 1, 2, or 3 forecasts."""
        return tuple(
            forecast
            for forecast in self.forecasts
            if forecast.local_warning.active
            and forecast.local_warning.level_number in {1, 2, 3}
        )

    @property
    def thunderstorm_risk(self) -> bool:
        """Return whether any active forecast has local convective risk."""
        return bool(self.thunderstorm_forecasts)

    @property
    def thunderstorm_hazards(self) -> tuple[EstofexHazard, ...]:
        """Return de-duplicated hazards from matching convective forecasts."""
        hazards: dict[str, EstofexHazard] = {}
        for forecast in self.thunderstorm_forecasts:
            for hazard in forecast.local_warning.hazards:
                hazards.setdefault(hazard.type, hazard)
        return tuple(hazards.values())

    @property
    def highest_thunderstorm_level(self) -> str | None:
        """Return the highest local convective level across active forecasts."""
        matching = self.thunderstorm_forecasts
        if not matching:
            return None
        return max(
            matching,
            key=lambda forecast: forecast.local_warning.level_number,
        ).local_warning.level


def _highest_level(polygons: tuple[EstofexPolygon, ...]) -> str | None:
    """Return the highest warning level from a sequence of polygons."""
    level_polygon = max(
        polygons, key=lambda polygon: polygon.level_number, default=None
    )
    if not level_polygon or level_polygon.level_number == 0:
        return None
    return level_polygon.level


def _as_utc(value: datetime) -> datetime:
    """Return a timezone-aware UTC datetime."""
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _level_sort_key(level: str | None) -> int:
    """Sort Level 1, Level 2, Level 3 in natural order."""
    return _level_number(level)


def _level_number(level: str | None) -> int:
    """Extract a numeric ESTOFEX level from a normalized label."""
    if not level:
        return 0
    match = re.search(r"\b([123])\b", level)
    return int(match.group(1)) if match else 0


def _forecast_sort_key(forecast: EstofexForecast) -> tuple[datetime, str]:
    """Return a stable newest-first sort key for a forecast."""
    issued_at = (
        _as_utc(forecast.issued_at)
        if forecast.issued_at
        else datetime.min.replace(tzinfo=UTC)
    )
    return issued_at, forecast.id or ""
