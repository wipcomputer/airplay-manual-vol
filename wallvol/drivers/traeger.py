"""Traeger WiFIRE grill through Traeger's cloud (unofficial).

No public API; this follows what the Traeger app does, as documented by the
community Home Assistant integrations (johnvoipguy/Traeger-WiFire,
nocturnal11/homeassistant-traeger):

- Sign in with the Traeger app login through AWS Cognito (us-west-2,
  USER_PASSWORD_AUTH) to get an ID token.
- GET  mobile-iot-api.iot.traegergrills.io/users/self   -> the account's grills ("things")
- POST .../mqtt-connections -> a pre-signed MQTT-over-WebSocket URL; status
  arrives on prod/thing/update/<thing> as JSON {"status": {...}}.
- POST .../things/<thing>/commands {"command": "..."}: "90" asks for a fresh
  status, "11,<°F>" sets the grill temperature.

Safety: the panel can only change the set temperature while the grill is
already cooking. It never ignites, starts or shuts down the grill; level 0 is
ignored. The screen shows the grill's actual temperature as the reading.
"""

import asyncio
import json
import ssl
import time
import uuid
from typing import Any, Optional
from urllib.parse import urlparse

import aiohttp
import paho.mqtt.client as mqtt

from .base import Driver

COGNITO = "https://cognito-idp.us-west-2.amazonaws.com/"
CLIENT_ID = "4id473dsrcq4kevlgrikukqn2a"   # the Traeger app's; changes occasionally
API = "https://mobile-iot-api.iot.traegergrills.io"
MIN_F, MAX_F = 165, 500
COOKING = range(4, 9)   # system_status values while the grill is running (per the HA integration)


class TraegerDriver(Driver):
    kind = "traeger"
    brand = "Traeger"
    control = "temperature"
    unit = "°F"
    display_min, display_max = MIN_F, MAX_F

    def __init__(self, host: str, username: str = "", password: str = "", thing: str = "", **options: Any) -> None:
        super().__init__(host, **options)
        self.username, self.password, self.thing = username, password, thing
        self._session: Optional[aiohttp.ClientSession] = None
        self._token, self._token_expires = None, 0.0
        self._mqtt: Optional[mqtt.Client] = None
        self._mqtt_expires = 0.0
        self.status: dict = {}          # latest grill status from MQTT
        self.status_time = 0.0

    # ---- cloud ----

    async def _http(self) -> aiohttp.ClientSession:
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=15))
        return self._session

    async def _sign_in(self) -> None:
        if self._token and time.time() < self._token_expires - 60:
            return
        s = await self._http()
        body = {"AuthFlow": "USER_PASSWORD_AUTH", "ClientId": CLIENT_ID, "ClientMetadata": {},
                "AuthParameters": {"USERNAME": self.username, "PASSWORD": self.password}}
        headers = {"Content-Type": "application/x-amz-json-1.1",
                   "X-Amz-Target": "AWSCognitoIdentityProviderService.InitiateAuth"}
        async with s.post(COGNITO, data=json.dumps(body), headers=headers) as r:
            data = await r.json(content_type=None)
        if "AuthenticationResult" not in data:
            raise PermissionError(f"Traeger sign-in failed: {data.get('message') or data.get('__type') or data}")
        self._token = data["AuthenticationResult"]["IdToken"]
        self._token_expires = time.time() + data["AuthenticationResult"]["ExpiresIn"]

    async def _api(self, method: str, path: str, body: Optional[dict] = None) -> Any:
        await self._sign_in()
        s = await self._http()
        async with s.request(method, API + path, json=body, headers={"Authorization": self._token}) as r:
            if r.status >= 400:
                raise ConnectionError(f"Traeger {path}: HTTP {r.status}")
            return await r.json(content_type=None) if r.content_length != 0 else None

    async def grills(self) -> list:
        data = await self._api("GET", "/users/self")
        return data.get("things", []) if isinstance(data, dict) else []

    async def _command(self, command: str) -> None:
        await self._api("POST", f"/things/{self.thing}/commands", {"command": command})

    # ---- status stream (MQTT over a pre-signed WebSocket URL) ----

    async def _start_mqtt(self) -> None:
        if self._mqtt is not None and time.time() < self._mqtt_expires - 60:
            return
        if self._mqtt is not None:
            self._mqtt.loop_stop()
            self._mqtt.disconnect()
        conn = await self._api("POST", "/mqtt-connections")
        self._mqtt_expires = time.time() + conn["expirationSeconds"]
        url = urlparse(conn["signedUrl"])
        client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"wallvol-{uuid.uuid4()}",
                             transport="websockets")
        client.ws_set_options(path=f"{url.path}?{url.query}")
        client.tls_set_context(ssl.create_default_context())
        topic = f"prod/thing/update/{self.thing}"
        client.on_connect = lambda c, *_: c.subscribe(topic, qos=1)

        def on_message(_c, _u, msg):
            try:
                self.status = json.loads(msg.payload).get("status", {})
                self.status_time = time.time()
            except ValueError:
                pass

        client.on_message = on_message
        client.connect_async(url.hostname, 443)
        client.loop_start()   # paho's own thread
        self._mqtt = client

    async def _fresh_status(self, wait: float = 8.0) -> dict:
        await self._start_mqtt()
        if time.time() - self.status_time > 30:
            since = self.status_time
            await self._command("90")   # ask the grill to publish its status
            deadline = time.time() + wait
            while self.status_time == since and time.time() < deadline:
                await asyncio.sleep(0.25)
        return self.status

    # ---- driver interface ----

    async def connect(self) -> None:
        grills = await self.grills()
        if not grills:
            raise ConnectionError("no grills on this Traeger account")
        if not self.thing:
            self.thing = grills[0]["thingName"]
            self.options["friendly_name"] = grills[0].get("friendlyName", "")
        await self._fresh_status()

    def _cooking(self) -> bool:
        return bool(self.status.get("connected")) and self.status.get("system_status") in COOKING

    def _level(self, f: float) -> float:
        return max(1.0, min(100.0, (f - MIN_F) / (MAX_F - MIN_F) * 100))

    async def get_volume(self) -> Optional[float]:
        s = await self._fresh_status(wait=0) if self.status else await self._fresh_status()
        if not self._cooking():
            return 0.0
        return self._level(s.get("set", MIN_F)) if s.get("set") else None

    async def get_reading(self) -> Optional[dict]:
        s = self.status
        if not s.get("connected"):
            return {"text": "OFFLINE"}
        reading = {"now": s.get("grill")} if s.get("grill") is not None else {}
        if s.get("probe_con"):
            reading["probe"] = s.get("probe")
        return reading

    async def set_volume(self, level: float) -> None:
        if level <= 0:
            return   # never shut down or start from the panel
        await self._fresh_status(wait=0)
        if not self._cooking():
            raise PermissionError("start the grill first: the panel only adjusts a grill that's cooking")
        target = int(round((MIN_F + level / 100 * (MAX_F - MIN_F)) / 5) * 5)   # Traeger steps in 5 °F
        await self._command(f"11,{target}")

    async def close(self) -> None:
        if self._mqtt is not None:
            self._mqtt.loop_stop()
            self._mqtt.disconnect()
        if self._session is not None:
            await self._session.close()
