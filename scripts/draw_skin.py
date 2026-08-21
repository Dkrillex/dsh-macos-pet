#!/usr/bin/env /usr/bin/python3
"""Draw a skin's eighteen source stills from geometry, with no image model.

`generate_frames.py` is the other way art arrives here, and it needs an image
API and credits. This needs neither: a skin is a `Spec` — a palette and a
handful of proportions — and the eighteen stills come out of it deterministically,
on the same flat magenta plate `build_frames.py` expects. Same spec in, same
bytes out, on any machine.

The choreography is shared. Every skin gets the same eighteen poses, because
what a state has to communicate does not depend on what the character looks
like: idle blinks, working holds a pencil and furrows its brow, waiting raises a
question mark, error crosses its eyes, happy grins with sparkles, sleeping
breathes out z's. A `Spec` changes who is doing it, not what is done.

Two constraints from `check_frames.py` shape all of it, and both are easy to
violate by accident:

* **The body's lowest pixel is identical in all eighteen frames.** The gate
  fails a skin whose states sit more than 20px apart, because a pet that drops
  when it starts working reads as a glitch. So the crest fans upward and
  outward with its downward rays dropped, the arms are clamped above the belly
  line, and every prop is placed overhead. Nothing but the body is ever the
  lowest thing in frame, and the body never moves.
* **No colour on the character may come near the plate.** An opaque pixel
  within 60 (sum-of-channels) of the plate colour is reported as background
  filled back in. `Palette.check()` enforces this at startup rather than
  leaving it to be discovered by a failing gate three commands later.

    ./scripts/draw_skin.py --list                # what specs exist
    ./scripts/draw_skin.py --skin claude         # write assets/source/claude/
    ./scripts/draw_skin.py --skin claude --force # overwrite existing stills

Then, as with any other skin:

    ./scripts/build_frames.py --skin claude

To add your own: copy a `Spec` in `SPECS`, change the palette and the
proportions, run it, and look at the contact sheet. Nothing else here needs
touching.
"""

from __future__ import annotations

import argparse
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from dsh_macos_pet.imaging import _write_png_rgba  # noqa: E402  (needs the path above)

SOURCE_ROOT = ROOT / "assets" / "source"

# Output size, matching the stills the image model produced for the other skins.
SIDE = 512
# Supersampling factor. The frame is drawn at SIDE*SS and box-averaged down,
# which is what puts a soft edge on the character — the same partially keyed
# edge a generated still has, and what `_despill_edges` expects to clean.
SS = 2

# The plate every skin is drawn on. Shared, because `build_frames.py` samples it
# from the still and keys against it; a per-skin plate would only widen the
# distance the key has to tolerate.
PLATE = (255, 0, 255)

# How close an opaque colour may come to the plate, summed over channels, before
# the gate calls it leftover background. Mirrors PLATE_DISTANCE_OPAQUE there.
MIN_PLATE_DISTANCE = 60

STATES = ("idle", "working", "waiting", "error", "happy", "sleeping")
FRAMES = ("00", "01", "02")


@dataclass(frozen=True)
class Palette:
    """Five colours. Everything the character is made of comes from here."""

    body: tuple[int, int, int]
    body_dark: tuple[int, int, int]
    body_light: tuple[int, int, int]
    face: tuple[int, int, int]
    ink: tuple[int, int, int]

    def check(self, name: str) -> None:
        """Refuse a palette the art gate would reject, before drawing anything.

        Cheap to check here and expensive to discover later: a colour too near
        the plate survives drawing, survives keying, and only shows up as
        "background filled back in" once the gate decodes the built frames.
        """

        for label, rgb in (("body", self.body), ("body_dark", self.body_dark),
                           ("body_light", self.body_light), ("face", self.face),
                           ("ink", self.ink)):
            distance = sum(abs(rgb[i] - PLATE[i]) for i in range(3))
            if distance < MIN_PLATE_DISTANCE:
                raise SystemExit(
                    f"{name}: {label} {rgb} is {distance} from the plate; the art gate "
                    f"rejects anything under {MIN_PLATE_DISTANCE} as un-keyed background")


@dataclass(frozen=True)
class Shape:
    """Proportions, in output pixels.

    `body_cy + body_ry` is the baseline the gate measures, so every other
    measurement is written relative to the body and nothing below it is drawn.
    """

    body_cy: float = 296.0
    body_rx: float = 100.0
    body_ry: float = 94.0
    rim: float = 3.0

    face_dy: float = -4.0
    face_rx: float = 64.0
    face_ry: float = 58.0

    eye_dx: float = 24.0
    eye_dy: float = -6.0
    eye_r: float = 10.0
    brow_dy: float = -25.0
    mouth_dy: float = 22.0

    crest_rays: int = 12
    crest_dy: float = -6.0
    crest_inner: float = 84.0
    crest_reach: float = 152.0
    crest_w0: float = 24.0
    crest_w1: float = 5.0
    # How long the odd rays are relative to the even ones. Alternating lengths
    # read as a mane; 1.0 makes every ray equal, which is what reads as a star.
    crest_alt: float = 0.78
    # No ray tip may come closer than this to the belly line.
    crest_floor_margin: float = 10.0
    # Rays aimed more steeply downward than this are dropped rather than
    # shortened: clamping them left a row of stubs under the body.
    crest_down_limit: float = 0.62

    # How far out the overhead glyphs sit, relative to the reference body. A
    # longer crest needs a bigger number or the glyph lands on a ray: it stays
    # legible, but it fuses with the body and the gate can no longer tell a
    # merged prop from a vanished one.
    prop_scale: float = 1.0

    arm_w0: float = 17.0
    arm_w1: float = 13.0
    hand_r: float = 16.0
    arm_shoulder_inset: float = 26.0
    arm_shoulder_dy: float = 44.0
    arm_bottom_margin: float = 14.0

    @property
    def cx(self) -> float:
        return SIDE / 2.0

    @property
    def bottom(self) -> float:
        return self.body_cy + self.body_ry


@dataclass(frozen=True)
class Spec:
    palette: Palette
    shape: Shape = field(default_factory=Shape)


SPECS: dict[str, Spec] = {
    # Claude's warm terracotta and cream. Distances to the plate, summed over
    # channels: body 325, dark 355, light 308, face 278, ink 456.
    "claude": Spec(
        palette=Palette(
            body=(217, 119, 87),
            body_dark=(184, 92, 63),
            body_light=(232, 155, 125),
            face=(240, 238, 230),
            ink=(61, 43, 36),
        ),
    ),
    # Distances to the plate, summed over channels: body 396, dark 412,
    # light 360, face 273, ink 466.
    "star": Spec(
        palette=Palette(
            body=(230, 176, 60),
            body_dark=(196, 138, 38),
            body_light=(246, 208, 112),
            face=(250, 245, 232),
            ink=(58, 44, 30),
        ),
        shape=Shape(
            body_rx=86.0,
            body_ry=82.0,
            face_rx=58.0,
            face_ry=53.0,
            eye_dx=21.0,
            mouth_dy=20.0,
            crest_rays=10,
            crest_alt=1.0,
            crest_inner=68.0,
            crest_reach=170.0,
            crest_w0=30.0,
            crest_w1=3.0,
            arm_shoulder_inset=22.0,
            prop_scale=1.14,
        ),
    ),
}


class Canvas:
    """An RGB frame with the handful of primitives this character needs.

    Coordinates arrive in output pixels and are scaled to the supersampled
    buffer here, so every measurement in this file stays in one unit. Every
    primitive is bounded by its own box before it loops, so cost tracks ink
    rather than canvas area — the difference between a second per frame and a
    minute.
    """

    def __init__(self, scale: int) -> None:
        self.scale = scale
        self.side = SIDE * scale
        self.buf = bytearray(PLATE * (self.side * self.side))

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
        s = self.scale
        cx, cy, rx, ry = cx * s, cy * s, max(rx * s, 0.5), max(ry * s, 0.5)

        def inside(x: float, y: float) -> bool:
            dx = (x - cx) / rx
            dy = (y - cy) / ry
            return dx * dx + dy * dy <= 1.0

        self._blit(int(cx - rx) - 1, int(cy - ry) - 1, int(cx + rx) + 1, int(cy + ry) + 1,
                   inside, color)

    def cone(self, x0: float, y0: float, x1: float, y1: float,
             r0: float, r1: float, color) -> None:
        """A capsule whose radius eases from r0 to r1 along the segment.

        One primitive covers most of the character: a ray is a cone, a limb is a
        cone with equal ends, a stroke of the mouth is a short one.
        """

        s = self.scale
        x0, y0, x1, y1, r0, r1 = x0 * s, y0 * s, x1 * s, y1 * s, r0 * s, r1 * s
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
        s = self.scale
        x0, y0, x1, y1 = x0 * s, y0 * s, x1 * s, y1 * s

        def inside(x: float, y: float) -> bool:
            return x0 <= x <= x1 and y0 <= y <= y1

        self._blit(int(x0), int(y0), int(x1) + 1, int(y1) + 1, inside, color)

    def arc(self, cx: float, cy: float, rx: float, ry: float, *,
            bow: float, r: float, color, steps: int = 10) -> None:
        """A bowed stroke: `bow` +1 curves away from the top, -1 toward it.

        Every mouth and eyelid goes through here. Drawn as ten segments rather
        than two because two straight lines meeting at a point is a beak, not a
        smile — which is exactly how the first pass looked.
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
        ss = self.scale
        buf = self.buf
        big = self.side
        area = ss * ss
        for y in range(SIDE):
            for x in range(SIDE):
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


class Pen:
    """A `Spec` bound to a `Canvas`.

    Holds the derived coordinates — where the eyes are, where the belly line is
    — so the pose code below reads as choreography rather than arithmetic, and
    so a new spec changes those numbers in one place.
    """

    def __init__(self, spec: Spec, canvas: Canvas) -> None:
        self.spec = spec
        self.c = canvas
        s, p = spec.shape, spec.palette
        self.s, self.p = s, p
        self.cx = s.cx
        self.body_cy = s.body_cy
        self.bottom = s.bottom
        self.face_cy = s.body_cy + s.face_dy
        self.eye_y = self.face_cy + s.eye_dy
        self.brow_y = self.face_cy + s.brow_dy
        self.mouth_y = self.face_cy + s.mouth_dy
        self.crest_cy = s.body_cy + s.crest_dy

    # --- anatomy -------------------------------------------------------------

    def crest(self, *, phase: float, reach: float, droop: float) -> None:
        """The starburst behind the head.

        `droop` squeezes the fan toward horizontal rather than rotating it, so a
        deflated burst still points outward on both sides; `reach` scales the
        rays; `phase` rotates the fan, which is the only motion the working loop
        needs.
        """

        s, p, c = self.s, self.p, self.c
        floor = self.bottom - s.crest_floor_margin
        for i in range(s.crest_rays):
            spread = 1.0 - droop / 90.0
            a = math.radians(90.0 + (360.0 * i / s.crest_rays - 90.0) * spread + phase)
            dx, dy = math.cos(a), -math.sin(a)
            length = reach * (1.0 if i % 2 == 0 else s.crest_alt)
            if dy > s.crest_down_limit:
                # Aimed almost straight down. Clamping these to the belly line
                # left a row of stubs under the body; the silhouette is round
                # and unbroken there, so omitting them costs nothing.
                continue
            iy = self.crest_cy + s.crest_inner * dy
            oy = self.crest_cy + length * dy
            if oy > floor:
                # Still shorten the low side rays rather than lose them, or the
                # burst goes bald where it meets the shoulders.
                length = max(s.crest_inner + 6.0, (floor - self.crest_cy) / dy)
                oy = self.crest_cy + length * dy
            c.cone(self.cx + s.crest_inner * dx, iy,
                   self.cx + length * dx, oy,
                   s.crest_w0, s.crest_w1, p.body if i % 2 == 0 else p.body_light)

    def body(self) -> None:
        """Body and face plate, each with an inward rim.

        Inward, never outward: the outer edge of the body is the baseline every
        frame is measured against, and thickening it here would move it.
        """

        s, p, c = self.s, self.p, self.c
        c.ellipse(self.cx, self.body_cy, s.body_rx, s.body_ry, p.body_dark)
        c.ellipse(self.cx, self.body_cy, s.body_rx - s.rim, s.body_ry - s.rim, p.body)
        c.ellipse(self.cx, self.face_cy, s.face_rx, s.face_ry, p.body_dark)
        c.ellipse(self.cx, self.face_cy, s.face_rx - s.rim + 1.0, s.face_ry - s.rim + 1.0,
                  p.face)

    def arms(self, left: tuple[float, float], right: tuple[float, float]) -> None:
        """Two stubby arms, clamped so neither can reach below the belly.

        The clamp is not decoration: an arm hanging one pixel lower than the
        body becomes the frame's lowest point, and the whole state then sits
        lower than its neighbours. Hands are drawn low on the body rather than
        level with the face, where they read as ears.
        """

        s, p, c = self.s, self.p, self.c
        limit = self.bottom - s.arm_bottom_margin
        for (hdx, hdy), sx in ((left, -1), (right, 1)):
            hx, hy = self.cx + hdx, self.body_cy + hdy
            shoulder_x = self.cx + sx * (s.body_rx - s.arm_shoulder_inset)
            hand_y = min(hy, limit)
            c.cone(shoulder_x, self.body_cy + s.arm_shoulder_dy, hx, hand_y,
                   s.arm_w0, s.arm_w1, p.body_dark)
            c.ellipse(hx, hand_y, s.hand_r, s.hand_r, p.body_dark)

    def eyes(self, kind: str, *, look: float = 0.0) -> None:
        """One of six eye shapes. `look` shifts the pupils for the waiting pose."""

        s, p, c = self.s, self.p, self.c
        r = s.eye_r
        for sx in (-1, 1):
            cx = self.cx + sx * s.eye_dx
            y = self.eye_y
            if kind == "open":
                c.ellipse(cx, y + look, r, r, p.ink)
                c.ellipse(cx + 3.4, y - 3.4 + look, 3.2, 3.2, p.face)
            elif kind == "narrow":
                c.ellipse(cx, y, r, 5.6, p.ink)
            elif kind == "half":
                c.ellipse(cx, y, r, r, p.ink)
                # The lid is the face colour painted over the top of the eye
                # rather than a smaller eye: a shrunken pupil reads as a
                # different expression, a covered one reads as mid-blink.
                c.rect(cx - r - 1, y - r - 1, cx + r + 1, y - 1, p.face)
                c.arc(cx, y - 2.0, r, 3.0, bow=1.0, r=2.8, color=p.ink)
            elif kind == "closed":
                c.arc(cx, y - 2.0, r + 1.0, 5.0, bow=1.0, r=3.2, color=p.ink)
            elif kind == "happy":
                c.arc(cx, y + 4.0, r + 1.0, 7.0, bow=-1.0, r=3.4, color=p.ink)
            elif kind == "cross":
                d = r - 1.0
                c.cone(cx - d, y - d, cx + d, y + d, 3.0, 3.0, p.ink)
                c.cone(cx - d, y + d, cx + d, y - d, 3.0, 3.0, p.ink)
            else:
                raise SystemExit(f"unknown eye kind {kind}")

    def brows(self, tilt: float, *, lift: float = 0.0, asym: float = 0.0) -> None:
        """`tilt` drops the inner end of each brow; `asym` raises the right one.

        "Inner" is the end nearer the middle of the face, which is the one that
        has to come down — dropping the outer ends reads as surprise.
        """

        s, p, c = self.s, self.p, self.c
        for sx in (-1, 1):
            cx = self.cx + sx * s.eye_dx
            y = self.brow_y - lift - (asym if sx > 0 else 0.0)
            c.cone(cx - sx * 10.0, y + tilt, cx + sx * 10.0, y - tilt * 0.35,
                   3.2, 3.2, p.body_dark)

    def mouth(self, kind: str) -> None:
        p, c = self.p, self.c
        y = self.mouth_y
        if kind == "smile":
            c.arc(self.cx, y - 2.0, 15.0, 7.0, bow=1.0, r=3.2, color=p.ink)
        elif kind == "flat":
            c.cone(self.cx - 12.0, y, self.cx + 12.0, y, 3.2, 3.2, p.ink)
        elif kind == "frown":
            c.arc(self.cx, y + 4.0, 15.0, 7.0, bow=-1.0, r=3.2, color=p.ink)
        elif kind == "grin":
            # A filled half-disc: drawn whole, then the top painted back to the
            # face colour, which is cheaper than clipping and reads as an open
            # mouth instead of a dark blob.
            c.ellipse(self.cx, y - 1.0, 17.0, 13.0, p.ink)
            c.rect(self.cx - 19.0, y - 15.0, self.cx + 19.0, y - 2.0, p.face)
            c.cone(self.cx - 17.0, y - 1.0, self.cx + 17.0, y - 1.0, 2.4, 2.4, p.ink)
        elif kind == "small":
            c.cone(self.cx - 6.0, y, self.cx + 6.0, y, 2.8, 2.8, p.ink)
        else:
            raise SystemExit(f"unknown mouth kind {kind}")

    # --- props ---------------------------------------------------------------
    # Every prop is placed overhead and drawn in the character's own palette.
    # Both rules come from the gate: a prop below the belly moves the baseline,
    # and a prop in a plate-adjacent colour is keyed away with the background.

    def _at(self, dx: float, dy: float) -> tuple[float, float]:
        """Body-relative. For anything held, which must track the hand."""

        return self.cx + dx, self.body_cy + dy

    def _overhead(self, dx: float, dy: float) -> tuple[float, float]:
        """Body-relative and pushed out past the crest. For the free glyphs."""

        k = self.s.prop_scale
        return self.cx + dx * k, self.body_cy + dy * k

    def pencil(self, dx: float, dy: float, angle: float) -> None:
        p, c = self.p, self.c
        hx, hy = self._at(dx, dy)
        a = math.radians(angle)
        tip_x, tip_y = hx + 52.0 * math.cos(a), hy - 52.0 * math.sin(a)
        c.cone(hx - 14.0 * math.cos(a), hy + 14.0 * math.sin(a), tip_x, tip_y,
               8.0, 6.0, p.face)
        c.cone(tip_x, tip_y, tip_x + 11.0 * math.cos(a), tip_y - 11.0 * math.sin(a),
               6.0, 1.5, p.ink)

    def question(self, dx: float, dy: float, lean: float, scale: float) -> None:
        p, c = self.p, self.c
        cx, cy = self._overhead(dx, dy)
        a = math.radians(lean)
        ca, sa = math.cos(a), math.sin(a)

        def at(ox: float, oy: float) -> tuple[float, float]:
            return cx + (ox * ca - oy * sa) * scale, cy + (ox * sa + oy * ca) * scale

        c.curve([at(-13, -12), at(0, -20), at(13, -10), at(2, 3), at(0, 12)],
                5.0 * scale, p.ink)
        c.ellipse(*at(0, 26), 5.4 * scale, 5.4 * scale, p.ink)

    def bang(self, dx: float, dy: float, scale: float) -> None:
        p, c = self.p, self.c
        cx, cy = self._overhead(dx, dy)
        c.cone(cx, cy - 22.0 * scale, cx, cy + 9.0 * scale,
               6.6 * scale, 4.4 * scale, p.ink)
        c.ellipse(cx, cy + 22.0 * scale, 5.6 * scale, 5.6 * scale, p.ink)

    def zed(self, dx: float, dy: float, scale: float) -> None:
        p, c = self.p, self.c
        cx, cy = self._overhead(dx, dy)
        d = 13.0 * scale
        c.curve([(cx - d, cy - d), (cx + d, cy - d), (cx - d, cy + d), (cx + d, cy + d)],
                4.2 * scale, p.face)

    def sparkle(self, dx: float, dy: float, scale: float) -> None:
        p, c = self.p, self.c
        cx, cy = self._overhead(dx, dy)
        d = 15.0 * scale
        c.cone(cx, cy - d, cx, cy + d, 4.2 * scale, 4.2 * scale, p.face)
        c.cone(cx - d, cy, cx + d, cy, 4.2 * scale, 4.2 * scale, p.face)


# --- The eighteen poses -------------------------------------------------------
# Shared by every skin: what a state has to communicate does not depend on what
# the character looks like. Offsets are relative to the body centre so a spec
# with different proportions still puts its hands and props in the right place.
#
# Read as a table on purpose. What differs between the three frames of one state
# is exactly what a reader needs to see, and it is all here.

REST_ARMS = ((-88.0, 48.0), (88.0, 48.0))


def pose(pen: Pen, state: str, index: str) -> None:
    if state == "idle":
        pen.crest(phase=0.0, reach=pen.s.crest_reach, droop=0.0)
        pen.body()
        pen.arms(*REST_ARMS)
        pen.brows(0.0)
        pen.eyes({"00": "open", "01": "closed", "02": "half"}[index])
        pen.mouth("smile")

    elif state == "working":
        pen.crest(phase={"00": 0.0, "01": 7.0, "02": 14.0}[index],
                  reach=pen.s.crest_reach, droop=0.0)
        pen.body()
        hand = {"00": (96.0, 34.0), "01": (110.0, 54.0), "02": (96.0, 34.0)}[index]
        pen.arms((-80.0, 54.0), hand)
        pen.pencil(hand[0] + 8.0, hand[1] - 6.0,
                   {"00": 62.0, "01": 38.0, "02": 62.0}[index])
        pen.brows(5.0)
        pen.eyes("closed" if index == "02" else "narrow")
        pen.mouth("flat")

    elif state == "waiting":
        pen.crest(phase={"00": 0.0, "01": -5.0, "02": 4.0}[index],
                  reach=pen.s.crest_reach - 2.0, droop=0.0)
        pen.body()
        pen.arms(REST_ARMS[0], (100.0, 4.0))
        pen.brows(0.0, lift=4.0, asym=7.0)
        pen.eyes("narrow" if index == "01" else "open", look=-3.0)
        pen.mouth("flat")
        pen.question(148.0, -82.0,
                     {"00": 0.0, "01": 14.0, "02": -10.0}[index],
                     {"00": 1.0, "01": 0.92, "02": 1.06}[index])

    elif state == "error":
        # A deflated burst, not a rotated one: the shape says "gave up".
        pen.crest(phase=0.0,
                  reach={"00": 116.0, "01": 112.0, "02": 120.0}[index], droop=26.0)
        pen.body()
        pen.arms((-96.0, 56.0), (96.0, 56.0))
        pen.brows(8.0)
        pen.eyes("closed" if index == "02" else "cross")
        pen.mouth("frown")
        pen.bang(148.0, -88.0, {"00": 1.0, "01": 0.9, "02": 1.05}[index])

    elif state == "happy":
        pen.crest(phase={"00": 0.0, "01": 6.0, "02": -6.0}[index],
                  reach=pen.s.crest_reach + 14.0, droop=0.0)
        pen.body()
        pen.arms((-106.0, 4.0), (106.0, 4.0))
        pen.brows(0.0, lift=6.0)
        pen.eyes("happy")
        pen.mouth("grin")
        wobble = {"00": 1.0, "01": 0.82, "02": 1.14}[index]
        for i, (dx, dy) in enumerate(((148.0, -72.0), (-148.0, -60.0), (136.0, 24.0))):
            pen.sparkle(dx, dy, wobble if i != 1 else wobble * 0.8)

    elif state == "sleeping":
        pen.crest(phase=0.0,
                  reach={"00": 124.0, "01": 120.0, "02": 128.0}[index], droop=14.0)
        pen.body()
        pen.arms((-86.0, 56.0), (86.0, 56.0))
        pen.brows(0.0, lift=-3.0)
        pen.eyes("closed")
        pen.mouth("small")
        # Two z's in every frame, drifting. A prop that vanishes for one frame of
        # a loop strobes, and the gate warns about exactly that.
        drift = {"00": 0.0, "01": -7.0, "02": -14.0}[index]
        pen.zed(136.0, -60.0 + drift, {"00": 1.0, "01": 1.08, "02": 0.92}[index])
        pen.zed(178.0, -106.0 + drift, {"00": 0.72, "01": 0.64, "02": 0.8}[index])

    else:
        raise SystemExit(f"unknown state {state}")


def draw(spec: Spec, state: str, index: str) -> Canvas:
    canvas = Canvas(SS)
    pose(Pen(spec, canvas), state, index)
    return canvas


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--skin", action="append", help="which spec to draw")
    parser.add_argument("--state", action="append", help="limit to these states")
    parser.add_argument("--force", action="store_true", help="overwrite existing stills")
    parser.add_argument("--list", action="store_true", help="list the known specs")
    args = parser.parse_args()

    if args.list:
        for name, spec in sorted(SPECS.items()):
            print(f"  {name:12s} body={spec.palette.body} face={spec.palette.face}")
        return 0

    skins = args.skin or sorted(SPECS)
    unknown = [s for s in skins if s not in SPECS]
    if unknown:
        parser.error(f"no spec for {', '.join(unknown)} (see --list)")

    wanted = args.state or list(STATES)
    written = skipped = 0
    for name in skins:
        spec = SPECS[name]
        spec.palette.check(name)
        for state in wanted:
            for index in FRAMES:
                dest = SOURCE_ROOT / name / state / f"{index}.png"
                if dest.is_file() and not args.force:
                    print(f"  {name}/{state}/{index}  skip (exists)")
                    skipped += 1
                    continue
                canvas = draw(spec, state, index)
                dest.parent.mkdir(parents=True, exist_ok=True)
                _write_png_rgba(dest, SIDE, SIDE, canvas.rgba())
                print(f"  {name}/{state}/{index}  {dest.stat().st_size // 1024} KB")
                written += 1

    print(f"\n{written} written, {skipped} skipped")
    if written:
        print(f"next: ./scripts/build_frames.py --skin {skins[0]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
