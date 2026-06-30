"""Geometry helpers for ESTOFEX polygons."""
from __future__ import annotations

_EPSILON = 1e-9


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

    vertices = _normalize_longitudes(longitude, coordinates)
    point_x = _normalize_longitude(longitude)
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
            intersect_x = (previous_x - current_x) * (
                point_y - current_y
            ) / (previous_y - current_y) + current_x
            if point_x < intersect_x:
                inside = not inside

        previous_x, previous_y = current_x, current_y

    return inside


def _normalize_longitudes(
    point_longitude: float,
    coordinates: tuple[tuple[float, float], ...],
) -> list[tuple[float, float]]:
    """Normalize longitudes to keep dateline-crossing polygons coherent."""
    longitudes = [_normalize_longitude(lon) for _, lon in coordinates]
    crosses_dateline = max(longitudes) - min(longitudes) > 180
    point_lon = _normalize_longitude(point_longitude)

    vertices: list[tuple[float, float]] = []
    for lat, lon in coordinates:
        normalized_lon = _normalize_longitude(lon)
        if crosses_dateline and normalized_lon - point_lon > 180:
            normalized_lon -= 360
        elif crosses_dateline and point_lon - normalized_lon > 180:
            normalized_lon += 360
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
    cross_product = (point_y - start_y) * (end_x - start_x) - (
        point_x - start_x
    ) * (end_y - start_y)
    if abs(cross_product) > _EPSILON:
        return False

    return (
        min(start_x, end_x) - _EPSILON
        <= point_x
        <= max(start_x, end_x) + _EPSILON
        and min(start_y, end_y) - _EPSILON
        <= point_y
        <= max(start_y, end_y) + _EPSILON
    )
