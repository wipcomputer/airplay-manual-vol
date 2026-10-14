"""Set a Syng Cell's volume over its local JSON-RPC WebSocket (works mid-AirPlay).

The Syng Space app controls Cells with JSON-RPC 2.0 over a secure WebSocket on
port 8765 of the room's primary Cell. The Cell's certificate is self-signed by
Syng's own CA, so verification is turned off here. No login or token is needed.

Volume is 0.0-1.0 and applies to an audio source; "airplay2" is the AirPlay
source, so this changes the volume of whatever is AirPlaying to the Cells, no
matter which device started it. A stereo pair follows its primary.

Usage: syng_volume.py HOST LEVEL [--source airplay2]
  LEVEL is 0-100 (converted to 0.0-1.0).
"""

import argparse
import asyncio
import json
import ssl

import aiohttp


async def call(host, method, params):
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE  # Cells present a cert signed by Syng's private CA
    request = {"jsonrpc": "2.0", "id": 1, "method": method, "params": params}
    async with aiohttp.ClientSession() as session:
        async with session.ws_connect(f"wss://{host}:8765/", ssl=ctx, timeout=5) as ws:
            await ws.send_str(json.dumps(request))
            reply = await ws.receive(timeout=5)
            return json.loads(reply.data)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("host", help="the primary Cell (role=primary in its _syng._tcp TXT record)")
    parser.add_argument("level", type=float, help="volume 0-100")
    parser.add_argument("--source", default="airplay2")
    args = parser.parse_args()
    params = {"source_id": args.source, "volume": max(0.0, min(args.level, 100.0)) / 100}
    print(asyncio.run(call(args.host, "source_set_volume", params)))
