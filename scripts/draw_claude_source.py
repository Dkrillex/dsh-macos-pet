#!/usr/bin/env /usr/bin/python3
"""Draw the Claude skin's eighteen source stills, without an image model.

`generate_frames.py` is the normal way art arrives here, and it needs an image
API. This draws the same eighteen stills — six states, three frames each, on the
same flat magenta plate — from geometry alone, so the skin can be built on a
machine with no credentials and rebuilt byte-identically later.

Two constraints from the gate shape everything below, and both are easy to
violate by accident:

* **The body's lowest pixel is the same in all eighteen frames.** `check_frames`
  measures the bottom of each frame's bounding box and fails a skin whose states
  sit more than 20px apart, because a pet that drops when it starts working
  reads as a glitch. So the crest fans upward and outward only, the arms stay
  above the belly line, and every prop is placed overhead. Nothing but the body
  is ever the lowest thing in frame, and the body never moves.
* **Nothing on the character may come near the plate colour.** An opaque pixel
  within 60 (sum-of-channels) of the plate is reported as background that got
  filled back in. Every colour in `PALETTE` is at least 278 away from magenta,
  which is why the palette is a closed set here rather than a suggestion.

Frames within one state are the same body an instant apart — the gate allows a
10% swing in body area across a loop — so a state's three frames differ only in
eyes, brow, crest phase and prop position.

    ./scripts/draw_claude_source.py            # write assets/source/claude/
    ./scripts/draw_claude_source.py --force    # overwrite existing stills

Then, as with any other skin:

    ./scripts/build_frames.py --skin claude
"""

from __future__ import annotations

import argparse
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dsh_macos_pet.imaging import _write_png_rgba  # noqa: E402  (needs the path above)

SOURCE_ROOT = ROOT / "assets" / "source" / "claude"

# Output size, matching the stills the image model produced for the other skins.
SIDE = 512
# Supersampling factor. The whole frame is drawn at SIDE*SS and box-averaged
# down, which is what puts a soft edge on the character — the same partially
# keyed edge a generated still has, and what `_despill_edges` expects to clean.
SS = 2

# Claude's warm terracotta and cream, plus an ink for the face.
#
# Distances to the magenta plate, sum-of-channels: orange 325, dark 355,
# light 308, cream 278, ink 456. The gate's opaque-plate bound is 60.
PLATE = (255, 0, 255)
ORANGE = (217, 119, 87)
ORANGE_DK = (184, 92, 63)
ORANGE_LT = (232, 155, 125)
CREAM = (240, 238, 230)
INK = (61, 43, 36)

# --- Geometry, in output pixels ------------------------------------------------
# BODY_BOTTOM is the number the gate actually watches. Every other measurement
# is written relative to the body so that changing the pose cannot move it.
BODY_CX, BODY_CY = 256.0, 296.0
BODY_RX, BODY_RY = 100.0, 94.0
BODY_BOTTOM = BODY_CY + BODY_RY  # 390

FACE_CX, FACE_CY = 256.0, 292.0
FACE_RX, FACE_RY = 64.0, 58.0

EYE_DX, EYE_Y, EYE_R = 24.0, 286.0, 10.0
BROW_Y = EYE_Y - 19.0
MOUTH_Y = 314.0

# The burst is centred on the body, not above it, so it reads as the Claude mark
# with a face in it rather than as hair. Its inner end starts inside the body so
# the rays look attached.
CREST_CX, CREST_CY = BODY_CX, BODY_CY - 6.0
CREST_INNER = 84.0
# No ray tip may come closer than this to the belly line. Downward rays are
# shortened to obey it, which is what keeps the body the lowest thing in frame
# in all eighteen frames.
CREST_FLOOR_MARGIN = 10.0

# Arms sit above the belly line by this much, so they can never become the
# lowest pixel no matter which pose moves them.
ARM_BOTTOM_MARGIN = 14.0


class Canvas:
    """An RGB frame with the handful of primitives this character needs.

    Every primitive is bounded by its own box before it loops, so cost tracks
    ink rather than canvas area — the difference between a second per frame and
    a minute.
    """

    def __init__(self, side: int) -> None:
        self.side = side
        self.buf = bytearray(PLATE * (side * side))

    def _blit(self, x0: int, y0: int, x1: int, y1: int, inside, color) -> None:
        side = self.side
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(side - 1, x1), min(side - 1, y1)
        r, g, b = color
        buf = self.buf
        for y in range(y0, y1 + 1):
            row = y * side
            for x in range(x0, x1 + 1):
                if inside(x + 0.5, y + 0.5):
                    i = (row + x) * 3
                    buf[i] = r
                    buf[i + 1] = g
                    buf[i + 2] = b

    def ellipse(self, cx: float, cy: float, rx: float, ry: float, color) -> None:
        rx = max(rx, 0.5)
        ry = max(ry, 0.5)

        def inside(x: float, y: float) -> bool:
            dx = (x - cx) / rx
            dy = (y - cy) / ry
            return dx * dx + dy * dy <= 1.0

        self._blit(int(cx - rx) - 1, int(cy - ry) - 1, int(cx + rx) + 1, int(cy + ry) + 1,
                   inside, color)

    def cone(self, x0: float, y0: float, x1: float, y1: float,
             r0: float, r1: float, color) -> None:
        """A capsule whose radius eases from r0 to r1 along the segment.

        One primitive covers the whole character: a spoke is a cone, a limb is a
        cone with equal ends, a stroke of the mouth is a short one.
        """

        dx, dy = x1 - x0, y1 - y0
        span = dx * dx + dy * dy

        def inside(x: float, y: float) -> bool:
            px, py = x - x0, y - y0
            t = 0.0 if span == 0 else max(0.0, min(1.0, (px * dx + py * dy) / span))
            ox, oy = px - t * dx, py - t * dy
            radius = r0 + t * (r1 - r0)
            return ox * ox + oy * oy <= radius * radius

        pad = max(r0, r1) + 1
        self._blit(int(min(x0, x1) - pad), int(min(y0, y1) - pad),
                   int(max(x0, x1) + pad), int(max(y0, y1) + pad), inside, color)

    def curve(self, points, r: float, color) -> None:
        """A polyline of cones — how every eyelid, brow and mouth is drawn."""

        for (ax, ay), (bx, by) in zip(points, points[1:]):
            self.cone(ax, ay, bx, by, r, r, color)

    def rect(self, x0: float, y0: float, x1: float, y1: float, color) -> None:
        def inside(x: float, y: float) -> bool:
            return x0 <= x <= x1 and y0 <= y <= y1

        self._blit(int(x0), int(y0), int(x1) + 1, int(y1) + 1, inside, color)

    def arc(self, cx: float, cy: float, rx: float, ry: float, *,
            bow: float, r: float, color, steps: int = 10) -> None:
        """A bowed stroke: `bow` +1 curves away from the top, -1 toward it.

        Every mouth and eyelid in the face goes through here. Drawn as ten
        segments rather than two because two straight lines meeting at a point
        is a beak, not a smile — which is exactly how the first pass looked.
        """

        pts = []
        for i in range(steps + 1):
            a = math.radians(25.0 + 130.0 * i / steps)
            pts.append((cx - rx * math.cos(a), cy + bow * ry * math.sin(a)))
        self.curve(pts, r, color)

    def rgba(self) -> bytes:
        """Box-average down to SIDE and pad to RGBA.

        Alpha is opaque throughout: the plate is a colour here, exactly as it is
        in a generated still, and `build_frames.py` is what turns it into
        transparency.
        """

        out = bytearray()
        side, ss = SIDE, SS
        buf = self.buf
        big = self.side
        area = ss * ss
        for y in range(side):
            for x in range(side):
                r = g = b = 0
                for sy in range(ss):
                    row = (y * ss + sy) * big
                    for sx in range(ss):
                        i = (row + x * ss + sx) * 3
                        r += buf[i]
                        g += buf[i + 1]
                        b += buf[i + 2]
                out += bytes((r // area, g // area, b // area, 255))
        return bytes(out)


# --- The character ------------------------------------------------------------


def crest(c: Canvas, *, phase: float, reach: float, droop: float) -> None:
    """The starburst behind the head.

    `droop` pulls the fan toward horizontal and is what makes the error pose
    read as deflated; `reach` scales the rays; `phase` rotates the whole fan a
    few degrees, which is the only motion the working loop needs.

    The span stops short of horizontal on both sides so no ray can ever swing
    below the body — the one thing the baseline check will not forgive.
    """

    rays = 12
    floor = BODY_BOTTOM - CREST_FLOOR_MARGIN
    for i in range(rays):
        # `droop` squeezes the fan toward the horizontal rather than rotating it,
        # so a deflated burst still points outward on both sides.
        spread = 1.0 - droop / 90.0
        a = math.radians(90.0 + (360.0 * i / rays - 90.0) * spread + phase)
        dx, dy = math.cos(a), -math.sin(a)
        # Long and short rays alternate: even lengths read as a comb.
        length = reach * (1.0 if i % 2 == 0 else 0.78)
        if dy > 0.62:
            # Aimed almost straight down. Clamping these to the belly line left a
            # row of stubs under the body; the silhouette is round and unbroken
            # there, so omitting them costs nothing.
            continue
        iy = CREST_CY + CREST_INNER * dy
        oy = CREST_CY + length * dy
        if oy > floor:
            # Still shorten the low side rays rather than lose them, or the
            # burst goes bald where it meets the shoulders.
            length = max(CREST_INNER + 6.0, (floor - CREST_CY) / dy)
            oy = CREST_CY + length * dy
        c.cone(CREST_CX + CREST_INNER * dx, iy,
               CREST_CX + length * dx, oy,
               24.0, 5.0, ORANGE if i % 2 == 0 else ORANGE_LT)


# Rim drawn inward, never outward: the outer edge of the body is the baseline
# every frame is measured against, and thickening it here would move it.
BODY_RIM = 3.0


def body(c: Canvas) -> None:
    c.ellipse(BODY_CX, BODY_CY, BODY_RX, BODY_RY, ORANGE_DK)
    c.ellipse(BODY_CX, BODY_CY, BODY_RX - BODY_RIM, BODY_RY - BODY_RIM, ORANGE)
    c.ellipse(FACE_CX, FACE_CY, FACE_RX, FACE_RY, ORANGE_DK)
    c.ellipse(FACE_CX, FACE_CY, FACE_RX - BODY_RIM + 1.0, FACE_RY - BODY_RIM + 1.0, CREAM)


def arms(c: Canvas, *, left: tuple[float, float], right: tuple[float, float]) -> None:
    """Two stubby arms, clamped so neither can reach below the belly.

    The clamp is not decoration: an arm hanging one pixel lower than the body
    becomes the frame's lowest point, and the whole state then sits lower than
    its neighbours.
    """

    limit = BODY_BOTTOM - ARM_BOTTOM_MARGIN
    for (hx, hy), sx in ((left, -1), (right, 1)):
        shoulder_x = BODY_CX + sx * (BODY_RX - 26.0)
        # Low on the body, not level with the face: at eye height these read as
        # ears, which is what the first pass drew.
        hand_y = min(hy, limit)
        c.cone(shoulder_x, BODY_CY + 44.0, hx, hand_y, 17.0, 13.0, ORANGE_DK)
        c.ellipse(hx, hand_y, 16.0, 16.0, ORANGE_DK)


def eyes(c: Canvas, kind: str, *, look: float = 0.0) -> None:
    """One of six eye shapes. `look` shifts the pupils for the waiting pose."""

    for sx in (-1, 1):
        cx = FACE_CX + sx * EYE_DX
        if kind == "open":
            c.ellipse(cx, EYE_Y + look, EYE_R, EYE_R, INK)
            c.ellipse(cx + 3.4, EYE_Y - 3.4 + look, 3.2, 3.2, CREAM)
        elif kind == "narrow":
            c.ellipse(cx, EYE_Y, EYE_R, 5.6, INK)
        elif kind == "half":
            c.ellipse(cx, EYE_Y, EYE_R, EYE_R, INK)
            # The lid is cream painted over the top of the eye rather than a
            # smaller eye: a shrunken pupil reads as a different expression,
            # while a covered one reads as mid-blink.
            c.rect(cx - EYE_R - 1, EYE_Y - EYE_R - 1, cx + EYE_R + 1, EYE_Y - 1, CREAM)
            c.arc(cx, EYE_Y - 2.0, EYE_R, 3.0, bow=1.0, r=2.8, color=INK)
        elif kind == "closed":
            c.arc(cx, EYE_Y - 2.0, EYE_R + 1.0, 5.0, bow=1.0, r=3.2, color=INK)
        elif kind == "happy":
            c.arc(cx, EYE_Y + 4.0, EYE_R + 1.0, 7.0, bow=-1.0, r=3.4, color=INK)
        elif kind == "cross":
            r = EYE_R - 1.0
            c.cone(cx - r, EYE_Y - r, cx + r, EYE_Y + r, 3.0, 3.0, INK)
            c.cone(cx - r, EYE_Y + r, cx + r, EYE_Y - r, 3.0, 3.0, INK)


def brows(c: Canvas, tilt: float, *, lift: float = 0.0, asym: float = 0.0) -> None:
    """`tilt` drops the inner end of each brow (a furrow); `asym` raises the right.

    "Inner" is the end nearer the middle of the face, which is the one that has
    to come down — dropping the outer ends instead reads as surprise.
    """

    for sx in (-1, 1):
        cx = FACE_CX + sx * EYE_DX
        y = BROW_Y - lift - (asym if sx > 0 else 0.0)
        inner_x = cx - sx * 10.0
        outer_x = cx + sx * 10.0
        c.cone(inner_x, y + tilt, outer_x, y - tilt * 0.35, 3.2, 3.2, ORANGE_DK)


def mouth(c: Canvas, kind: str) -> None:
    if kind == "smile":
        c.arc(FACE_CX, MOUTH_Y - 2.0, 15.0, 7.0, bow=1.0, r=3.2, color=INK)
    elif kind == "flat":
        c.cone(FACE_CX - 12.0, MOUTH_Y, FACE_CX + 12.0, MOUTH_Y, 3.2, 3.2, INK)
    elif kind == "frown":
        c.arc(FACE_CX, MOUTH_Y + 4.0, 15.0, 7.0, bow=-1.0, r=3.2, color=INK)
    elif kind == "grin":
        # A filled half-disc: drawn whole, then the top half painted back to
        # cream, which is cheaper than clipping and reads as an open mouth
        # instead of a dark blob.
        c.ellipse(FACE_CX, MOUTH_Y - 1.0, 17.0, 13.0, INK)
        c.rect(FACE_CX - 19.0, MOUTH_Y - 15.0, FACE_CX + 19.0, MOUTH_Y - 2.0, CREAM)
        c.cone(FACE_CX - 17.0, MOUTH_Y - 1.0, FACE_CX + 17.0, MOUTH_Y - 1.0, 2.4, 2.4, INK)
    elif kind == "small":
        c.cone(FACE_CX - 6.0, MOUTH_Y, FACE_CX + 6.0, MOUTH_Y, 2.8, 2.8, INK)


# --- Props --------------------------------------------------------------------
# Every prop lives overhead and in the character's own palette. Both rules come
# from the gate: a prop below the belly moves the baseline, and a prop in a
# background-adjacent colour is keyed away with the plate.


def pencil(c: Canvas, hx: float, hy: float, angle: float) -> None:
    a = math.radians(angle)
    tip_x, tip_y = hx + 52.0 * math.cos(a), hy - 52.0 * math.sin(a)
    c.cone(hx - 14.0 * math.cos(a), hy + 14.0 * math.sin(a), tip_x, tip_y, 8.0, 6.0, CREAM)
    c.cone(tip_x, tip_y, tip_x + 11.0 * math.cos(a), tip_y - 11.0 * math.sin(a), 6.0, 1.5, INK)


def question(c: Canvas, cx: float, cy: float, lean: float, scale: float) -> None:
    s = scale
    a = math.radians(lean)
    ca, sa = math.cos(a), math.sin(a)

    def at(dx: float, dy: float) -> tuple[float, float]:
        return cx + (dx * ca - dy * sa) * s, cy + (dx * sa + dy * ca) * s

    c.curve([at(-13, -12), at(0, -20), at(13, -10), at(2, 3), at(0, 12)], 5.0 * s, INK)
    c.ellipse(*at(0, 26), 5.4 * s, 5.4 * s, INK)


def bang(c: Canvas, cx: float, cy: float, scale: float) -> None:
    s = scale
    c.cone(cx, cy - 22.0 * s, cx, cy + 9.0 * s, 6.6 * s, 4.4 * s, INK)
    c.ellipse(cx, cy + 22.0 * s, 5.6 * s, 5.6 * s, INK)


def zed(c: Canvas, cx: float, cy: float, scale: float) -> None:
    s = 13.0 * scale
    c.curve([(cx - s, cy - s), (cx + s, cy - s), (cx - s, cy + s), (cx + s, cy + s)],
            4.2 * scale, CREAM)


def sparkle(c: Canvas, cx: float, cy: float, scale: float) -> None:
    r = 15.0 * scale
    c.cone(cx, cy - r, cx, cy + r, 4.2 * scale, 4.2 * scale, CREAM)
    c.cone(cx - r, cy, cx + r, cy, 4.2 * scale, 4.2 * scale, CREAM)


# --- The eighteen frames ------------------------------------------------------
# Read as a table on purpose: what differs between the frames of one state is
# exactly what a reader needs to see, and it is all here.

REST_ARMS = ((168.0, 344.0), (344.0, 344.0))


def draw(state: str, index: str) -> Canvas:
    # Everything below is specified in output pixels; drawing happens at
    # SIDE*SS, and the canvas scales for us.
    c = _ScaledCanvas(SIDE * SS, SS)

    if state == "idle":
        crest(c, phase=0.0, reach=152.0, droop=0.0)
        body(c)
        arms(c, left=REST_ARMS[0], right=REST_ARMS[1])
        brows(c, 0.0)
        eyes(c, {"00": "open", "01": "closed", "02": "half"}[index])
        mouth(c, "smile")

    elif state == "working":
        crest(c, phase={"00": 0.0, "01": 7.0, "02": 14.0}[index], reach=152.0, droop=0.0)
        body(c)
        hand = {"00": (352.0, 330.0), "01": (366.0, 350.0), "02": (352.0, 330.0)}[index]
        arms(c, left=(176.0, 350.0), right=hand)
        pencil(c, hand[0] + 8.0, hand[1] - 6.0, {"00": 62.0, "01": 38.0, "02": 62.0}[index])
        brows(c, 5.0)
        eyes(c, "closed" if index == "02" else "narrow")
        mouth(c, "flat")

    elif state == "waiting":
        crest(c, phase={"00": 0.0, "01": -5.0, "02": 4.0}[index], reach=150.0, droop=0.0)
        body(c)
        arms(c, left=REST_ARMS[0], right=(356.0, 300.0))
        brows(c, 0.0, lift=4.0, asym=7.0)
        eyes(c, "narrow" if index == "01" else "open", look=-3.0)
        mouth(c, "flat")
        question(c, 404.0, 214.0,
                 {"00": 0.0, "01": 14.0, "02": -10.0}[index],
                 {"00": 1.0, "01": 0.92, "02": 1.06}[index])

    elif state == "error":
        crest(c, phase=0.0, reach={"00": 116.0, "01": 112.0, "02": 120.0}[index], droop=26.0)
        body(c)
        arms(c, left=(160.0, 352.0), right=(352.0, 352.0))
        brows(c, 8.0)
        eyes(c, "closed" if index == "02" else "cross")
        mouth(c, "frown")
        bang(c, 404.0, 208.0, {"00": 1.0, "01": 0.9, "02": 1.05}[index])

    elif state == "happy":
        crest(c, phase={"00": 0.0, "01": 6.0, "02": -6.0}[index], reach=166.0, droop=0.0)
        body(c)
        arms(c, left=(150.0, 300.0), right=(362.0, 300.0))
        brows(c, 0.0, lift=6.0)
        eyes(c, "happy")
        mouth(c, "grin")
        for i, (px, py) in enumerate(((404.0, 224.0), (108.0, 236.0), (392.0, 320.0))):
            wobble = {"00": 1.0, "01": 0.82, "02": 1.14}[index]
            sparkle(c, px, py, wobble if i != 1 else wobble * 0.8)

    elif state == "sleeping":
        crest(c, phase=0.0, reach={"00": 124.0, "01": 120.0, "02": 128.0}[index], droop=14.0)
        body(c)
        arms(c, left=(170.0, 352.0), right=(342.0, 352.0))
        brows(c, 0.0, lift=-3.0)
        eyes(c, "closed")
        mouth(c, "small")
        # Two z's in every frame, drifting: a prop that vanishes for one frame
        # of a loop strobes, and the gate warns about exactly that.
        drift = {"00": 0.0, "01": -7.0, "02": -14.0}[index]
        zed(c, 392.0, 236.0 + drift, {"00": 1.0, "01": 1.08, "02": 0.92}[index])
        zed(c, 434.0, 190.0 + drift, {"00": 0.72, "01": 0.64, "02": 0.8}[index])

    else:
        raise SystemExit(f"unknown state {state}")

    return c


class _ScaledCanvas(Canvas):
    """A canvas that takes coordinates in output pixels and draws supersampled.

    Keeps every measurement in this file in one unit. Without it each of the
    thirty-odd call sites above would have to remember to multiply, and the one
    that forgot would draw a body part at half scale.
    """

    def __init__(self, side: int, scale: int) -> None:
        super().__init__(side)
        self.scale = scale

    def ellipse(self, cx, cy, rx, ry, color) -> None:
        s = self.scale
        super().ellipse(cx * s, cy * s, rx * s, ry * s, color)

    def cone(self, x0, y0, x1, y1, r0, r1, color) -> None:
        s = self.scale
        super().cone(x0 * s, y0 * s, x1 * s, y1 * s, r0 * s, r1 * s, color)

    def rect(self, x0, y0, x1, y1, color) -> None:
        s = self.scale
        super().rect(x0 * s, y0 * s, x1 * s, y1 * s, color)

    def curve(self, points, r, color) -> None:
        for (ax, ay), (bx, by) in zip(points, points[1:]):
            self.cone(ax, ay, bx, by, r, r, color)


STATES = {
    "idle": ("00", "01", "02"),
    "working": ("00", "01", "02"),
    "waiting": ("00", "01", "02"),
    "error": ("00", "01", "02"),
    "happy": ("00", "01", "02"),
    "sleeping": ("00", "01", "02"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--force", action="store_true", help="overwrite existing stills")
    parser.add_argument("--state", action="append", help="limit to these states")
    args = parser.parse_args()

    wanted = args.state or list(STATES)
    written = skipped = 0
    for state in wanted:
        for index in STATES[state]:
            dest = SOURCE_ROOT / state / f"{index}.png"
            if dest.is_file() and not args.force:
                print(f"  claude/{state}/{index}  skip (exists)")
                skipped += 1
                continue
            canvas = draw(state, index)
            dest.parent.mkdir(parents=True, exist_ok=True)
            _write_png_rgba(dest, SIDE, SIDE, canvas.rgba())
            print(f"  claude/{state}/{index}  {dest.stat().st_size // 1024} KB")
            written += 1

    print(f"\n{written} written, {skipped} skipped")
    if written:
        print("next: ./scripts/build_frames.py --skin claude")
    return 0


if __name__ == "__main__":
    sys.exit(main())
