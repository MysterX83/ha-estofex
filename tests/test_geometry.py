"""Tests for ESTOFEX geometry helpers."""
from __future__ import annotations

from .helpers import load_estofex_module

models = load_estofex_module("models")
geometry = load_estofex_module("geometry")


def test_point_in_polygon_inside() -> None:
    """Point inside a polygon returns true."""
    assert geometry.point_in_polygon(1, 1, ((0, 0), (0, 2), (2, 2), (2, 0)))


def test_point_in_polygon_outside() -> None:
    """Point outside a polygon returns false."""
    assert not geometry.point_in_polygon(3, 3, ((0, 0), (0, 2), (2, 2), (2, 0)))


def test_point_on_boundary_counts_as_inside() -> None:
    """Point on polygon boundary returns true."""
    assert geometry.point_in_polygon(0, 1, ((0, 0), (0, 2), (2, 2), (2, 0)))


def test_evaluate_location_warning_returns_highest_matching_level() -> None:
    """Local warning selects the highest matching polygon level."""
    hail = models.EstofexHazard(type="large_hail")
    polygons = (
        models.EstofexPolygon(
            level="Level 1",
            coordinates=((0, 0), (0, 3), (3, 3), (3, 0)),
            hazards=(),
        ),
        models.EstofexPolygon(
            level="Level 2",
            coordinates=((0, 0), (0, 2), (2, 2), (2, 0)),
            hazards=(hail,),
        ),
    )

    warning = geometry.evaluate_location_warning(1, 1, polygons)

    assert warning.active
    assert warning.level == "Level 2"
    assert warning.hazards == (hail,)
