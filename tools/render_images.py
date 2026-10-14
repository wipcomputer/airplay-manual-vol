"""Render the README images from the web prototype's own styling.

Builds static pages that reuse the CSS in wallvol/web/index.html, puts the
panel in fixed states, and screenshots them with headless Chrome. Re-run it
after changing the panel's look so the README never drifts from the demo.

Usage: python tools/render_images.py [--chrome PATH]
Writes docs/images/panel-front.png, one-knob-switching.png, panel-three-knobs.png
and screen-states.png.
"""

import argparse
import re
import subprocess
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUT = ROOT / "docs" / "images"
CHROME = "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome"

LOCK_SVG = ('<svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="1.3">'
            '<rect x="5" y="11" width="14" height="10"/><path d="M8 11V8a4 4 0 0 1 8 0v3"/></svg>')
QR_JS = "https://cdnjs.cloudflare.com/ajax/libs/qrcodejs/1.0.0/qrcode.min.js"


DEFAULT_MENU = [("LIVING ROOM", "HomePod", True, True, True), ("DEN", "Syng", True, False, False),
                ("BEDROOM", "Sonos", False, False, False)]


def display(state: str, room: str = "LIVING ROOM", level: int = 42, number: str = "", dots: str = "",
            menu_items: list = None) -> str:
    """The screen's inner markup, in one of the panel's states."""
    classes = {"idle": "off", "volume": "", "muted": "muted", "locked": "locked",
               "setup": "setup-mode", "add": "setup-mode", "devices": "menu-mode",
               "offline": "offline"}[state]
    fill = 0 if state == "muted" else level
    menu = ""
    if state == "devices":
        # (name, brand, connected, highlighted, active)
        lis = "".join(
            f'<li class="{"hl" if hl else ""}"><span class="dot {"" if on else "off"}"></span>'
            f'<span class="label">{r}{" ●" if cur else ""}<small>{b}</small></span></li>'
            for r, b, on, hl, cur in (menu_items or DEFAULT_MENU))
        menu = lis + '<li class="add"><span class="label">+ Add device</span></li>'
    title = "ADD DEVICE" if state == "add" else "SET UP"
    return f"""
      <div class="display {classes}">
        <div class="room">{room}</div>
        <div class="kdots">{dots}</div>
        <div class="track"><div class="fill" style="height:{fill}%"></div></div>
        <div class="number">{number or level}</div>
        <div class="mute"></div>
        <div class="lock">{LOCK_SVG}<span>ENTER CODE</span><span class="or">OR TAP IPHONE</span></div>
        <div class="no-speaker">OFFLINE</div>
        <div class="menu"><div class="title">DEVICES</div><ul>{menu}</ul></div>
        <div class="setup"><div class="title">{title}</div><div class="qr"></div><div class="hint">SCAN WITH IPHONE</div></div>
      </div>"""


PLATE_MM = {2: 114.3, 3: 160.3, 4: 206.4}
GANG_MM = 46.04


def plate(state: str = "volume", knobs: int = 1, **screen) -> str:
    """A Decora plate with `knobs` knob gangs and the screen gang, at real proportions."""
    gangs = knobs + 1
    w = PLATE_MM[gangs]
    x = lambda i: f"{(w / 2 + (i - (gangs - 1) / 2) * GANG_MM) / w * 100:.3f}%"
    screws = "".join(f'<div class="screw" style="left:{x(i)};top:{t}"></div>'
                     for i in range(gangs) for t in ("9.5%", "90.5%"))
    knob_gangs = "".join(f'<div class="insert left" style="left:{x(i)}"><div class="knob"><div class="knurl"></div>'
                         f'<div class="face"></div></div></div>' for i in range(knobs))
    return f"""
  <div class="plate" style="--w:{w}">
    {screws}{knob_gangs}
    <div class="insert right" style="left:{x(gangs - 1)}"><div class="screen">{display(state, **screen)}</div></div>
  </div>"""


def page(css: str, body: str, extra_css: str = "") -> str:
    return f"""<!doctype html><html><head><meta charset="utf-8">
<link rel="stylesheet" href="https://fonts.googleapis.com/css2?family=Jost:wght@300;400;500&display=swap">
<style>{css}
  body {{ min-height: 0; padding: 0; background: #d6d7d9; color: #1d1d1f; }}
  .display {{ transition: none !important; }}
  .knob {{ cursor: default; }}
  {extra_css}
</style></head><body>{body}
<script src="{QR_JS}"></script>
<script>
  document.querySelectorAll('.qr').forEach(el => new QRCode(el, {{ text: 'https://github.com/', width: 256, height: 256,
    colorDark: '#0a0a0a', colorLight: '#f4f4f2', correctLevel: QRCode.CorrectLevel.M }}));
</script></body></html>"""


def front(css: str) -> str:
    body = f"""
<div class="shot">
  {plate("volume")}
  <div class="caption"><b>MODEL 01</b>SCREEN + ENCODER · STAINLESS TWO-GANG PLATE</div>
</div>"""
    extra = """
  :root { color-scheme: light; }
  .shot { width: 1200px; height: 1200px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 70px; }
  .plate { --u: 7.2px; }
  .caption { font-size: 22px; color: #6b6d70; }"""
    return page(css, body, extra)


def switching(css: str) -> str:
    """One knob, one screen: switching the knob to another device."""
    menu = [("LIVING ROOM", "HomePod", True, False, True), ("SAUNA", "HUUM", True, True, False),
            ("OUTSIDE LIGHTS", "Matter plug", True, False, False)]
    steps = [
        (plate("volume"), "1 · LIVING ROOM", "Turn the knob: speaker volume"),
        (plate("devices", menu_items=menu), "2 · TRIPLE-CLICK", "Devices menu: turn, then click"),
        (plate("volume", room="SAUNA", level=82, number='185<span class="unit">°</span>'),
         "3 · SAUNA", "Same knob, now the sauna's temperature"),
    ]
    cells = "".join(f"""
    <figure>{p}<figcaption><b>{t}</b><span>{d}</span></figcaption></figure>
    {'<div class="arrow">→</div>' if i < 2 else ''}""" for i, (p, t, d) in enumerate(steps))
    body = f"""
<div class="shot">
  <div class="head"><b>ONE KNOB · ONE SCREEN</b>SWITCH WHAT THE KNOB CONTROLS</div>
  <div class="row">{cells}</div>
</div>"""
    extra = """
  .shot { width: 2000px; padding: 60px 50px; }
  .head { font-size: 20px; letter-spacing: .24em; color: #6b6d70; margin: 0 0 50px 30px; }
  .head b { color: #1d1d1f; font-weight: 500; margin-right: 1.4em; }
  .row { display: flex; align-items: center; justify-content: center; gap: 26px; }
  .plate { --u: 4.6px; }
  figure { margin: 0; display: flex; flex-direction: column; align-items: center; gap: 26px; }
  figcaption { text-align: center; font-size: 15px; color: #6b6d70; line-height: 1.6; }
  figcaption b { display: block; font-weight: 500; letter-spacing: .24em; color: #1d1d1f; font-size: 17px; }
  .arrow { font-size: 40px; color: #8b8d90; margin-bottom: 70px; }"""
    return page(css, body, extra)


def multi(css: str) -> str:
    body = f"""
<div class="shot">
  {plate("volume", knobs=3, room="SAUNA", level=82, number='185<span class="unit">°</span>',
         dots='KNOB 2')}
  <div class="caption"><b>MODEL 01 · 3 KNOBS</b>LIVING ROOM · SAUNA · OUTSIDE LIGHT, ONE SCREEN</div>
</div>"""
    extra = """
  .shot { width: 1600px; height: 1000px; display: flex; flex-direction: column; align-items: center; justify-content: center; gap: 60px; }
  .plate { --u: 6.6px; }
  .caption { font-size: 20px; color: #6b6d70; }"""
    return page(css, body, extra)


def states(css: str) -> str:
    shots = [("idle", "01 IDLE", "Dark glass until touch or turn"),
             ("volume", "02 VOLUME", "Bar tracks the knob · tap or slide it"),
             ("muted", "03 MUTED", "Red circle · level remembered"),
             ("locked", "04 LOCKED", "Hold to lock · code or iPhone to unlock"),
             ("setup", "05 SETUP", "Scan to set up the panel"),
             ("devices", "06 DEVICES", "Triple-push the knob · pick a speaker"),
             ("add", "ADD DEVICE", "Add a speaker from the menu"),
             ("offline", "OFFLINE", "Active speaker unreachable")]
    cells = "".join(f"""
    <figure>
      <div class="frame"><div class="screen">{display(s)}</div></div>
      <figcaption><b>{t}</b><span>{d}</span></figcaption>
    </figure>""" for s, t, d in shots)
    body = f"""
<div class="shot">
  <div class="head"><b>SCREEN STATES</b>BLACK GLASS FILLING THE DECORA OPENING</div>
  <div class="row">{cells}</div>
</div>"""
    extra = """
  .shot { width: 2000px; padding: 70px 60px 60px; }
  .head { font-size: 20px; letter-spacing: .24em; color: #6b6d70; margin: 0 0 50px 20px; }
  .head b { color: #1d1d1f; font-weight: 500; margin-right: 1.4em; }
  .row { display: grid; grid-template-columns: repeat(4, 1fr); gap: 50px 40px; }
  figure { margin: 0; display: flex; flex-direction: column; align-items: center; gap: 22px; }
  .frame { --u: 6.6px; width: calc(33 * var(--u)); height: calc(60.5 * var(--u)); padding: 10px;
           background: linear-gradient(180deg, #dfe1e3, #cfd2d5); border-radius: 8px;
           box-shadow: 0 10px 24px rgba(0,0,0,.14); }
  figcaption { text-align: center; font-size: 15px; color: #6b6d70; line-height: 1.6; }
  figcaption b { display: block; font-weight: 500; letter-spacing: .24em; color: #1d1d1f; font-size: 17px; }"""
    return page(css, body, extra)


def shoot(chrome: str, html: str, out: Path, size: tuple) -> None:
    with tempfile.NamedTemporaryFile("w", suffix=".html", delete=False) as f:
        f.write(html)
    subprocess.run([chrome, "--headless=new", "--hide-scrollbars", "--force-device-scale-factor=1",
                    f"--window-size={size[0]},{size[1]}", "--virtual-time-budget=8000",
                    f"--screenshot={out}", f"file://{f.name}"],
                   check=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    Path(f.name).unlink()
    print(f"wrote {out.relative_to(ROOT)}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--chrome", default=CHROME)
    args = parser.parse_args()
    index = (ROOT / "wallvol" / "web" / "index.html").read_text()
    css = re.search(r"<style>(.*?)</style>", index, re.S).group(1)
    OUT.mkdir(parents=True, exist_ok=True)
    shoot(args.chrome, front(css), OUT / "panel-front.png", (1200, 1200))
    shoot(args.chrome, states(css), OUT / "screen-states.png", (2000, 1300))
    shoot(args.chrome, multi(css), OUT / "panel-three-knobs.png", (1600, 1000))
    shoot(args.chrome, switching(css), OUT / "one-knob-switching.png", (2000, 820))


if __name__ == "__main__":
    main()
