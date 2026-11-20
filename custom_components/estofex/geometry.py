"""Geometry helpers for ESTOFEX polygons."""

from __future__ import annotations

from .models import EstofexHazard, EstofexLocalWarning, EstofexPolygon

_EPSILON = 1e-9


def evaluate_location_warning(
    latitude: float | None,
    longitude: float | None,
    polygons: tuple[EstofexPolygon, ...],
) -> EstofexLocalWarning:
    """Evaluate a location against forecast polygons."""
    if latitude is None or longitude is None:
        return EstofexLocalWarning()

    matching = [
        polygon
        for polygon in polygons
        if point_in_polygon(latitude, longitude, polygon.coordinates)
    ]
    if not matching:
        return EstofexLocalWarning()

    best_polygon = max(
        matching,
        key=lambda polygon: (polygon.level_number, len(polygon.hazards)),
    )
    return EstofexLocalWarning(
        active=True,
        level=best_polygon.level,
        hazards=_unique_hazards(matching),
        polygon=best_polygon,
    )


def point_in_polygon(
    latitude: float,
    longitude: float,
    coordinates: tuple[tuple[float, float], ...],
) -> bool:
    """Return whether a latitude/longitude point is inside a polygon.

    Coordinates are expected as ``(latitude, longitude)`` pairs. Points on a
    polygon boundary count as inside.
    """
    if len(coordinates) < 3:
        return False

    vertices = _normalize_longitudes(coordinates)
    point_x = _normalize_longitude(longitude)
    center_x = (min(x for x, _ in vertices) + max(x for x, _ in vertices)) / 2
    point_x += 360 * round((center_x - point_x) / 360)
    point_y = latitude

    inside = False
    previous_x, previous_y = vertices[-1]

    for current_x, current_y in vertices:
        if _point_on_segment(
            point_x,
            point_y,
            previous_x,
            previous_y,
            current_x,
            current_y,
        ):
            return True

        crosses = (current_y > point_y) != (previous_y > point_y)
        if crosses:
            intersect_x = (previous_x - current_x) * (point_y - current_y) / (
                previous_y - current_y
            ) + current_x
            if point_x < intersect_x:
                inside = not inside

        previous_x, previous_y = current_x, current_y

    return inside


def _unique_hazards(
    polygons: list[EstofexPolygon],
) -> tuple[EstofexHazard, ...]:
    """Return de-duplicated hazards from matching polygons."""
    hazards: dict[str, EstofexHazard] = {}
    for polygon in polygons:
        for hazard in polygon.hazards:
            hazards.setdefault(hazard.type, hazard)
    return tuple(hazards.values())


def _normalize_longitudes(
    coordinates: tuple[tuple[float, float], ...],
) -> list[tuple[float, float]]:
    """Normalize longitudes to keep dateline-crossing polygons coherent."""
    vertices: list[tuple[float, float]] = []
    for lat, lon in coordinates:
        normalized_lon = _normalize_longitude(lon)
        if vertices:
            # Unwrap consecutive edges independently of the query point.
            normalized_lon += 360 * round((vertices[-1][0] - normalized_lon) / 360)
        vertices.append((normalized_lon, lat))
    return vertices


def _normalize_longitude(longitude: float) -> float:
    """Normalize longitude to the -180..180 range."""
    return ((longitude + 180) % 360) - 180


def _point_on_segment(
    point_x: float,
    point_y: float,
    start_x: float,
    start_y: float,
    end_x: float,
    end_y: float,
) -> bool:
    """Return whether a point lies on a line segment."""
    cross_product = (point_y - start_y) * (end_x - start_x) - (point_x - start_x) * (
        end_y - start_y
    )
    if abs(cross_product) > _EPSILON:
        return False

    return (
        min(start_x, end_x) - _EPSILON <= point_x <= max(start_x, end_x) + _EPSILON
        and min(start_y, end_y) - _EPSILON <= point_y <= max(start_y, end_y) + _EPSILON
    )
