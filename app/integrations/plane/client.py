"""
Plane API HTTP Client
"""
import aiohttp
from typing import Dict, Any, Optional, List
from ...utils.logger import bot_logger
from .exceptions import PlaneAPIError, PlaneAuthError, PlaneNotFoundError, PlaneRateLimitError


class PlaneAPIClient:
    """Low-level HTTP client for Plane API"""

    def __init__(self, api_url: str, api_token: str, workspace_slug: str):
        self.api_url = api_url.rstrip('/')
        self.api_token = api_token
        self.workspace_slug = workspace_slug
        self.headers = {
            'x-api-key': api_token,
            'Content-Type': 'application/json'
        }

    async def _request(
        self,
        session: aiohttp.ClientSession,
        method: str,
        endpoint: str,
        params: Optional[Dict] = None,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """Make HTTP request to Plane API"""
        url = f"{self.api_url}{endpoint}"

        try:
            async with session.request(
                method=method,
                url=url,
                headers=self.headers,
                params=params,
                json=json_data,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 401:
                    raise PlaneAuthError("Invalid API token")
                elif response.status == 404:
                    raise PlaneNotFoundError(f"Resource not found: {endpoint}")
                elif response.status == 429:
                    raise PlaneRateLimitError("Rate limit exceeded")
                elif response.status >= 400:
                    error_text = await response.text()
                    raise PlaneAPIError(f"HTTP {response.status}: {error_text}")

                return await response.json()

        except aiohttp.ClientError as e:
            bot_logger.error(f"HTTP request failed: {e}")
            raise PlaneAPIError(f"Request failed: {e}")

    async def get(
        self,
        session: aiohttp.ClientSession,
        endpoint: str,
        params: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """GET request"""
        return await self._request(session, 'GET', endpoint, params=params)

    async def post(
        self,
        session: aiohttp.ClientSession,
        endpoint: str,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """POST request"""
        return await self._request(session, 'POST', endpoint, json_data=json_data)

    async def patch(
        self,
        session: aiohttp.ClientSession,
        endpoint: str,
        json_data: Optional[Dict] = None
    ) -> Dict[str, Any]:
        """PATCH request"""
        return await self._request(session, 'PATCH', endpoint, json_data=json_data)

    async def delete(
        self,
        session: aiohttp.ClientSession,
        endpoint: str
    ) -> Dict[str, Any]:
        """DELETE request"""
        return await self._request(session, 'DELETE', endpoint)
