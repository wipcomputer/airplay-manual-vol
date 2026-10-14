"""3D models of the Model 01 wall mockup (hardware/PARTS.md, section B).

Builds every part with CadQuery and writes:
  hardware/models/*.stl          every part, for the 3D viewer
  hardware/models/print/*.stl    the parts you 3D-print or laser-cut
  hardware/models/print/*.step   the same, for Fusion / Onshape / SolidWorks
  hardware/models/print/screen-acrylic.dxf   the acrylic outline for laser cutting
  hardware/models/parts.json     where each part sits, its colour and how it explodes
                                 (the viewer reads this, so it can't drift from the CAD)

Run:  .venv-cad/bin/python hardware/cad/model.py
(create it with: python3 -m venv .venv-cad && .venv-cad/bin/pip install cadquery)

Coordinates in millimetres: X across the wall, Y up, Z out of the wall.
The wall surface is Z = 0; the electrical box is behind it (Z < 0).

Printed parts (strap + face per gang, board housing, encoder bracket) are
designed here. Bought parts (board, encoder, knob, wall plate, box) are
simplified stand-ins with their key dimensions, for fit and for the viewer.
Dimensions marked APPROX need checking against the real part.
"""

import json
from pathlib import Path

import cadquery as cq

OUT = Path(__file__).resolve().parent.parent / "models"

# ---- Standards -------------------------------------------------------------
GANG = 46.04            # Decora gang spacing (1.8125")
BOX_SCREWS = 83.34      # device-to-box screw spacing (3.281")
PLATE_SCREWS = 96.84    # wall-plate-to-device screw spacing (3.8125")
OPENING_W, OPENING_H = 33.3, 66.8   # Decora opening in the wall plate
PLATE_H = 114.3
PLATE_W = {2: 114.3, 3: 160.3, 4: 206.4}
PLATE_D = 6.0           # plate depth off the wall
PLATE_SKIN = 1.6        # plate front thickness

# ---- Our printed parts -----------------------------------------------------
STRAP_W, STRAP_H, STRAP_T = 44.0, 104.0, 2.5    # printed strap (yoke)
FACE_W, FACE_H = OPENING_W - 0.6, OPENING_H - 0.6   # 0.3 mm clearance each side
FACE_Z0, FACE_Z1 = STRAP_T, PLATE_D + 0.4        # face pokes 0.4 mm proud of the plate
ACRYLIC_T = 1.5
SCREW_HOLE = 3.6        # clearance for #6-32

# ---- Bought parts (APPROX unless noted) -------------------------------------
BOARD_W, BOARD_H, BOARD_T = 26.0, 52.0, 9.0     # Waveshare ESP32-S3-Touch-LCD-1.9, APPROX
SCREEN_W, SCREEN_H = 22.7, 42.7                  # 1.9" 170x320 active area
ENC_BODY = (12.4, 13.2, 6.5)                     # EC11 / PEC11R body (W, H, D)
ENC_BUSHING_D, ENC_BUSHING_L = 7.0, 7.0          # M7 threaded bushing
ENC_SHAFT_D, ENC_SHAFT_L = 6.0, 15.0
KNOB_D, KNOB_L = 22.0, 16.0
BOX_W, BOX_H, BOX_D, BOX_WALL = 99.0, 95.0, 64.0, 2.5   # 2-gang old-work box, APPROX


def gang_x(i, gangs):
    return (i - (gangs - 1) / 2) * GANG


def strap(x):
    """Printed strap (yoke): screws to the box, holds the face. The wall plate
    screws into it too, like a real Decora device."""
    s = cq.Workplane("XY").rect(STRAP_W, STRAP_H).extrude(STRAP_T).edges("|Z").fillet(2)
    for y in (BOX_SCREWS / 2, -BOX_SCREWS / 2):
        s = s.cut(cq.Workplane("XY").center(0, y).slot2D(8, SCREW_HOLE, 0).extrude(STRAP_T))
    for y in (PLATE_SCREWS / 2, -PLATE_SCREWS / 2):   # plate screws thread into these (#6-32 pilot)
        s = s.cut(cq.Workplane("XY").center(0, y).circle(1.4).extrude(STRAP_T))
    return s.translate((x, 0, 0))


def screen_face(x):
    """Face for the screen gang: fills the Decora opening, with a window for the
    display and a recess for the black acrylic cover."""
    f = (cq.Workplane("XY").workplane(offset=FACE_Z0).rect(FACE_W, FACE_H)
         .extrude(FACE_Z1 - FACE_Z0).edges("|Z").fillet(1.0))
    f = f.cut(cq.Workplane("XY").workplane(offset=FACE_Z0).rect(SCREEN_W + 0.6, SCREEN_H + 0.6)
              .extrude(FACE_Z1 - FACE_Z0))
    f = f.cut(cq.Workplane("XY").workplane(offset=FACE_Z1 - ACRYLIC_T).rect(FACE_W - 2.4, FACE_H - 2.4)
              .extrude(ACRYLIC_T))
    return f.translate((x, 0, 0))


def knob_face(x):
    """Face for a knob gang: fills the opening, with a hole for the encoder's
    M7 bushing (nut on the front)."""
    f = (cq.Workplane("XY").workplane(offset=FACE_Z0).rect(FACE_W, FACE_H)
         .extrude(FACE_Z1 - FACE_Z0).edges("|Z").fillet(1.0))
    f = f.cut(cq.Workplane("XY").workplane(offset=FACE_Z0).circle(ENC_BUSHING_D / 2 + 0.2).extrude(10))
    return f.translate((x, 0, 0))


def board_housing(x):
    """Printed cradle behind the screen face that holds the board against the
    window. Open at the bottom for the USB-C cable."""
    depth = BOARD_T + 4
    h = cq.Workplane("XY").workplane(offset=-depth).rect(BOARD_W + 5, BOARD_H + 5).extrude(depth)
    h = h.cut(cq.Workplane("XY").workplane(offset=-BOARD_T).rect(BOARD_W + 0.6, BOARD_H + 0.6).extrude(BOARD_T))
    h = h.cut(cq.Workplane("XY").workplane(offset=-depth).center(0, -(BOARD_H / 2)).rect(12, 8).extrude(depth))
    return h.translate((x, 0, 0))


def encoder_bracket(x):
    """Printed spacer behind the knob face that keeps the encoder square."""
    t = 4.0
    b = cq.Workplane("XY").workplane(offset=-t).rect(22, 22).extrude(t)
    b = b.cut(cq.Workplane("XY").workplane(offset=-t).rect(ENC_BODY[0] + 0.4, ENC_BODY[1] + 0.4).extrude(t))
    return b.translate((x, 0, 0))


def acrylic(x):
    return (cq.Workplane("XY").workplane(offset=FACE_Z1 - ACRYLIC_T).rect(FACE_W - 2.6, FACE_H - 2.6)
            .extrude(ACRYLIC_T - 0.05).edges("|Z").fillet(0.8).translate((x, 0, 0)))


# ---- Stand-ins for bought parts ---------------------------------------------

def board(x):
    pcb = cq.Workplane("XY").workplane(offset=-BOARD_T).rect(BOARD_W, BOARD_H).extrude(BOARD_T - 1.6)
    glass = cq.Workplane("XY").workplane(offset=-1.6).rect(BOARD_W, BOARD_H - 2).extrude(1.6)
    return pcb.union(glass).translate((x, 0, 0))


def encoder(x):
    bw, bh, bd = ENC_BODY
    body = cq.Workplane("XY").workplane(offset=-bd).rect(bw, bh).extrude(bd)
    bushing = cq.Workplane("XY").circle(ENC_BUSHING_D / 2).extrude(FACE_Z1 + 1)
    shaft = (cq.Workplane("XY").workplane(offset=FACE_Z1 + 1).circle(ENC_SHAFT_D / 2)
             .extrude(ENC_SHAFT_L))
    return body.union(bushing).union(shaft).translate((x, 0, 0))


def knob(x):
    z = FACE_Z1 + 1.5
    k = cq.Workplane("XY").workplane(offset=z).circle(KNOB_D / 2).extrude(KNOB_L).edges(">Z").fillet(1.2)
    return k.translate((x, 0, 0))


def wall_plate(gangs):
    w = PLATE_W[gangs]
    p = cq.Workplane("XY").rect(w, PLATE_H).extrude(PLATE_D).edges("|Z").fillet(2.0)
    p = p.cut(cq.Workplane("XY").rect(w - 2 * 1.6, PLATE_H - 2 * 1.6).extrude(PLATE_D - PLATE_SKIN))
    for i in range(gangs):
        p = p.cut(cq.Workplane("XY").center(gang_x(i, gangs), 0).rect(OPENING_W, OPENING_H).extrude(PLATE_D))
    return p


def electrical_box(gangs):
    w = BOX_W + (gangs - 2) * GANG
    b = cq.Workplane("XY").workplane(offset=-BOX_D).rect(w, BOX_H).extrude(BOX_D)
    b = b.cut(cq.Workplane("XY").workplane(offset=-BOX_D + BOX_WALL).rect(w - 2 * BOX_WALL, BOX_H - 2 * BOX_WALL)
              .extrude(BOX_D))
    return b


# ---- Assembly ---------------------------------------------------------------

def assembly(knobs=1):
    """Every part of a panel with `knobs` knobs and one screen, in place.
    Each entry: (file name, shape, colour, explode distance along Z, printed?, label)."""
    gangs = knobs + 1
    parts = [("box", electrical_box(gangs), "#9aa0a6", -70, False, "Electrical box (2-gang old-work)"),
             ("plate", wall_plate(gangs), "#c9ccd0", 70, False, "Decora wall plate (any brand)")]
    for i in range(knobs):
        x = gang_x(i, gangs)
        n = i + 1
        parts += [
            (f"knob{n}-strap", strap(x), "#30343a", 0, True, f"Knob {n}: printed strap"),
            (f"knob{n}-bracket", encoder_bracket(x), "#30343a", -14, True, f"Knob {n}: printed encoder bracket"),
            (f"knob{n}-encoder", encoder(x), "#b08d57", -28, False, f"Knob {n}: rotary encoder (PEC11R)"),
            (f"knob{n}-face", knob_face(x), "#e6e7e9", 22, True, f"Knob {n}: printed face"),
            (f"knob{n}-knob", knob(x), "#d7dadd", 92, False, f"Knob {n}: knob cap"),
        ]
    x = gang_x(gangs - 1, gangs)
    parts += [
        ("screen-strap", strap(x), "#30343a", 0, True, "Screen: printed strap"),
        ("screen-housing", board_housing(x), "#30343a", -30, True, "Screen: printed board housing"),
        ("screen-board", board(x), "#1f6f4a", -16, False, "Screen: Waveshare ESP32-S3 1.9\" board"),
        ("screen-face", screen_face(x), "#e6e7e9", 22, True, "Screen: printed face"),
        ("screen-acrylic", acrylic(x), "#0b0b0b", 44, True, "Screen: black acrylic cover (laser cut)"),
    ]
    return parts


def main():
    (OUT / "print").mkdir(parents=True, exist_ok=True)
    manifest = {}
    for knobs in (1, 2, 3):
        entries = []
        for name, shape, colour, explode, printed, label in assembly(knobs):
            file = f"{knobs}k-{name}.stl"
            cq.exporters.export(shape, str(OUT / file), tolerance=0.05, angularTolerance=0.1)
            entries.append({"file": file, "name": name, "label": label, "color": colour,
                            "explode": explode, "printed": printed})
            if printed and knobs == 1 or (printed and name.startswith("knob")):
                # Printables don't depend on the knob count; export each once
                base = name.split("-", 1)[1] if name.startswith(("knob", "screen")) else name
                kind = "screen" if name.startswith("screen") else "knob"
                stem = f"{kind}-{base}"
                cq.exporters.export(shape.translate((-shape.val().Center().x, 0, 0)), str(OUT / "print" / f"{stem}.stl"),
                                    tolerance=0.02, angularTolerance=0.05)
                cq.exporters.export(shape.translate((-shape.val().Center().x, 0, 0)), str(OUT / "print" / f"{stem}.step"))
        manifest[str(knobs)] = {"plate_width": PLATE_W[knobs + 1], "parts": entries}
        print(f"{knobs} knob(s): {len(entries)} parts")
    # Laser-cut outline of the black acrylic cover (SendCutSend / Ponoko take DXF)
    outline = cq.Workplane("XY").rect(FACE_W - 2.6, FACE_H - 2.6).extrude(ACRYLIC_T).edges("|Z").fillet(0.8)
    cq.exporters.export(outline.faces("<Z").wires().toPending().extrude(0.01).section(),
                        str(OUT / "print" / "screen-acrylic.dxf"))
    (OUT / "parts.json").write_text(json.dumps(manifest, indent=2) + "\n")
    print(f"wrote {OUT}")


if __name__ == "__main__":
    main()
