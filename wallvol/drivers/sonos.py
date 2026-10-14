"""Sonos driver: local UPnP RenderingControl on port 1400, via SoCo.

No pairing, account or Sonos app needed, and it works while the speaker is
playing an AirPlay stream. See docs/FINDINGS.md#sonos.
"""

import asyncio
from typing import Optional

import soco

from .base import Driver


class SonosDriver(Driver):
    kind = "sonos"
    brand = "Sonos"
    audio = True

    async def connect(self) -> None:
        self._zone = soco.SoCo(self.host)

    async def get_volume(self) -> Optional[float]:
        # SoCo is synchronous HTTP; keep it off the event loop
        return float(await asyncio.to_thread(lambda: self._zone.volume))

    async def set_volume(self, level: float) -> None:
        await asyncio.to_thread(setattr, self._zone, "volume", round(level))
