"""HUUM driver against a real status reply (captured 2026-10-13: numbers arrive as strings)."""
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from wallvol.drivers.huum import HuumDriver, c_to_f  # noqa: E402

REAL = {"maxHeatingTime": "3", "statusCode": 231, "door": True, "config": 0, "temperature": "90",
        "targetTemperature": "90", "startDate": 1791932270, "endDate": 1791943070, "duration": 70,
        "remoteSafetyState": "safe"}


async def run():
    d = HuumDriver("huum:account", username="x", password="y")

    sent = []

    async def fake_call(method, action, json=None):
        sent.append((method, action, json))
        d._last = dict(REAL)
        return d._last
    d._call = fake_call
    d.status = lambda: fake_call("GET", "status")
    level = await d.get_volume()
    target_f = d.display_min + level / 100 * (d.display_max - d.display_min)
    assert round(target_f) == round(c_to_f(90)), (level, target_f)          # 194 °F
    # heating: the session start / end come along for the panel's timer ring
    assert await d.get_reading() == {"now": round(c_to_f(90)), "starts": 1791932270, "ends": 1791943070}, await d.get_reading()
    # changing the target while heating keeps the session (no timer reset)
    await d.set_volume(50)
    assert sent[-1] == ("POST", "start", {"targetTemperature": 75, "startDate": 1791932270, "endDate": 1791943070}), sent[-1]
    REAL["door"] = False
    await d.status()                     # the driver reads the door from its latest status
    assert (await d.get_reading())["text"] == "DOOR OPEN"
    REAL["statusCode"] = 232            # online, not heating
    assert await d.get_volume() == 0.0
    REAL["door"] = True
    await d.set_volume(50)                # starting fresh: a new session
    assert sent[-1] == ("POST", "start", {"targetTemperature": 75}), sent[-1]
    print("test_huum: ok (target 194 °F, NOW 194°, door open, not heating, target change keeps the session)")


asyncio.run(run())
