"""HUUM sauna (UKU controller) through HUUM's cloud API.

The same API the HUUM app and Home Assistant's integration use: HTTPS with
the HUUM account's email and password (HTTP Basic auth) at
https://sauna.huum.eu/action/home/{status,start,stop}. Temperatures are °C,
40-110. Cloud only: needs internet.

The knob sets the target temperature, shown in °F. Level 0 (turned all the
way down, or the mute circle) turns the sauna off.

Safety: like the HUUM app, starting is refused while the sauna door is open.
"""

from typing import Any, Optional

import aiohttp

from .base import Driver

# api.huum.eu answers a bad login with a proper 403 JSON error; the older
# sauna.huum.eu host (used by the Home Assistant library) answers it with an
# empty 200. Try the current one first, fall back if it's unreachable.
APIS = ("https://api.huum.eu/action/home/", "https://sauna.huum.eu/action/home/")
MIN_C, MAX_C = 40, 110
HEATING = 231
OFFLINE = 230


def num(v) -> Optional[float]:
    """HUUM sends numbers as strings ("90") or numbers; None if missing/blank."""
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def c_to_f(c: float) -> float:
    return c * 9 / 5 + 32


class HuumDriver(Driver):
    kind = "huum"
    brand = "HUUM"
    control = "temperature"
    startable = True     # long-press start / stop, like the HUUM app
    unit = "°F"
    display_min, display_max = c_to_f(MIN_C), c_to_f(MAX_C)   # 104-230 °F

    def __init__(self, host: str, username: str = "", password: str = "", **options: Any) -> None:
        super().__init__(host, **options)
        import base64
        token = base64.b64encode(f"{username}:{password}".encode()).decode()
        self._headers = {"Authorization": f"Basic {token}"}
        self._api = APIS[0]
        self._session: Optional[aiohttp.ClientSession] = None
        self._last: dict = {}

    async def _call(self, method: str, action: str, json: Optional[dict] = None) -> dict:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        try:
            return await self._request(self._api, method, action, json)
        except aiohttp.ClientConnectionError:
            other = APIS[1] if self._api == APIS[0] else APIS[0]
            result = await self._request(other, method, action, json)
            self._api = other
            return result

    async def _request(self, base: str, method: str, action: str, json: Optional[dict]) -> dict:
        async with self._session.request(method, base + action, headers=self._headers, json=json) as r:
            text = await r.text()
            if r.status in (401, 403):
                raise PermissionError("HUUM rejected the email or password")
            r.raise_for_status()
            if not text.strip():
                # the older host's way of saying the login is wrong
                raise PermissionError("HUUM rejected the email or password")
            import json as _json
            data = _json.loads(text)
            if isinstance(data, dict) and data.get("state", {}).get("code") in (401, 403):
                raise PermissionError("HUUM rejected the email or password")
            return data

    async def status(self) -> dict:
        self._last = await self._call("GET", "status")
        return self._last

    async def connect(self) -> None:
        status = await self.status()
        if status.get("statusCode") == OFFLINE:
            raise ConnectionError("the sauna is offline (check its Wi-Fi)")

    def _level(self, celsius: float) -> float:
        return max(1.0, min(100.0, (celsius - MIN_C) / (MAX_C - MIN_C) * 100))

    async def get_volume(self) -> Optional[float]:
        status = await self.status()
        if status.get("statusCode") != HEATING:
            return 0.0
        target = num(status.get("targetTemperature"))
        return self._level(target) if target is not None else None

    async def get_reading(self) -> Optional[dict]:
        if self._last.get("statusCode") == OFFLINE:
            return {"text": "OFFLINE"}
        current = num(self._last.get("temperature"))
        reading = {"now": round(c_to_f(current))} if current is not None else {}
        end = num(self._last.get("endDate"))
        if self._last.get("statusCode") == HEATING and end:
            reading["ends"] = int(end)          # epoch seconds; the panel counts down to it
            start = num(self._last.get("startDate"))
            if start:
                reading["starts"] = int(start)  # so the panel's timer ring knows the session length
        if self._last and not self._last.get("door", True):
            reading["text"] = "DOOR OPEN"
        return reading or None

    async def set_volume(self, level: float) -> None:
        if level <= 0:
            await self._call("POST", "stop")
            return
        celsius = round(MIN_C + level / 100 * (MAX_C - MIN_C))
        status = await self.status()
        heating = status.get("statusCode") == HEATING
        if not heating and not status.get("door", False):
            raise PermissionError("close the sauna door to start it")
        body = {"targetTemperature": celsius}
        if heating and status.get("startDate") and status.get("endDate"):
            # "start" otherwise begins a new session, so a target change would
            # reset the timer to a fresh 3 h: keep the running session's times
            body["startDate"], body["endDate"] = status["startDate"], status["endDate"]
        await self._call("POST", "start", json=body)

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()
