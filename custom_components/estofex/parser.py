"""Parsing helpers for ESTOFEX forecast sources."""
from __future__ import annotations

from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re

from .models import (
    HAZARD_EXCESSIVE_RAIN,
    HAZARD_FLASH_FLOOD,
    HAZARD_LARGE_HAIL,
    HAZARD_SEVERE_WIND,
    HAZARD_TORNADO,
    EstofexForecast,
    EstofexHazard,
    EstofexPolygon,
)

PARSER_VERSION = "0.3.0"

_FCSTFILE_RE = re.compile(
    r"(?P<id>\d{10}_\d{12}_(?P<number>\d+)_(?:stormforecast|mesoscalediscussion)\.xml)",
    re.IGNORECASE,
)
_STORM_FCSTFILE_RE = re.compile(
    r"fcstfile=([^\"'&<>]+stormforecast\.xml)",
    re.IGNORECASE,
)
_VALUE_ATTR_RE = re.compile(r"<(?P<tag>\w+)\s+value=[\"'](?P<value>[^\"']+)[\"']\s*/?>")
_AREA_RE = re.compile(
    r"<area\b(?P<attrs>[^>]*)>(?P<body>.*?)</area>",
    re.IGNORECASE | re.DOTALL,
)
_POINT_RE = re.compile(
    r"<point\b[^>]*\blat=[\"'](?P<lat>-?\d+(?:\.\d+)?)[\"']"
    r"[^>]*\blon=[\"'](?P<lon>-?\d+(?:\.\d+)?)[\"'][^>]*/?>",
    re.IGNORECASE,
)
_ATTR_RE = re.compile(r"(?P<key>\w+)=[\"'](?P<value>[^\"']*)[\"']")
_VALID_RE = re.compile(
    r"\bValid:\s*(?P<valid_from>.*?)\s+to\s+"
    r"(?P<valid_until>.*?)\s+UTC\b",
    re.IGNORECASE | re.DOTALL,
)
_ISSUED_RE = re.compile(
    r"\bIssued:\s*(?P<issued>"
    r"[A-Za-z]{3}\s+\d{1,2}\s+[A-Za-z]{3}\s+\d{4}\s+\d{2}:\d{2}"
    r")(?:\s*UTC)?\b",
    re.IGNORECASE,
)
_FORECASTER_RE = re.compile(r"\bForecaster:\s*(?P<forecaster>[^\n\r]+)")
_SECTION_RE = re.compile(r"(?im)^(SYNOPSIS|DISCUSSION)\s*$")
_LEVEL_TEXT_RE = re.compile(r"\blevel\s+(?P<level>[123])\b", re.IGNORECASE)

_HAZARD_PATTERNS: tuple[tuple[str, tuple[str, ...]], ...] = (
    (
        HAZARD_LARGE_HAIL,
        (
            r"\bvery large hail\b",
            r"\blarge hail\b",
            r"\bisolated large\)? hail\b",
            r"\bhail\b",
        ),
    ),
    (
        HAZARD_SEVERE_WIND,
        (
            r"\bsevere wind\b",
            r"\bdamaging gusts?\b",
            r"\bsevere gusts?\b",
            r"\bstrong to severe gusts?\b",
            r"\bgust risk\b",
            r"\bdownburst gusts?\b",
        ),
    ),
    (
        HAZARD_EXCESSIVE_RAIN,
        (
            r"\bexcessive rain\b",
            r"\bheavy rain\b",
            r"\bheavy rainfall\b",
            r"\bextreme rainfall\b",
            r"\bextreme rainfall rates\b",
        ),
    ),
    (HAZARD_TORNADO, (r"\btornado(?:es)?\b",)),
    (
        HAZARD_FLASH_FLOOD,
        (
            r"\bflash flood(?:ing)?\b",
            r"\blocal flooding\b",
        ),
    ),
)


class _BulletinHTMLParser(HTMLParser):
    """Extract visible ESTOFEX bulletin paragraphs from the forecast page."""

    def __init__(self) -> None:
        """Initialize the parser."""
        super().__init__(convert_charrefs=True)
        self.bulletins: list[str] = []
        self.title: str | None = None
        self._in_bulletin = False
        self._in_title = False
        self._current: list[str] = []
        self._title_parts: list[str] = []

    def handle_starttag(
        self, tag: str, attrs: list[tuple[str, str | None]]
    ) -> None:
        """Handle relevant start tags."""
        tag = tag.lower()
        attr_map = {key.lower(): value or "" for key, value in attrs}
        classes = attr_map.get("class", "").lower().split()

        if tag == "div" and "title" in classes:
            self._in_title = True
            self._title_parts = []
            return

        if tag == "p" and "bulletin" in classes:
            self._in_bulletin = True
            self._current = []
            return

        if self._in_bulletin and tag == "br":
            self._current.append("\n")

    def handle_endtag(self, tag: str) -> None:
        """Handle relevant end tags."""
        tag = tag.lower()

        if tag == "div" and self._in_title:
            title = _normalize_text("".join(self._title_parts))
            self.title = title or self.title
            self._in_title = False
            return

        if tag == "p" and self._in_bulletin:
            text = _normalize_text("".join(self._current))
            if text:
                self.bulletins.append(text)
            self._in_bulletin = False

    def handle_data(self, data: str) -> None:
        """Collect text data for active elements."""
        if self._in_bulletin:
            self._current.append(data)
        elif self._in_title:
            self._title_parts.append(data)


def parse_latest_forecast_id(html: str) -> str | None:
    """Extract the newest storm forecast id from the ESTOFEX list page."""
    matches = _STORM_FCSTFILE_RE.findall(html)
    return matches[0] if matches else None


def parse_estofex_forecast(
    source: str,
    fcstfile: str,
    map_url: str | None = None,
    local_map_url: str | None = None,
    local_map_path: str | None = None,
    discussion_nl: str | None = None,
    summary_nl: str | None = None,
) -> EstofexForecast:
    """Parse an ESTOFEX XML-ish or HTML source into a forecast model."""
    if "<forecast" in source.lower() and "<area" in source.lower():
        return _parse_xmlish_forecast(
            source,
            fcstfile,
            map_url,
            local_map_url,
            local_map_path,
            discussion_nl,
            summary_nl,
        )

    return _parse_html_forecast(
        source,
        fcstfile,
        map_url,
        local_map_url,
        local_map_path,
        discussion_nl,
        summary_nl,
    )


def _parse_xmlish_forecast(
    source: str,
    fcstfile: str,
    map_url: str | None,
    local_map_url: str | None,
    local_map_path: str | None,
    discussion_nl: str | None,
    summary_nl: str | None,
) -> EstofexForecast:
    """Parse ESTOFEX's XML-like forecast response."""
    discussion = _extract_xmlish_text(source)
    level_texts = _extract_level_texts(discussion)
    hazards = _extract_hazards(discussion)
    hazards_by_level = _hazards_by_level(level_texts, hazards)

    return EstofexForecast(
        id=fcstfile,
        issued_at=_parse_compact_datetime(_value_attr(source, "issue_time"), True)
        or _parse_fcstfile_issued_at(fcstfile),
        valid_from=_parse_compact_datetime(_value_attr(source, "start_time"), False),
        valid_until=_parse_compact_datetime(_value_attr(source, "expiry_time"), False)
        or _parse_fcstfile_valid_until(fcstfile),
        forecaster=_tag_value(source, "forecaster"),
        forecast_number=_parse_forecast_number(fcstfile),
        discussion=discussion,
        discussion_nl=discussion_nl,
        summary_nl=summary_nl,
        map_url=map_url,
        local_map_url=local_map_url,
        local_map_path=local_map_path,
        polygons=_parse_polygons(source, hazards, hazards_by_level, level_texts),
        hazards=hazards,
        level_texts=level_texts,
    )


def _parse_html_forecast(
    source: str,
    fcstfile: str,
    map_url: str | None,
    local_map_url: str | None,
    local_map_path: str | None,
    discussion_nl: str | None,
    summary_nl: str | None,
) -> EstofexForecast:
    """Parse the HTML text endpoint as a fallback source."""
    parser = _BulletinHTMLParser()
    parser.feed(source)

    paragraphs = parser.bulletins or [_text_fallback(source)]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    metadata = _find_metadata(paragraphs)
    body_text = _find_body_text(paragraphs, metadata)
    level_texts = _extract_level_texts(body_text)
    discussion = _extract_discussion_text(body_text)
    hazards = _extract_hazards(body_text)

    valid_from, valid_until = _parse_valid_period(metadata)
    issued_at = _parse_issued_at(metadata)

    return EstofexForecast(
        id=fcstfile,
        issued_at=issued_at or _parse_fcstfile_issued_at(fcstfile),
        valid_from=valid_from,
        valid_until=valid_until or _parse_fcstfile_valid_until(fcstfile),
        forecaster=_parse_forecaster(metadata),
        forecast_number=_parse_forecast_number(fcstfile),
        discussion=discussion,
        discussion_nl=discussion_nl,
        summary_nl=summary_nl,
        map_url=map_url,
        local_map_url=local_map_url,
        local_map_path=local_map_path,
        hazards=hazards,
        level_texts=level_texts,
    )


def _parse_polygons(
    source: str,
    forecast_hazards: tuple[EstofexHazard, ...],
    hazards_by_level: dict[str, tuple[EstofexHazard, ...]],
    level_texts: tuple[str, ...],
) -> tuple[EstofexPolygon, ...]:
    """Parse ESTOFEX area polygons from XML-ish source."""
    descriptions_by_level = _descriptions_by_level(level_texts)
    polygons: list[EstofexPolygon] = []

    for area_match in _AREA_RE.finditer(source):
        attrs = _parse_attrs(area_match.group("attrs"))
        risk_type = attrs.get("risktype")
        coordinates = _parse_points(area_match.group("body"))
        if not coordinates:
            continue

        level = _risk_type_to_level(risk_type)
        polygon_hazards = hazards_by_level.get(level or "", ())
        if level and level.lower().startswith("level ") and not polygon_hazards:
            polygon_hazards = forecast_hazards

        polygons.append(
            EstofexPolygon(
                level=level,
                coordinates=coordinates,
                hazards=polygon_hazards,
                region=_region_from_description(
                    descriptions_by_level.get(level or "")
                ),
                description=descriptions_by_level.get(level or ""),
                risk_type=risk_type,
            )
        )

    return tuple(polygons)


def _parse_points(body: str) -> tuple[tuple[float, float], ...]:
    """Parse point coordinates from an ESTOFEX area body."""
    points: list[tuple[float, float]] = []
    for match in _POINT_RE.finditer(body):
        points.append((float(match.group("lat")), float(match.group("lon"))))
    return tuple(points)


def _parse_attrs(attrs: str) -> dict[str, str]:
    """Parse XML-ish attributes from a tag."""
    return {
        match.group("key").lower(): match.group("value")
        for match in _ATTR_RE.finditer(attrs)
    }


def _risk_type_to_level(risk_type: str | None) -> str | None:
    """Normalize ESTOFEX risk type values."""
    if not risk_type:
        return None

    value = risk_type.strip().lower()
    level_match = re.search(r"level\s*([123])", value)
    if level_match:
        return f"Level {level_match.group(1)}"
    if "thunder" in value:
        return "Thunderstorm"
    if value and value != "severe storms unlikely":
        return risk_type.strip().title()
    return None


def _extract_xmlish_text(source: str) -> str | None:
    """Extract and normalize the forecast text from XML-ish source."""
    match = re.search(r"<text>(?P<text>.*?)</text>", source, re.IGNORECASE | re.DOTALL)
    if not match:
        return None
    text = re.sub(r"<br\s*/?>", "\n", match.group("text"), flags=re.IGNORECASE)
    return _normalize_text(re.sub(r"<[^>]+>", "", text))


def _tag_value(source: str, tag: str) -> str | None:
    """Extract a simple tag value from XML-ish source."""
    match = re.search(
        rf"<{re.escape(tag)}\b[^>]*>(?P<value>.*?)</{re.escape(tag)}>",
        source,
        re.IGNORECASE | re.DOTALL,
    )
    return _normalize_text(match.group("value")) if match else None


def _value_attr(source: str, tag: str) -> str | None:
    """Extract a value attribute from an XML-ish tag."""
    for match in _VALUE_ATTR_RE.finditer(source):
        if match.group("tag").lower() == tag.lower():
            return match.group("value")
    return None


def _extract_hazards(text: str | None) -> tuple[EstofexHazard, ...]:
    """Extract normalized hazards from ESTOFEX text."""
    if not text:
        return ()

    hazards: list[EstofexHazard] = []
    for hazard_type, patterns in _HAZARD_PATTERNS:
        if any(re.search(pattern, text, re.IGNORECASE) for pattern in patterns):
            hazards.append(
                EstofexHazard(
                    type=hazard_type,
                    severity=_hazard_severity(hazard_type, text),
                    probability=_hazard_probability(text),
                )
            )
    return tuple(hazards)


def _hazards_by_level(
    level_texts: tuple[str, ...],
    forecast_hazards: tuple[EstofexHazard, ...],
) -> dict[str, tuple[EstofexHazard, ...]]:
    """Map warning levels to hazards mentioned in their level text."""
    hazards_by_level: dict[str, list[EstofexHazard]] = {}
    for level_text in level_texts:
        level = _level_from_text(level_text)
        if not level:
            continue
        hazards_by_level.setdefault(level, [])
        for hazard in _extract_hazards(level_text):
            if hazard.type not in {existing.type for existing in hazards_by_level[level]}:
                hazards_by_level[level].append(hazard)

    return {
        level: tuple(hazards or forecast_hazards)
        for level, hazards in hazards_by_level.items()
    }


def _hazard_severity(hazard_type: str, text: str) -> str | None:
    """Infer a coarse hazard severity from natural-language text."""
    lowered = text.lower()
    if "very large" in lowered or "extreme" in lowered:
        return "high"
    if hazard_type in (HAZARD_TORNADO, HAZARD_FLASH_FLOOD):
        return "severe"
    if "severe" in lowered or "excessive" in lowered or "large hail" in lowered:
        return "severe"
    if "local" in lowered or "isolated" in lowered:
        return "localized"
    return None


def _hazard_probability(text: str) -> str | None:
    """Infer a coarse hazard probability from natural-language text."""
    lowered = text.lower()
    if "isolated" in lowered:
        return "isolated"
    if "local" in lowered:
        return "local"
    if "numerous" in lowered:
        return "numerous"
    return None


def _extract_level_texts(body_text: str | None) -> tuple[str, ...]:
    """Extract forecast level text blocks."""
    if not body_text:
        return ()

    lead_text = body_text
    section_match = _SECTION_RE.search(body_text)
    if section_match:
        lead_text = body_text[: section_match.start()]

    return tuple(
        block
        for block in _split_blocks(lead_text)
        if _LEVEL_TEXT_RE.search(block)
    )


def _descriptions_by_level(level_texts: tuple[str, ...]) -> dict[str, str]:
    """Return the first description found for each warning level."""
    descriptions: dict[str, str] = {}
    for text in level_texts:
        level = _level_from_text(text)
        if level and level not in descriptions:
            descriptions[level] = text
    return descriptions


def _level_from_text(text: str) -> str | None:
    """Extract a warning level from text."""
    match = _LEVEL_TEXT_RE.search(text)
    return f"Level {match.group('level')}" if match else None


def _region_from_description(description: str | None) -> str | None:
    """Extract the free-text region from a level sentence."""
    if not description:
        return None
    match = re.search(
        r"\blevel\s+[123]\s+was\s+issued\s+for\s+(?P<region>.*?)(?:\s+mainly|\.)",
        description,
        re.IGNORECASE | re.DOTALL,
    )
    return _flatten(match.group("region")) if match else None


def _extract_discussion_text(body_text: str) -> str | None:
    """Extract the narrative forecast discussion text."""
    section_match = _SECTION_RE.search(body_text)
    if section_match:
        return body_text[section_match.start() :].strip() or None

    discussion_blocks = [
        block for block in _split_blocks(body_text) if not _LEVEL_TEXT_RE.search(block)
    ]
    return "\n\n".join(discussion_blocks).strip() or None


def _find_metadata(paragraphs: list[str]) -> str:
    """Return the paragraph containing forecast metadata."""
    for paragraph in paragraphs:
        if any(label in paragraph for label in ("Valid:", "Issued:", "Forecaster:")):
            return paragraph
    return paragraphs[0] if paragraphs else ""


def _find_body_text(paragraphs: list[str], metadata: str) -> str:
    """Return the forecast body text paragraph(s)."""
    body_parts: list[str] = []
    for paragraph in paragraphs:
        if paragraph == metadata:
            continue
        if any(label in paragraph for label in ("Valid:", "Issued:", "Forecaster:")):
            continue
        if paragraph.lower() in {"storm forecast"}:
            continue
        body_parts.append(paragraph)
    return "\n\n".join(body_parts).strip()


def _parse_valid_period(metadata: str) -> tuple[datetime | None, datetime | None]:
    """Parse the valid-from and valid-until timestamps."""
    match = _VALID_RE.search(_flatten(metadata))
    if not match:
        return None, None
    return (
        _parse_estofex_datetime(match.group("valid_from")),
        _parse_estofex_datetime(match.group("valid_until")),
    )


def _parse_issued_at(metadata: str) -> datetime | None:
    """Parse the issue timestamp."""
    match = _ISSUED_RE.search(_flatten(metadata))
    if not match:
        return None
    return _parse_estofex_datetime(match.group("issued"))


def _parse_forecaster(metadata: str) -> str | None:
    """Parse the forecaster name."""
    match = _FORECASTER_RE.search(metadata)
    return match.group("forecaster").strip() if match else None


def _parse_forecast_number(fcstfile: str | None) -> str | None:
    """Parse the forecast number from an ESTOFEX forecast filename."""
    if not fcstfile:
        return None
    match = _FCSTFILE_RE.search(fcstfile)
    return match.group("number") if match else None


def _parse_fcstfile_issued_at(fcstfile: str) -> datetime | None:
    """Parse the issued timestamp from a forecast filename."""
    match = _FCSTFILE_RE.search(fcstfile)
    if not match:
        return None
    parts = match.group("id").split("_")
    return _parse_compact_datetime(parts[1], True) if len(parts) > 1 else None


def _parse_fcstfile_valid_until(fcstfile: str) -> datetime | None:
    """Parse the valid-until timestamp from a forecast filename."""
    match = _FCSTFILE_RE.search(fcstfile)
    if not match:
        return None
    parts = match.group("id").split("_")
    return _parse_compact_datetime(parts[0], False) if parts else None


def _parse_compact_datetime(value: str | None, has_minutes: bool) -> datetime | None:
    """Parse ESTOFEX compact UTC datetime strings."""
    if not value:
        return None
    date_format = "%Y%m%d%H%M" if has_minutes else "%Y%m%d%H"
    try:
        return datetime.strptime(value, date_format).replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def _parse_estofex_datetime(value: str) -> datetime | None:
    """Parse an ESTOFEX UTC timestamp."""
    value = _flatten(value)
    for date_format in ("%a %d %b %Y %H:%M", "%d %b %Y %H:%M"):
        try:
            return datetime.strptime(value, date_format).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


def _split_blocks(text: str) -> list[str]:
    """Split text into blank-line-separated blocks."""
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def _text_fallback(html: str) -> str:
    """Return a simple tag-stripped fallback for non-standard responses."""
    return _normalize_text(re.sub(r"<[^>]+>", "\n", html))


def _flatten(text: str) -> str:
    """Collapse all whitespace in text."""
    return re.sub(r"\s+", " ", text).strip()


def _normalize_text(text: str) -> str:
    """Normalize ESTOFEX text while preserving paragraph breaks."""
    text = unescape(text).replace("\xa0", " ")
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    text = re.sub(r"[ \t\f\v]+", " ", text)

    lines = [line.strip() for line in text.split("\n")]
    normalized: list[str] = []
    previous_blank = False

    for line in lines:
        if not line:
            if normalized and not previous_blank:
                normalized.append("")
            previous_blank = True
            continue

        normalized.append(line)
        previous_blank = False

    return "\n".join(normalized).strip()
