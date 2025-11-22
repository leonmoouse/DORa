from typing import Any, Dict, Optional

import httpx


async def post_json(url: str, headers: Optional[Dict[str, str]] = None, data: Optional[Dict[str, Any]] = None, timeout: float = 120.0) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.post(url, headers=headers, json=data)
        response.raise_for_status()
        return response


async def get_json(url: str, headers: Optional[Dict[str, str]] = None, timeout: float = 120.0) -> httpx.Response:
    async with httpx.AsyncClient(timeout=timeout) as client:
        response = await client.get(url, headers=headers)
        response.raise_for_status()
        return response
