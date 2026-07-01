"""ESTOFEX API client."""
from __future__ import annotations

from dataclasses import dataclass

from aiohttp import ClientError

from homeassistant.core import HomeAssistant
from homeassistant.helpers.aiohttp_client import async_get_clientsession

from .const import BASE_URL
from .exceptions import EstofexConnectionError


@dataclass(frozen=True, slots=True)
class EstofexApiTextResponse:
    """Text response metadata."""

    body: str
    status: int
    size: int
    url: str


@dataclass(frozen=True, slots=True)
class EstofexApiBytesResponse:
    """Binary response metadata."""

    body: bytes
    status: int
    size: int
    url: str


class EstofexApiClient:
    """Async client for ESTOFEX HTTP resources."""

    def __init__(self, hass: HomeAssistant) -> None:
        """Initialize the API client."""
        self._session = async_get_clientsession(hass)

    async def async_fetch_forecast_list(self) -> EstofexApiTextResponse:
        """Fetch the ESTOFEX forecast list page."""
        url = self.forecast_list_url()
        return await self._async_get_text(url)

    async def async_fetch_forecast_source(
        self, fcstfile: str
    ) -> EstofexApiTextResponse:
        """Fetch the ESTOFEX XML forecast source."""
        url = self.forecast_source_url(fcstfile)
        return await self._async_get_text(url)

    async def async_fetch_forecast_page(
        self, fcstfile: str
    ) -> EstofexApiTextResponse:
        """Fetch the ESTOFEX HTML forecast page."""
        url = self.forecast_page_url(fcstfile)
        return await self._async_get_text(url)

    async def async_fetch_forecast_map(
        self, fcstfile: str
    ) -> EstofexApiBytesResponse:
        """Fetch the ESTOFEX forecast map image."""
        url = self.forecast_map_url(fcstfile)
        return await self._async_get_bytes(url)

    @staticmethod
    def forecast_list_url() -> str:
        """Return the ESTOFEX forecast list URL."""
        return f"{BASE_URL}?list=yes"

    @staticmethod
    def forecast_source_url(fcstfile: str) -> str:
        """Return the ESTOFEX XML forecast source URL."""
        return f"{BASE_URL}?xml=yes&fcstfile={fcstfile}"

    @staticmethod
    def forecast_page_url(fcstfile: str) -> str:
        """Return the ESTOFEX HTML forecast page URL."""
        return f"{BASE_URL}?text=yes&fcstfile={fcstfile}"

    @staticmethod
    def forecast_map_url(fcstfile: str) -> str:
        """Return the ESTOFEX map image URL."""
        return f"{BASE_URL}?lightningmap=yes&fcstfile={fcstfile}"

    async def _async_get_text(self, url: str) -> EstofexApiTextResponse:
        """Fetch and validate a text response."""
        try:
            async with self._session.get(url, timeout=20) as response:
                status = response.status
                body = await response.text()
                if status >= 400:
                    raise EstofexConnectionError(
                        f"ESTOFEX returned HTTP {status} for {url}",
                        status=status,
                    )
                return EstofexApiTextResponse(
                    body=body,
                    status=status,
                    size=len(
                        body.encode(response.charset or "utf-8", errors="ignore")
                    ),
                    url=str(response.url),
                )
        except EstofexConnectionError:
            raise
        except (ClientError, TimeoutError) as err:
            raise EstofexConnectionError(
                f"Could not fetch ESTOFEX URL {url}: {err}"
            ) from err

    async def _async_get_bytes(self, url: str) -> EstofexApiBytesResponse:
        """Fetch and validate a binary response."""
        try:
            async with self._session.get(url, timeout=20) as response:
                status = response.status
                body = await response.read()
                if status >= 400:
                    raise EstofexConnectionError(
                        f"ESTOFEX returned HTTP {status} for {url}",
                        status=status,
                    )
                return EstofexApiBytesResponse(
                    body=body,
                    status=status,
                    size=len(body),
                    url=str(response.url),
                )
        except EstofexConnectionError:
            raise
        except (ClientError, TimeoutError) as err:
            raise EstofexConnectionError(
                f"Could not fetch ESTOFEX URL {url}: {err}"
            ) from err
