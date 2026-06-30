"""Download and cache helpers for ESTOFEX."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession


@dataclass(frozen=True, slots=True)
class EstofexTextResponse:
    """Text response metadata."""

    body: str
    status: int
    size: int


@dataclass(frozen=True, slots=True)
class EstofexBytesResponse:
    """Binary response metadata."""

    body: bytes
    status: int
    size: int


class EstofexDownloader:
    """Downloader for ESTOFEX HTTP resources and cached files."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the downloader."""
        self._hass = hass

    async def async_get_text(self, url: str) -> EstofexTextResponse:
        """Fetch a text resource."""
        session = async_get_clientsession(self._hass)
        async with session.get(url, timeout=20) as response:
            response.raise_for_status()
            body = await response.text()
            return EstofexTextResponse(
                body=body,
                status=response.status,
                size=len(body.encode(response.charset or "utf-8", errors="ignore")),
            )

    async def async_get_bytes(self, url: str) -> EstofexBytesResponse:
        """Fetch a binary resource."""
        session = async_get_clientsession(self._hass)
        async with session.get(url, timeout=20) as response:
            response.raise_for_status()
            body = await response.read()
            return EstofexBytesResponse(
                body=body,
                status=response.status,
                size=len(body),
            )

    async def async_download_file(self, url: str, out_file: Path) -> EstofexBytesResponse:
        """Download a binary resource to a file."""
        response = await self.async_get_bytes(url)
        await self._hass.async_add_executor_job(
            self._write_bytes,
            out_file,
            response.body,
        )
        return response

    async def async_remove_file(self, path: Path) -> None:
        """Remove a cached file if it exists."""
        await self._hass.async_add_executor_job(self._remove_file, path)

    @staticmethod
    def _write_bytes(path: Path, data: bytes) -> None:
        """Write bytes to a file, creating parent directories."""
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)

    @staticmethod
    def _remove_file(path: Path) -> None:
        """Remove a file if it exists."""
        if path.exists():
            path.unlink()
