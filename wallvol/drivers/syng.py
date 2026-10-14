"""Syng driver: JSON-RPC 2.0 over a secure WebSocket on the primary Cell.

The Syng Space app uses `source_set_volume` on wss://<primary-cell>:8765. No
login or token is needed. The Cell's certificate is signed by Syng's private CA,
so verification is off. A stereo pair follows its primary, so `host` must be the
Cell advertising role=primary in its _syng._tcp mDNS record.

Reading the current volume isn't solved yet (see docs/FINDINGS.md#syng), so
get_volume returns the last level this driver set, or None before the first set.
"""

import itertools
import json
import ssl
from typing import Any, Optional

import aiohttp

from .base import Driver


class SyngDriver(Driver):
    kind = "syng"
    brand = "Syng"
    audio = True

    def __init__(self, host: str, source: str = "airplay2", **options: Any) -> None:
        super().__init__(host, **options)
        self.source = source
        self._session: Optional[aiohttp.ClientSession] = None
        self._ws: Optional[aiohttp.ClientWebSocketResponse] = None
        self._ids = itertools.count(1)
        self._last: Optional[float] = None

    async def connect(self) -> None:
        await self.close()
        ctx = ssl.create_default_context()
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        self._session = aiohttp.ClientSession()
        self._ws = await self._session.ws_connect(
            f"wss://{self.host}:8765/", ssl=ctx, timeout=5, heartbeat=20
        )

    async def _call(self, method: str, params: dict) -> Any:
        if self._ws is None or self._ws.closed:
            await self.connect()
        request_id = next(self._ids)
        await self._ws.send_str(
            json.dumps({"jsonrpc": "2.0", "id": request_id, "method": method, "params": params})
        )
        while True:
            msg = await self._ws.receive(timeout=5)
            if msg.type != aiohttp.WSMsgType.TEXT:
                raise ConnectionError(f"Syng closed the connection ({msg.type.name})")
            reply = json.loads(msg.data)
            if reply.get("id") == request_id:
                if "error" in reply:
                    raise RuntimeError(f"{method} failed: {reply['error']}")
                return reply.get("result")

    async def get_volume(self) -> Optional[float]:
        return self._last

    async def set_volume(self, level: float) -> None:
        await self._call("source_set_volume", {"source_id": self.source, "volume": level / 100})
        self._last = level

    async def close(self) -> None:
        if self._ws is not None:
            await self._ws.close()
        if self._session is not None:
            await self._session.close()
        self._ws = self._session = None
