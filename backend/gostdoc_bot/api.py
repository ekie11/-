"""Клиент API ГОСТ-форматировщика с заголовками бота."""

from __future__ import annotations

from typing import Literal
from urllib.parse import quote

import httpx

UNAVAILABLE = "Сервис временно недоступен, попробуйте позже"


class ApiError(Exception):
    def __init__(self, status: int, detail: str) -> None:
        super().__init__(detail)
        self.status = status
        self.detail = detail


class ApiClient:
    def __init__(
        self,
        base_url: str,
        secret: str,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._secret = secret
        self._http = httpx.AsyncClient(
            base_url=base_url.rstrip("/"), transport=transport, timeout=60
        )

    async def aclose(self) -> None:
        await self._http.aclose()

    def _headers(self, user_id: int, name: str | None) -> dict[str, str]:
        headers = {"X-Bot-Secret": self._secret, "X-Telegram-User": str(user_id)}
        if name:
            headers["X-Telegram-Name"] = quote(name)
        return headers

    async def _request(
        self, method: str, path: str, user_id: int, name: str | None, **kw
    ) -> httpx.Response:
        try:
            resp = await self._http.request(
                method, path, headers=self._headers(user_id, name), **kw
            )
        except httpx.HTTPError as exc:
            raise ApiError(0, UNAVAILABLE) from exc
        if resp.is_success:
            return resp
        detail = UNAVAILABLE
        try:
            body = resp.json()
            if isinstance(body, dict) and isinstance(body.get("detail"), str):
                detail = body["detail"]
        except ValueError:
            pass
        raise ApiError(resp.status_code, detail)

    async def _json(self, method: str, path: str, user_id: int, name: str | None, **kw):
        try:
            return (await self._request(method, path, user_id, name, **kw)).json()
        except ValueError as exc:
            raise ApiError(0, UNAVAILABLE) from exc

    async def profiles(self, user_id: int, name: str | None) -> list[dict]:
        return await self._json("GET", "/profiles", user_id, name)

    async def create_job(
        self,
        user_id: int,
        name: str | None,
        file: tuple[str, bytes] | None,
        text: str | None,
        profile_id: str,
        mode: str,
    ) -> dict:
        data = {"profile_id": profile_id, "mode": mode}
        files = None
        if file is not None:
            files = {"file": file}
        if text is not None:
            data["text"] = text
        return await self._json("POST", "/jobs", user_id, name, data=data, files=files)

    async def job(self, user_id: int, name: str | None, id: str) -> dict:
        return await self._json("GET", f"/jobs/{id}", user_id, name)

    async def download(
        self, user_id: int, name: str | None, id: str, kind: Literal["docx", "pdf"]
    ) -> bytes:
        return (await self._request("GET", f"/jobs/{id}/{kind}", user_id, name)).content

    async def jobs(self, user_id: int, name: str | None) -> list[dict]:
        return await self._json("GET", "/jobs", user_id, name)

    async def create_extraction(
        self,
        user_id: int,
        name: str | None,
        file: tuple[str, bytes] | None,
        text: str | None,
        base_profile_id: str,
    ) -> dict:
        data = {"base_profile_id": base_profile_id}
        if text is not None:
            data["text"] = text
        files = {"file": file} if file is not None else None
        return await self._json("POST", "/extractions", user_id, name, data=data, files=files)

    async def extraction(self, user_id: int, name: str | None, id: str) -> dict:
        return await self._json("GET", f"/extractions/{id}", user_id, name)

    async def quota(self, user_id: int, name: str | None) -> dict:
        return await self._json("GET", "/extractions/quota", user_id, name)

    async def create_profile_from_extraction(
        self, user_id: int, name: str | None, id: str, accepted: list[int], profile_name: str
    ) -> dict:
        body = {"accepted": accepted, "name": profile_name}
        return await self._json("POST", f"/extractions/{id}/profile", user_id, name, json=body)

    async def profile_json(self, user_id: int, name: str | None, id: str) -> bytes:
        return (await self._request("GET", f"/profiles/{id}/export", user_id, name)).content

    async def config(self) -> dict:
        try:
            resp = await self._http.get("/config")
            resp.raise_for_status()
            return resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise ApiError(0, UNAVAILABLE) from exc
