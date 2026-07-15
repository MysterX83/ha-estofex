"""Tests for ESTOFEX parser helpers."""

from __future__ import annotations

from datetime import UTC, datetime

from .helpers import load_estofex_module

load_estofex_module("models")
parser = load_estofex_module("parser")


def test_parse_latest_forecast_id() -> None:
    """The newest storm forecast id is extracted from the list page."""
    html = """
    <a href="/cgi-bin/polygon/showforecast.cgi?text=yes&fcstfile=2026070106_202606291259_1_stormforecast.xml">Storm Forecast</a>
    <a href="/cgi-bin/polygon/showforecast.cgi?text=yes&fcstfile=2026062906_202606271607_2_stormforecast.xml">Storm Forecast</a>
    """

    assert (
        parser.parse_latest_forecast_id(html)
        == "2026070106_202606291259_1_stormforecast.xml"
    )


def test_parse_forecast_entries_returns_all_unique_references() -> None:
    """All storm forecasts are returned with activity metadata."""
    html = """
    <a href="?fcstfile=2026070206_202607010600_1_stormforecast.xml">new</a>
    <a href="?fcstfile=2026070112_202606301200_2_stormforecast.xml">old</a>
    <a href="?fcstfile=2026070206_202607010600_1_stormforecast.xml">duplicate</a>
    """

    entries = parser.parse_forecast_entries(html)

    assert [entry.forecast_id for entry in entries] == [
        "2026070206_202607010600_1_stormforecast.xml",
        "2026070112_202606301200_2_stormforecast.xml",
    ]
    now = datetime(2026, 7, 1, 18, tzinfo=UTC)
    assert entries[0].is_active(now)
    assert not entries[1].is_active(now)


def test_parse_estofex_xml_forecast() -> None:
    """ESTOFEX XML-ish source is parsed into a rich forecast model."""
    source = """
    <?xml version="1.0"?>
    <forecast>
      <forecast_type>Storm Forecast</forecast_type>
      <start_time value="2026063006"/>
      <expiry_time value="2026070106"/>
      <issue_time value="202606291259"/>
      <forecaster>TUSCHY</forecaster>
      <text>A level 2 was issued for the test area mainly for very large hail, severe gusts, excessive rain and tornadoes.<BR><BR>DISCUSSION<BR><BR>Heavy rainfall and flash flooding are possible.</text>
      <area risktype="level 2">
        <point lat="0" lon="0"/>
        <point lat="0" lon="2"/>
        <point lat="2" lon="2"/>
        <point lat="2" lon="0"/>
        <point lat="0" lon="0"/>
      </area>
    </forecast>
    """

    forecast = parser.parse_estofex_forecast(
        source,
        "2026070106_202606291259_2_stormforecast.xml",
        map_url="https://example.test/map.png",
    )

    assert forecast.id == "2026070106_202606291259_2_stormforecast.xml"
    assert forecast.forecaster == "TUSCHY"
    assert forecast.forecast_number == "2"
    assert forecast.highest_level == "Level 2"
    assert len(forecast.polygons) == 1
    assert {hazard.type for hazard in forecast.hazards} >= {
        "large_hail",
        "severe_wind",
        "excessive_rain",
        "tornado",
        "flash_flood",
    }


def _xml_with_discussion(discussion: str) -> str:
    """Return a minimal polygon forecast with the supplied discussion."""
    return f"""
    <forecast>
      <expiry_time value="2026070206"/>
      <issue_time value="202607010600"/>
      <text>{discussion}</text>
      <area risktype="level 1">
        <point lat="0" lon="0"/><point lat="0" lon="1"/>
        <point lat="1" lon="1"/><point lat="1" lon="0"/>
      </area>
    </forecast>
    """


def test_discussion_preserves_paragraphs_and_decodes_entities() -> None:
    """Discussion parsing preserves useful structure and decodes entities."""
    forecast = parser.parse_estofex_forecast(
        _xml_with_discussion(
            "SYNOPSIS<BR><BR>First &amp; second.<BR><BR>DISCUSSION<BR><BR>Final paragraph."
        ),
        "2026070206_202607010600_1_stormforecast.xml",
    )

    assert "First & second." in forecast.discussion
    assert "\n\n" in forecast.discussion
    assert forecast.discussion_markdown.startswith("## Synopsis")
    assert "## Discussion" in forecast.discussion_markdown


def test_discussion_strips_unsafe_tags_and_normalizes_whitespace() -> None:
    """Scripts, styles, tags, and excessive whitespace are removed."""
    forecast = parser.parse_estofex_forecast(
        _xml_with_discussion(
            "  DISCUSSION  <BR><BR><script>alert(1)</script>"
            "<style>bad { color: red }</style><b>Useful</b>    text.  "
        ),
        "2026070206_202607010600_1_stormforecast.xml",
    )

    assert forecast.discussion == "DISCUSSION\n\nUseful text."
    assert "alert" not in forecast.discussion
    assert "style" not in forecast.discussion
    assert "<" not in forecast.discussion


def test_empty_discussion_is_none() -> None:
    """An empty discussion is represented as unavailable."""
    forecast = parser.parse_estofex_forecast(
        _xml_with_discussion("   "),
        "2026070206_202607010600_1_stormforecast.xml",
    )

    assert forecast.discussion is None
    assert forecast.discussion_markdown is None


def test_very_long_discussion_is_not_truncated() -> None:
    """The full normalized discussion remains available as an attribute value."""
    discussion = "DISCUSSION<BR><BR>" + "Long forecast sentence. " * 1000
    forecast = parser.parse_estofex_forecast(
        _xml_with_discussion(discussion),
        "2026070206_202607010600_1_stormforecast.xml",
    )

    assert forecast.discussion is not None
    assert len(forecast.discussion) > 20_000
    assert forecast.discussion.endswith("Long forecast sentence.")
