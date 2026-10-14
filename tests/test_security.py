"""The API's guards (see server.py "Who may use the API"), without a browser.

Covers what the e2e test can't reach from this computer: a phone (another
address on the network) gets the token in the setup page only through the QR
link's ?t=, and device error text is cleaned before the panel shows it.
"""
import asyncio
import sys
import tempfile
from pathlib import Path
from unittest import mock

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from aiohttp.test_utils import make_mocked_request  # noqa: E402

from wallvol.server import error_text, make_app  # noqa: E402
from wallvol.store import Store  # noqa: E402

LAN = "192.168.1.78"


def request(app, path, remote):
    transport = mock.Mock()
    transport.get_extra_info.side_effect = lambda k, d=None: (remote, 50000) if k == "peername" else d
    return make_mocked_request("GET", path, headers={"Host": f"{LAN}:8080"}, app=app, transport=transport)


async def run():
    app = make_app(Store(Path(tempfile.mkdtemp())), f"http://{LAN}:8080/setup", 8080, LAN, token="tok123")
    setup = next(r.handler for r in app.router.routes() if r.resource and r.resource.canonical == "/setup")
    has = lambda resp: 'name="wallvol-token" content="tok123"' in resp.text
    assert has(await setup(request(app, "/setup", "127.0.0.1"))), "this computer (loopback)"
    assert has(await setup(request(app, "/setup", LAN))), "this computer (its own LAN address)"
    assert not has(await setup(request(app, "/setup", "192.168.1.50"))), "a phone without the QR link"
    assert not has(await setup(request(app, "/setup?t=wrong", "192.168.1.50"))), "a wrong ?t="
    assert has(await setup(request(app, "/setup?panel=panel-1&t=tok123", "192.168.1.50"))), "the QR link"

    # --host with a specific address (no --lan): that address is an allowed host name
    hosts = lambda a: next(m for m in a.middlewares)  # noqa: E731
    app2 = make_app(Store(Path(tempfile.mkdtemp())), "http://192.168.1.5:8080/setup", 8080, None, token="t", host="192.168.1.5")
    ok = await hosts(app2)(make_mocked_request("GET", "/", headers={"Host": "192.168.1.5:8080"}, app=app2),
                          lambda r: asyncio.sleep(0, result="passed"))
    assert ok == "passed", ok
    bad = await hosts(app2)(make_mocked_request("GET", "/", headers={"Host": "evil.example:8080"}, app=app2),
                           lambda r: asyncio.sleep(0, result="passed"))
    assert bad.status == 421, bad

    text = error_text(RuntimeError("<img src=x onerror=alert(1)>\n\x07" + "x" * 500))
    assert "\n" not in text and "\x07" not in text and len(text) <= 160, text
    print("test_security: ok (token only for this computer or the QR link; --host allowed; error text cleaned)")


asyncio.run(run())
