"""End-to-end test of the web prototype: clicks through the panel and the phone
setup like a person would, in a real (headless) Chromium.

Runs its own server on port 8099 (WALLVOL_E2E_PORT) with a throwaway settings folder and Matter
port, so it never touches your demo. Needs the network scan to work (it uses
the demo devices, so no real device is changed).

  .venv/bin/pip install playwright && .venv/bin/python -m playwright install chromium
  .venv/bin/python tests/e2e_test.py            # add --headed to watch
"""

import json
import os
import re
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
from pathlib import Path

from playwright.sync_api import expect, sync_playwright

ROOT = Path(__file__).resolve().parent.parent
# Ports from the environment, so two runs (e.g. a reviewer's and yours) don't collide
PORT = int(os.environ.get("WALLVOL_E2E_PORT", "8099"))
MATTER_PORT = int(os.environ.get("WALLVOL_E2E_MATTER_PORT", "5599"))
BASE = f"http://127.0.0.1:{PORT}"
results = []
_page = None


def check(name, fn):
    try:
        fn()
        results.append((name, None))
        print(f"  ✓ {name}")
    except Exception as e:  # report and keep going
        results.append((name, e))
        try:
            _page.screenshot(path=f"/tmp/e2e-fail-{len(results)}.png")
        except Exception:
            pass
        msg = (str(e) or repr(e)).splitlines()
        hint = " | ".join(l.strip() for l in msg[-3:]) if len(msg) > 1 else ""
        print(f"  ✗ {name}: {msg[0][:200]} {hint[:200]}")


TOKEN = ""   # the server's per-launch API token, read from its settings folder


def api(path):
    req = urllib.request.Request(BASE + path, headers={"X-Wallvol-Token": TOKEN})
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def raw(path, method="GET", body=None, headers=None, port=PORT):
    """A request with exactly these headers; returns the HTTP status."""
    req = urllib.request.Request(f"http://127.0.0.1:{port}{path}", data=body, headers=headers or {}, method=method)
    try:
        with urllib.request.urlopen(req, timeout=10) as r:
            return r.status
    except urllib.error.HTTPError as e:
        return e.code


def panel():
    return api("/api/panels")["panels"][0]


def start_server(home):
    global TOKEN
    # PYTHONPATH: run this checkout's code, even if .venv has another one installed
    env = {**os.environ, "WALLVOL_MATTER_PORT": str(MATTER_PORT), "PYTHONPATH": str(ROOT)}
    proc = subprocess.Popen([str(ROOT / ".venv/bin/wallvol"), "--home", home, "--port", str(PORT)],
                            cwd=ROOT, env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, stdin=subprocess.PIPE)
    for _ in range(100):
        try:
            TOKEN = (Path(home) / "credentials" / "api-token").read_text().strip()
            api("/api/panels")
            return proc
        except Exception:
            time.sleep(0.2)
    raise RuntimeError("test server didn't start")


def main(headed=False):
    home = tempfile.mkdtemp(prefix="wallvol-e2e-")
    server = start_server(home)
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=not headed)
            page = browser.new_page(viewport={"width": 1600, "height": 1300})
            global _page
            _page = page
            page.on("dialog", lambda d: d.accept())       # confirm() for resets
            errors = []
            page.on("pageerror", lambda e: errors.append(str(e)))
            page.goto(BASE + "/")
            phone = page.frame_locator("#phoneFrame")

            print("Security")
            def api_locked_down():
                tok = {"X-Wallvol-Token": TOKEN, "Content-Type": "application/json"}
                assert raw("/api/panels") == 403, "no token"
                assert raw("/api/panels", headers={"X-Wallvol-Token": "wrong"}) == 403, "wrong token"
                assert raw("/api/panels", headers={"X-Wallvol-Token": TOKEN}) == 200, "right token"
                # a website posting blind: text/plain, no token / with a token but text/plain
                assert raw("/api/start-over", "POST", b"{}", {"Content-Type": "text/plain"}) in (403, 415)
                assert raw("/api/start-over", "POST", b"{}", {**tok, "Content-Type": "text/plain"}) == 415
                assert raw("/api/units", "POST", b'{"units":"F"}', {**tok, "Origin": "https://evil.example"}) == 403
                # DNS rebinding: an attacker's host name pointing at us
                assert raw("/api/panels", headers={**tok, "Host": f"evil.example:{PORT}"}) == 421
                assert raw("/", headers={"Host": f"evil.example:{PORT}"}) == 421
                # the Matter bridge answers only the server (secret) on its own host name
                assert raw("/nodes", port=MATTER_PORT) == 403, "bridge without secret"
            check("API: token, JSON + origin, host allowlist; Matter bridge needs its secret", api_locked_down)

            def token_only_for_this_computer():
                html = page.request.get(BASE + "/").text()
                assert 'name="wallvol-token"' in html, "local page gets the token"
            check("pages loaded on this computer carry the token", token_only_for_this_computer)

            def error_shown_as_text():
                # a device's error text (e.g. a Sonos HTTP 500 body) must never run as HTML
                page.evaluate("""() => { const k = state.knobs[0] || newKnob(); state.knobs[0] = k;
                    Object.assign(state, { configured: true });
                    k.speaker = { id: 'x', room: 'X', brand: 'X', name: 'X', control: 'level' };
                    k.connected = false; k.error = '<img src=x onerror="window.pwned=1">'; render(); }""")
                time.sleep(0.5)
                assert page.evaluate("() => window.pwned") is None, "error text ran as HTML"
                expect(page.locator("#sConn")).to_contain_text("<img src=x")
                page.reload()
            check("a device's error text is shown as text, never run", error_shown_as_text)

            print("Setup")
            def knob_turns_on_setup_screen():
                # a real knob turns whatever the screen shows: here, the SET UP code
                face = page.locator(".knob .face").first
                before = face.evaluate("e => e.style.transform")
                page.locator(".knob").first.focus()
                page.keyboard.press("ArrowUp"); page.keyboard.press("ArrowUp")
                after = face.evaluate("e => e.style.transform")
                assert before != after and "rotate(" in after, (before, after)
            check("the knob visibly turns even on the setup screen", knob_turns_on_setup_screen)
            check("new panel shows the setup code", lambda: expect(page.locator("#setupTitle")).to_have_text("SET UP"))

            def open_phone_and_scan():
                page.locator("#screen").click()
                expect(page.locator("#phone")).to_have_class("phone open")
                phone.get_by_role("button", name="Continue").click()
                phone.get_by_role("button", name="Join Network").click()
                expect(phone.get_by_text("Add by code or account")).to_be_visible(timeout=40000)
            check("phone setup reaches the device list", open_phone_and_scan)
            check("list has the account and code options", lambda: [
                expect(phone.locator("#addMatter")).to_be_visible(),
                expect(phone.locator("#addHuum")).to_be_visible(),
                expect(phone.locator("#addTraeger")).to_be_visible()])
            check("demo devices are hidden until asked", lambda: expect(phone.locator("#demoList")).to_be_hidden())

            def huum_wrong_login():
                phone.locator("#addHuum").click()
                expect(phone.get_by_role("heading", name="Connect a HUUM sauna")).to_be_visible()
                phone.locator("#auser").fill("nobody@example.com")
                phone.locator("#apass").fill("wrong")
                phone.get_by_role("button", name="Sign In").click()
                expect(phone.locator(".error")).to_contain_text("HUUM rejected", timeout=30000)
            check("HUUM sauna opens sign-in and reports a wrong login", huum_wrong_login)

            def traeger_screen():
                page.locator("#phoneFrame").evaluate("f => f.contentWindow.scan()")
                expect(phone.locator("#addTraeger")).to_be_visible(timeout=40000)
                phone.locator("#addTraeger").click()
                expect(phone.get_by_role("heading", name="Connect a Traeger grill")).to_be_visible()
            check("Traeger grill opens its sign-in", traeger_screen)

            def traeger_wrong_login():
                phone.locator("#auser").fill("nobody@example.com")
                phone.locator("#apass").fill("wrong-Password1")
                phone.get_by_role("button", name="Sign In").click()
                expect(phone.locator(".error")).to_be_visible(timeout=30000)
            check("Traeger reports a wrong login", traeger_wrong_login)

            def matter_bad_code():
                page.locator("#phoneFrame").evaluate("f => f.contentWindow.scan()")
                expect(phone.locator("#addMatter")).to_be_visible(timeout=40000)
                phone.locator("#addMatter").click()
                phone.locator("#mcode").fill("123")
                phone.get_by_role("button", name="Add Device").click()
                expect(phone.locator(".error")).to_contain_text("11-digit")
            check("Matter device asks for a valid pairing code", matter_bad_code)

            def demo_setup():
                page.locator("#phoneFrame").evaluate("f => f.contentWindow.scan()")
                expect(phone.locator("#showDemo")).to_be_visible(timeout=40000)
                phone.locator("#showDemo").click()
                phone.get_by_text("Outside Light 1 (demo)").click()
                phone.get_by_role("button", name="Finish Setup").click()
                expect(phone.get_by_text("is ready")).to_be_visible(timeout=20000)
                expect(page.locator("#room")).to_have_text("Outside Light 1 (demo)", timeout=10000)
            check("a demo device can be set up end to end", demo_setup)

            print("Panel")
            def knob_turn():
                page.locator("#knob, .knob").first.focus()
                page.keyboard.press("ArrowUp")
                time.sleep(1)
                assert panel()["knobs"][0]["volume"] == 100, panel()["knobs"][0]
            check("turning the knob right switches the light on", knob_turn)

            def first_lock_sets_code():
                page.keyboard.down("l"); time.sleep(6.4); page.keyboard.up("l")
                expect(page.locator(".code .title")).to_have_text("SET CODE")
                page.keyboard.type("1234")
                expect(page.locator(".code .title")).to_have_text("CONFIRM CODE")
                page.keyboard.type("1234")
                time.sleep(1)
                assert panel()["locked"] and panel()["has_passcode"], panel()
            check("first hold asks SET CODE / CONFIRM CODE, then locks", first_lock_sets_code)

            def wrong_then_right_code():
                page.locator("#screen").click()
                expect(page.locator(".code .title")).to_have_text("ENTER CODE")
                page.keyboard.type("0000")
                expect(page.locator("#codeMsg")).to_have_text("WRONG CODE")
                page.keyboard.type("1234")
                time.sleep(1)
                assert not panel()["locked"], panel()
            check("wrong code refused, right code unlocks", wrong_then_right_code)

            def nfc_unlock():
                page.keyboard.down("l"); time.sleep(6.4); page.keyboard.up("l")
                time.sleep(1)
                assert panel()["locked"]
                expect(page.locator("#nfc")).to_be_visible(timeout=5000)
                page.locator("#nfc").click()
                phone.get_by_role("button", name="Unlock with Face ID").click()
                expect(phone.get_by_role("heading", name="Unlocked")).to_be_visible(timeout=10000)
                time.sleep(2)
                assert not panel()["locked"]
            check("Tap iPhone (NFC) unlocks with a signed message", nfc_unlock)

            print("Master Volume")
            def post(path, body):
                req = urllib.request.Request(BASE + path, data=json.dumps(body).encode(),
                                             headers={"Content-Type": "application/json", "X-Wallvol-Token": TOKEN}, method="POST")
                with urllib.request.urlopen(req, timeout=60) as r:
                    return json.load(r)

            def levels():
                return {d["id"]: d for d in panel()["devices"]}

            def master_menu():
                # two demo speakers at 40 and 20, so there's something to balance
                pid = panel()["id"]
                api(f"/api/panels/{pid}/setup/scan")
                for sid, level in (("patio-speaker-demo", 20), ("kitchen-speaker-demo", 40)):
                    post(f"/api/panels/{pid}/setup/finish", {"speaker": sid, "knob": 0})
                    time.sleep(0.5)
                    post(f"/api/panels/{pid}/volume", {"level": level, "knob": 0})
                time.sleep(2)
                names = [d["room"] for d in panel()["devices"]]
                assert "Master Volume" in names, names
                knob = page.locator(".knob").first
                for _ in range(3):
                    knob.click()
                expect(page.locator(".menu .title")).to_have_text("MENU", timeout=5000)
                page.locator("#menuList li", has_text="Devices").click()
                expect(page.locator("#menuList")).to_contain_text("Master Volume", timeout=5000)
                page.locator("#menuList li", has_text="Master Volume").click()
                time.sleep(2)
                assert panel()["knobs"][0]["speaker"]["id"] == "master", panel()["knobs"][0]
            check("triple-click opens the menu → Devices, which offers Master Volume", master_menu)

            def master_keeps_balance():
                page.locator(".knob").first.focus()
                for _ in range(5):
                    page.keyboard.press("ArrowUp")   # +10 % on the loudest
                time.sleep(2)
                k = panel()["knobs"][0]
                assert round(k["volume"]) == 50, k
            check("Master Volume shows the loudest speaker's level after turning", master_keeps_balance)

            def master_scaled_both():
                # read each speaker through the API by pointing knob 0 at it in turn
                pid = panel()["id"]
                got = {}
                for sid in ("kitchen-speaker-demo", "patio-speaker-demo"):
                    post(f"/api/panels/{pid}/select", {"speaker": sid, "knob": 0})
                    time.sleep(1.5)
                    got[sid] = round(panel()["knobs"][0]["volume"])
                assert got == {"kitchen-speaker-demo": 50, "patio-speaker-demo": 25}, got
                post(f"/api/panels/{pid}/select", {"speaker": "master", "knob": 0})
            check("both speakers moved together, keeping their 2:1 balance", master_scaled_both)


            print("Sauna start / stop")
            def long_press(locator, seconds=2.9):
                box = locator.bounding_box()
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.mouse.down(); time.sleep(seconds); page.mouse.up()

            def sauna_knob_sets_target_only():
                pid = panel()["id"]
                post(f"/api/panels/{pid}/setup/finish", {"speaker": "sauna-demo", "knob": 0})
                time.sleep(2)
                post(f"/api/panels/{pid}/volume", {"level": 0, "knob": 0})   # make sure it's off
                time.sleep(2)
                expect(page.locator("#powerLabel")).to_have_text("HOLD TO START", timeout=5000)
                page.locator(".knob").first.focus()
                page.keyboard.press("ArrowUp"); page.keyboard.press("ArrowUp")
                time.sleep(1.5)
                assert panel()["knobs"][0]["volume"] == 0, panel()["knobs"][0]
            check("turning the knob on an off sauna only sets the target", sauna_knob_sets_target_only)

            def sauna_long_press_starts():
                page.locator("#screen").click()            # wake
                long_press(page.locator("#powerBtn"))
                time.sleep(1.5)
                assert panel()["knobs"][0]["volume"] > 0, panel()["knobs"][0]
            check("long press starts the sauna", sauna_long_press_starts)

            def sauna_timer():
                # the session countdown under the ring, and the ring nearly full
                expect(page.locator("#powerLabel")).to_have_text(re.compile(r"^[23]:\d\d:\d\d$"), timeout=8000)
                off = float(page.locator("#timerLeft").evaluate("e => parseFloat(e.style.strokeDashoffset)"))
                assert 0 <= off < 5, off
            check("a running sauna shows a draining ring and the time left", sauna_timer)

            def units_screen():
                page.locator("#screen").click(position={"x": 8, "y": 8}); time.sleep(0.3)   # wake (a corner, not the number)
                page.locator("#number").click(); page.locator("#number").click()
                expect(page.locator(".menu .title")).to_have_text("UNITS")
                page.locator("#menuList li", has_text="°C").click()
                time.sleep(1.5)
                assert api("/api/panels")["units"] == "C"
                f = panel()["knobs"][0]["volume"]          # target in % of 110-195 °F
                c = round(((110 + f / 100 * 85) - 32) * 5 / 9)
                expect(page.locator("#number")).to_contain_text(str(c))
                page.locator("#number").click(); page.locator("#number").click()
                page.keyboard.press("ArrowLeft")            # knob works on the units screen too (up the list)
                page.locator(".knob").first.click()
                time.sleep(1.5)
                assert api("/api/panels")["units"] == "F"
            check("double-tapping the temperature switches °F / °C (touch and knob)", units_screen)

            def sauna_list():
                page.locator("#screen").click(position={"x": 8, "y": 8}); time.sleep(0.3)
                page.locator("#room").click()
                expect(page.locator(".menu .title")).to_have_text("SAUNAS")
                expect(page.locator("#menuList")).to_contain_text("Sauna (demo)")
                expect(page.locator("#menuList")).not_to_contain_text("+ Add sauna")   # off for now (one sauna)
                expect(page.locator("#menuList")).not_to_contain_text("speaker (demo)")
                page.locator("#menuList li", has_text="Exit").click()
                expect(page.locator("#display")).not_to_have_class(re.compile(r"menu-mode"))
            check("tapping the name lists every sauna (no + Add sauna for now)", sauna_list)

            def sauna_short_tap_does_nothing():
                page.locator("#powerBtn").click()
                time.sleep(1.5)
                assert panel()["knobs"][0]["volume"] > 0, panel()["knobs"][0]
            check("a short tap doesn't stop it", sauna_short_tap_does_nothing)

            def sauna_long_press_stops():
                long_press(page.locator("#powerBtn"))
                time.sleep(1.5)
                assert panel()["knobs"][0]["volume"] == 0, panel()["knobs"][0]
                expect(page.locator("#powerLabel")).to_have_text("HOLD TO START")
            check("long press stops the sauna", sauna_long_press_stops)

            def knob_hold_starts_sauna():
                knob = page.locator(".knob").first
                box = knob.bounding_box()
                page.mouse.move(box["x"] + box["width"] / 2, box["y"] + box["height"] / 2)
                page.mouse.down(); time.sleep(4.2)          # past the 3 s when the red ring would start
                ring = page.locator(".knob .holdRing").first
                assert "filling" not in (ring.get_attribute("class") or ""), "red lock ring shown"
                page.mouse.up()
                time.sleep(1.5)
                assert panel()["knobs"][0]["volume"] > 0, panel()["knobs"][0]
                assert not panel()["locked"]
                long_press(knob)
                time.sleep(1.5)
                assert panel()["knobs"][0]["volume"] == 0, panel()["knobs"][0]
                expect(page.locator("#powerLabel")).to_have_text("HOLD TO START")
            check("holding the knob on a sauna starts / stops it like the icon (no red ring)", knob_hold_starts_sauna)

            def rename():
                knob = page.locator(".knob").first
                for _ in range(3):
                    knob.click()
                expect(page.locator(".menu .title")).to_have_text("MENU", timeout=5000)
                page.locator("#menuList li", has_text="Settings").click()
                page.locator("#menuList li", has_text="Name").click()
                expect(page.locator(".menu .title")).to_have_text("SETTINGS")     # the panel stays on Settings
                expect(page.locator("#phone")).to_have_class("phone open")
                expect(phone.locator("#rname")).to_have_value("Sauna (demo)", timeout=10000)
                phone.locator("#rname").fill("Crane Sauna")
                phone.get_by_role("button", name="Save").click()
                expect(phone.get_by_text("Renamed to Crane Sauna")).to_be_visible(timeout=10000)
                page.locator("#phoneClose").click()
                expect(page.locator("#menuList li", has_text="Name")).to_contain_text("Crane Sauna", timeout=6000)
                page.locator("#menuList li", has_text="‹ Back").click()
                page.locator("#menuList li", has_text="Exit").click()
                expect(page.locator("#room")).to_have_text("Crane Sauna", timeout=6000)
            check("Settings → Name renames the sauna on the iPhone", rename)

            def unscrew_opens_viewer():
                sc = page.locator(".screw").first
                sc.click(); sc.click()
                angle = sc.evaluate("e => e.style.transform")
                assert "rotate(-120deg)" in angle, angle
                assert page.url.rstrip("/") == BASE, page.url                  # two turns: still here
                sc.click()                                                     # third: spins out, opens the viewer
                page.wait_for_url("**/hardware/viewer.html", timeout=5000)
                page.goto(BASE + "/")
                expect(page.locator("#display")).to_be_attached()
                time.sleep(2)
            check("clicking a screw turns it counterclockwise; the third click opens the 3D viewer", unscrew_opens_viewer)

            def factory_reset():
                page.locator("#reset").click()
                expect(page.locator("#setupTitle")).to_have_text("SET UP", timeout=10000)
                expect(page.locator("#sDriver")).to_have_text("Knob 1")
                expect(page.locator("#sLatency")).to_have_text("—")
            def brightness_settings():
                knob = page.locator(".knob").first
                for _ in range(3):
                    knob.click()
                expect(page.locator(".menu .title")).to_have_text("MENU", timeout=5000)
                page.locator("#menuList li", has_text="Settings").click()
                expect(page.locator(".menu .title"), "step 1").to_have_text("SETTINGS")
                expect(page.locator("#menuList")).to_contain_text("Dim Brightness")
                page.locator("#menuList li", has_text="Brightness").first.click()
                expect(page.locator("#adjustTitle")).to_have_text("BRIGHTNESS")
                knob.focus()
                for _ in range(4):
                    page.keyboard.press("ArrowDown")       # 100 → 80
                expect(page.locator("#adjustValue")).to_have_text("80%")
                knob.click()                                # push saves
                time.sleep(1.5)
                assert panel()["screen"]["brightness"] == 80, panel()["screen"]
                op = page.locator("#display").evaluate("e => getComputedStyle(e).opacity")
                assert abs(float(op) - 0.8) < 0.01, op
                expect(page.locator(".menu .title"), "step 2").to_have_text("SETTINGS")   # back to Settings, not the main screen
                page.locator("#menuList li", has_text="Dim Brightness").click()
                expect(page.locator("#adjustTitle")).to_have_text("DIM BRIGHTNESS")
                expect(page.locator("#adjustValue")).to_have_text("5%")
                page.keyboard.press("ArrowUp")              # 5 → 10
                page.locator("#screen").click()             # tap saves too
                time.sleep(1.5)
                assert panel()["screen"]["dim"] == 10, panel()["screen"]
                page.locator("#menuList li", has_text="Temperature").click()
                expect(page.locator(".menu .title")).to_have_text("UNITS")
                page.locator("#menuList li", has_text="°F").click()
                expect(page.locator(".menu .title"), "step 3").to_have_text("SETTINGS")
                page.locator("#menuList li", has_text="Auto Update").click()
                expect(page.locator(".menu .title"), "step 4").to_have_text("SETTINGS")
                expect(page.locator("#menuList li", has_text="Auto Update")).to_contain_text("Off")
                time.sleep(1.5)
                assert panel()["auto_update"] is False, panel()
                page.locator("#menuList li", has_text="Auto Update").click()
                time.sleep(1.5)
                assert panel()["auto_update"] is True, panel()
                page.locator("#menuList li", has_text="Brightness").first.click()
                time.sleep(7)                               # idle on a setting: saved, back to SETTINGS
                expect(page.locator(".menu .title"), "step 5").to_have_text("SETTINGS")
                time.sleep(7)                               # idle on SETTINGS closes it
                post(f"/api/panels/{panel()['id']}/screen", {"brightness": 100, "dim": 5})
                time.sleep(2)
            check("Settings: Brightness, Dim Brightness, Temperature, Auto Update; every exit returns to Settings", brightness_settings)

            def menu_navigation():
                knob = page.locator(".knob").first
                title = page.locator(".menu .title")
                def clicks(n):
                    for _ in range(n):
                        knob.click()
                    time.sleep(0.6)                         # past the click gap
                clicks(3); expect(title).to_have_text("MENU")
                page.locator("#menuList li", has_text="Settings").click(); expect(title).to_have_text("SETTINGS")
                page.locator("#menuList li", has_text="Dim Brightness").click()
                expect(page.locator("#adjustTitle")).to_have_text("DIM BRIGHTNESS")
                clicks(3); expect(title).to_have_text("MENU")                  # three clicks: top, from anywhere
                page.locator("#menuList li", has_text="Settings").click()
                page.locator("#menuList li", has_text="Temperature").click(); expect(title).to_have_text("UNITS")
                clicks(2); expect(title).to_have_text("SETTINGS")              # double click = back, like the iPod's MENU
                clicks(2); expect(title).to_have_text("MENU")
                page.locator("#menuList li", has_text="Devices").click(); expect(title).to_have_text("DEVICES")
                page.locator("#menuList li", has_text="‹ Back").click(); expect(title).to_have_text("MENU")
                page.locator("#menuList li", has_text="Exit").click()
                expect(page.locator("#display")).not_to_have_class(re.compile(r"menu-mode"))
            check("three clicks = MENU from anywhere; double click / ‹ Back = up one level; Exit", menu_navigation)

            def dims_to_5():
                page.locator("#screen").click()
                expect(page.locator("#display")).to_have_class(re.compile(r"\boff\b"), timeout=12000)
                time.sleep(0.6)
                op = page.locator("#display").evaluate("e => getComputedStyle(e).opacity")
                assert abs(float(op) - 0.05) < 0.01, op
            check("an idle screen dims to 5 %, not black", dims_to_5)

            check("factory reset clears the panel and the status lines", factory_reset)

            check("no JavaScript errors", lambda: (_ for _ in ()).throw(AssertionError(errors)) if errors else None)
            browser.close()
    finally:
        server.terminate()
    failed = [n for n, e in results if e]
    print(f"\n{len(results) - len(failed)} passed, {len(failed)} failed")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main(headed="--headed" in sys.argv))
