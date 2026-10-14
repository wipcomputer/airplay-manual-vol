"""Read or set a HomePod's volume using saved pairing credentials.

Forces pyatv's remote-control (MRP) tunnel, which pyatv normally only opens for
HomePods with transient credentials, and answers the Digest challenge that
password-protected HomePods send on the tunnel's RTSP SETUP.

Usage: homepod_volume.py HOST CREDS_FILE [get | set N | half] [--password PW]
"""

import argparse
import asyncio
import hashlib
import re

import pyatv
from pyatv import exceptions
from pyatv.const import Protocol
from pyatv.settings import MrpTunnel
from pyatv.storage.memory_storage import MemoryStorage
from pyatv.support.http import HttpConnection

PASSWORD = None

# Password-protected receivers require RFC 2617 Digest (user "AirPlay") on requests
# inside the encrypted channel; pyatv doesn't do this, so wrap send_and_receive.
_orig_send = HttpConnection.send_and_receive


def _digest(method, uri, realm, nonce):
    md5 = lambda v: hashlib.md5(v.encode()).hexdigest()
    ha1 = md5(f"AirPlay:{realm}:{PASSWORD}")
    resp = md5(f"{ha1}:{nonce}:{md5(f'{method}:{uri}')}")
    return (
        f'Digest username="AirPlay", realm="{realm}", nonce="{nonce}", '
        f'uri="{uri}", response="{resp}"'
    )


async def _send_with_digest(self, method, uri, *args, headers=None, allow_error=False, **kw):
    headers = dict(headers or {})
    challenge = getattr(self, "_digest_challenge", None)
    if challenge and PASSWORD:
        headers["Authorization"] = _digest(method, uri, *challenge)
    resp = await _orig_send(self, method, uri, *args, headers=headers, allow_error=True, **kw)
    auth = resp.headers.get("WWW-Authenticate", "") if resp.code == 401 else ""
    if auth.startswith("Digest") and PASSWORD:
        realm = re.search(r'realm="([^"]*)"', auth).group(1)
        nonce = re.search(r'nonce="([^"]*)"', auth).group(1)
        self._digest_challenge = (realm, nonce)
        headers["Authorization"] = _digest(method, uri, realm, nonce)
        # Retry must keep the same CSeq, or pyatv's RTSP layer never matches the reply
        resp = await _orig_send(self, method, uri, *args, headers=headers, allow_error=True, **kw)
    if not allow_error and not 200 <= resp.code < 300:
        raise exceptions.HttpError(f"{method} {uri} failed: {resp.code}", resp.code)
    return resp


HttpConnection.send_and_receive = _send_with_digest


async def main(args):
    loop = asyncio.get_running_loop()
    confs = await pyatv.scan(loop, hosts=[args.host], timeout=5)
    if not confs:
        raise SystemExit(f"no device found at {args.host}")
    conf = confs[0]
    creds = open(args.creds_file).read().strip()
    for proto in (Protocol.AirPlay, Protocol.RAOP):
        conf.set_credentials(proto, creds)
    storage = MemoryStorage()
    settings = await storage.get_settings(conf)
    settings.protocols.airplay.mrp_tunnel = MrpTunnel.Force
    # AirPlay only: if RAOP is connected it answers volume from its own local state,
    # so reads and sets "succeed" without ever reaching the speaker
    atv = await pyatv.connect(conf, loop, protocol=Protocol.AirPlay, storage=storage)
    try:
        await asyncio.sleep(2)  # let the tunnel deliver the current volume
        print("volume", round(atv.audio.volume, 1))
        if args.action in ("set", "half"):
            target = args.value if args.action == "set" else atv.audio.volume / 2
            await atv.audio.set_volume(target)
            await asyncio.sleep(1)
            print("now", round(atv.audio.volume, 1))
    finally:
        atv.close()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("host")
    parser.add_argument("creds_file")
    parser.add_argument("action", nargs="?", default="get", choices=["get", "set", "half"])
    parser.add_argument("value", nargs="?", type=float)
    parser.add_argument("--password", help="AirPlay password, if the HomePod has one")
    args = parser.parse_args()
    if args.action == "set" and args.value is None:
        parser.error("set needs a volume (0-100)")
    PASSWORD = args.password
    asyncio.run(main(args))
