"""Parsing helpers for ESTOFEX forecast text pages."""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
import re


@dataclass(frozen=True, slots=True)
class EstofexMesoscaleDiscussion:
    """Structured placeholder for future ESTOFEX Mesoscale Discussions."""

    original_text: str | None = None
    discussion_nl: str | None = None
    summary_nl: str | None = None
    issued_at: datetime | None = None
    affected_region: str | None = None
    source_url: str | None = None


@dataclass(frozen=True, slots=True)
class ParsedEstofexForecast:
    """Structured data parsed from an ESTOFEX forecast text page."""

    title: str | None
    valid_from: datetime | None
    valid_until: datetime | None
    issued_at: datetime | None
    forecaster: str | None
    forecast_number: str | None
    level_texts: tuple[str, ...]
    discussion_text: str | None
    mesoscale_discussions: tuple[EstofexMesoscaleDiscussion, ...] = ()


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
_FCSTFILE_RE = re.compile(
    r"^\d{10}_\d{12}_(?P<number>\d+)_stormforecast\.xml$",
    re.IGNORECASE,
)
_SECTION_RE = re.compile(r"(?im)^(SYNOPSIS|DISCUSSION)\s*$")
_LEVEL_TEXT_RE = re.compile(
    r"\b(level\s+\d|thunderstorm\s+level|lightning\s+area)\b",
    re.IGNORECASE,
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


def parse_estofex_forecast(
    html: str, fcstfile: str | None = None
) -> ParsedEstofexForecast:
    """Parse an ESTOFEX forecast text page into structured fields."""
    parser = _BulletinHTMLParser()
    parser.feed(html)

    paragraphs = parser.bulletins or [_text_fallback(html)]
    paragraphs = [paragraph for paragraph in paragraphs if paragraph]

    metadata = _find_metadata(paragraphs)
    body_text = _find_body_text(paragraphs, metadata)

    valid_from, valid_until = _parse_valid_period(metadata)
    issued_at = _parse_issued_at(metadata)

    return ParsedEstofexForecast(
        title=_parse_title(metadata, parser.title),
        valid_from=valid_from,
        valid_until=valid_until,
        issued_at=issued_at,
        forecaster=_parse_forecaster(metadata),
        forecast_number=_parse_forecast_number(fcstfile),
        level_texts=_extract_level_texts(body_text),
        discussion_text=_extract_discussion_text(body_text),
    )


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


def _parse_title(metadata: str, page_title: str | None) -> str | None:
    """Parse the forecast title."""
    for line in metadata.splitlines():
        line = line.strip()
        if line and not line.startswith(("Valid:", "Issued:", "Forecaster:")):
            return line
    return page_title


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
    match = _FCSTFILE_RE.match(fcstfile)
    return match.group("number") if match else None


def _extract_level_texts(body_text: str) -> tuple[str, ...]:
    """Extract forecast level text blocks."""
    lead_text = body_text
    section_match = _SECTION_RE.search(body_text)
    if section_match:
        lead_text = body_text[: section_match.start()]

    return tuple(
        block
        for block in _split_blocks(lead_text)
        if _LEVEL_TEXT_RE.search(block)
    )


def _extract_discussion_text(body_text: str) -> str | None:
    """Extract the narrative forecast discussion text."""
    section_match = _SECTION_RE.search(body_text)
    if section_match:
        return body_text[section_match.start() :].strip() or None

    discussion_blocks = [
        block for block in _split_blocks(body_text) if not _LEVEL_TEXT_RE.search(block)
    ]
    return "\n\n".join(discussion_blocks).strip() or None


def _split_blocks(text: str) -> list[str]:
    """Split text into blank-line-separated blocks."""
    return [block.strip() for block in re.split(r"\n\s*\n", text) if block.strip()]


def _parse_estofex_datetime(value: str) -> datetime | None:
    """Parse an ESTOFEX UTC timestamp."""
    value = _flatten(value)
    for date_format in ("%a %d %b %Y %H:%M", "%d %b %Y %H:%M"):
        try:
            return datetime.strptime(value, date_format).replace(tzinfo=timezone.utc)
        except ValueError:
            continue
    return None


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
