"""Matter drivers: plugs, lights and dimmers, through the local Matter bridge.

The bridge (wallvol/matter/bridge.mjs, matter.js) joins devices as an extra
controller using a pairing code from the Home app, so Apple Home keeps
working. Each outlet or light (Matter endpoint) is its own device here, e.g.
the two outlets of a Tapo P400M are two devices.

host is "matter:<node id>/<endpoint>".
"""

import os
from typing import Any, Optional

import aiohttp

from .base import Driver


def bridge_url() -> str:
    return f"http://127.0.0.1:{os.environ.get('WALLVOL_MATTER_PORT', '5541')}"


def bridge_headers() -> dict:
    """The per-launch secret the server gave the bridge (it refuses requests without it)."""
    return {"X-Wallvol-Secret": os.environ.get("WALLVOL_MATTER_SECRET", "")}


class _MatterDriver(Driver):
    def __init__(self, host: str, **options: Any) -> None:
        super().__init__(host, **options)
        node, _, ep = host.removeprefix("matter:").partition("/")
        self.node, self.ep = node, int(ep or 1)
        self._session: Optional[aiohttp.ClientSession] = None

    async def _call(self, method: str, path: str, **kw) -> dict:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15), headers=bridge_headers())
        async with self._session.request(method, bridge_url() + path, **kw) as r:
            data = await r.json()
            if r.status != 200:
                raise ConnectionError(data.get("error", f"bridge HTTP {r.status}"))
            return data

    async def connect(self) -> None:
        state = await self._call("GET", f"/state?node={self.node}&ep={self.ep}")
        if not state.get("connected", True):
            raise ConnectionError("Matter device not reachable")

    async def close(self) -> None:
        if self._session is not None:
            await self._session.close()


class MatterSwitchDriver(_MatterDriver):
    kind = "matter-switch"
    brand = "Matter plug"
    control = "switch"
    unit = ""

    async def get_volume(self) -> Optional[float]:
        state = await self._call("GET", f"/state?node={self.node}&ep={self.ep}")
        return 100.0 if state["on"] else 0.0

    async def set_volume(self, level: float) -> None:
        await self._call("POST", "/set", json={"node": self.node, "ep": self.ep, "on": level > 0})


class MatterDimmerDriver(_MatterDriver):
    kind = "matter-dimmer"
    brand = "Matter dimmer"

    async def get_volume(self) -> Optional[float]:
        state = await self._call("GET", f"/state?node={self.node}&ep={self.ep}")
        if not state["on"]:
            return 0.0
        return float(state["level"]) if state.get("level") is not None else 100.0

    async def set_volume(self, level: float) -> None:
        await self._call("POST", "/set", json={"node": self.node, "ep": self.ep, "level": level})
