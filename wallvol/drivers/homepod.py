"""HomePod driver: Apple's remote-control (MRP) protocol tunnelled over AirPlay.

Uses pyatv, plus two additions that password-protected HomePods need (see
docs/FINDINGS.md#homepod):

1. Saved credentials from a one-time pairing (spike/homepod_pair.py), with the
   MRP tunnel forced on. pyatv otherwise only opens it with transient pairing.
2. RFC 2617 Digest auth (user "AirPlay") on the tunnel's RTSP SETUP, which pyatv
   doesn't do. Added by patching pyatv's HttpConnection below.

Connects with the AirPlay protocol only: if RAOP is also connected, pyatv
answers volume from RAOP's local state and nothing reaches the speaker.
"""

import asyncio
import hashlib
import re
from typing import Any, Optional

import pyatv
from pyatv import exceptions
from pyatv.const import Protocol
from pyatv.settings import MrpTunnel
from pyatv.storage.memory_storage import MemoryStorage
from pyatv.support.http import HttpConnection

from .base import Driver

# AirPlay password per HomePod IP, filled in by HomePodDriver
_PASSWORDS: dict = {}
_orig_send = HttpConnection.send_and_receive


def _digest(password, method, uri, realm, nonce):
    md5 = lambda v: hashlib.md5(v.encode()).hexdigest()
    ha1 = md5(f"AirPlay:{realm}:{password}")
    resp = md5(f"{ha1}:{nonce}:{md5(f'{method}:{uri}')}")
    return (
        f'Digest username="AirPlay", realm="{realm}", nonce="{nonce}", '
        f'uri="{uri}", response="{resp}"'
    )


async def _send_with_digest(self, method, uri, *args, headers=None, allow_error=False, **kw):
    password = _PASSWORDS.get(self.remote_ip) if self.transport else None
    headers = dict(headers or {})
    challenge = getattr(self, "_digest_challenge", None)
    if challenge and password:
        headers["Authorization"] = _digest(password, method, uri, *challenge)
    resp = await _orig_send(self, method, uri, *args, headers=headers, allow_error=True, **kw)
    auth = resp.headers.get("WWW-Authenticate", "") if resp.code == 401 else ""
    if auth.startswith("Digest") and password:
        realm = re.search(r'realm="([^"]*)"', auth).group(1)
        nonce = re.search(r'nonce="([^"]*)"', auth).group(1)
        self._digest_challenge = (realm, nonce)
        headers["Authorization"] = _digest(password, method, uri, realm, nonce)
        # Retry must keep the same CSeq, or pyatv's RTSP layer never matches the reply
        resp = await _orig_send(self, method, uri, *args, headers=headers, allow_error=True, **kw)
    if not allow_error and not 200 <= resp.code < 300:
        raise exceptions.HttpError(f"{method} {uri} failed: {resp.code}", resp.code)
    return resp


HttpConnection.send_and_receive = _send_with_digest


class HomePodDriver(Driver):
    kind = "homepod"
    brand = "HomePod"
    audio = True

    def __init__(
        self,
        host: str,
        credentials: Optional[str] = None,
        password: Optional[str] = None,
        **options: Any,
    ) -> None:
        super().__init__(host, **options)
        self.credentials_file = credentials
        self.password = password
        self._atv = None

    async def connect(self) -> None:
        await self.close()
        if self.password:
            _PASSWORDS[self.host] = self.password
        loop = asyncio.get_running_loop()
        confs = await pyatv.scan(loop, hosts=[self.host], timeout=5)
        if not confs:
            raise ConnectionError(f"no HomePod found at {self.host}")
        conf = confs[0]
        if self.credentials_file:
            creds = open(self.credentials_file).read().strip()
            for proto in (Protocol.AirPlay, Protocol.RAOP):
                conf.set_credentials(proto, creds)
        storage = MemoryStorage()
        settings = await storage.get_settings(conf)
        settings.protocols.airplay.mrp_tunnel = MrpTunnel.Force
        self._atv = await pyatv.connect(conf, loop, protocol=Protocol.AirPlay, storage=storage)
        await asyncio.sleep(2)  # the tunnel delivers the current volume shortly after connecting

    async def get_volume(self) -> Optional[float]:
        return float(self._atv.audio.volume)

    async def set_volume(self, level: float) -> None:
        try:
            await self._atv.audio.set_volume(level)
        except asyncio.TimeoutError:
            # pyatv waits up to 5 s for the HomePod to echo the new level; the
            # command was still sent, so a missing echo isn't fatal
            pass

    async def close(self) -> None:
        if self._atv is not None:
            self._atv.close()
            self._atv = None
