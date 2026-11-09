"""Build assets/hero.svg and assets/lines.svg.

All text is converted to outlines: GitHub serves README images under a strict CSP,
so embedded or remote fonts are not guaranteed to load. Outlines always render.

Fonts (SIL OFL) live in scripts/fonts/ (gitignored):
  Archivo.ttf         https://github.com/google/fonts/raw/main/ofl/archivo/Archivo%5Bwdth,wght%5D.ttf
  InstrumentSans.ttf  https://github.com/google/fonts/raw/main/ofl/instrumentsans/InstrumentSans%5Bwdth,wght%5D.ttf
  JetBrainsMono.ttf   https://github.com/google/fonts/raw/main/ofl/jetbrainsmono/JetBrainsMono%5Bwght%5D.ttf

Run: python3 scripts/build.py   (needs fonttools)
"""
import math
import re
from pathlib import Path

from fontTools.pens.boundsPen import BoundsPen
from fontTools.pens.svgPathPen import SVGPathPen
from fontTools.pens.transformPen import TransformPen
from fontTools.svgLib.path import parse_path
from fontTools.ttLib import TTFont
from fontTools.varLib.instancer import instantiateVariableFont

HERE = Path(__file__).resolve().parent
OUT = HERE.parent / "assets"


def num(v):
    s = f"{v:.1f}".rstrip("0").rstrip(".")
    return "0" if s in ("-0", "") else s


def kerning(font):
    """Pair kerning from GPOS 'kern' lookups (PairPos formats 1 and 2)."""
    if "GPOS" not in font:
        return lambda a, b: 0
    g = font["GPOS"].table
    ids = sorted({i for fr in g.FeatureList.FeatureRecord if fr.FeatureTag == "kern" for i in fr.Feature.LookupListIndex})
    lookups = []
    for i in ids:
        lk, subs = g.LookupList.Lookup[i], []
        for st in lk.SubTable:
            if lk.LookupType == 9:
                if st.ExtensionLookupType != 2:
                    continue
                st = st.ExtSubTable
            elif lk.LookupType != 2:
                continue
            cov = {n: k for k, n in enumerate(st.Coverage.glyphs)}
            if st.Format == 1:
                pairs = {}
                for first, k in cov.items():
                    for r in st.PairSet[k].PairValueRecord:
                        pairs[(first, r.SecondGlyph)] = getattr(r.Value1, "XAdvance", 0) or 0
                subs.append(("pairs", cov, pairs))
            else:
                subs.append(("class", cov, st))
        lookups.append(subs)

    def kern(a, b):
        total = 0
        for subs in lookups:
            for kind, cov, data in subs:
                if a not in cov:
                    continue
                if kind == "pairs":
                    if (a, b) in data:
                        total += data[(a, b)]
                        break
                else:
                    c1 = data.ClassDef1.classDefs.get(a, 0)
                    c2 = data.ClassDef2.classDefs.get(b, 0)
                    total += getattr(data.Class1Record[c1].Class2Record[c2].Value1, "XAdvance", 0) or 0
                    break
        return total

    return kern


class Face:
    def __init__(self, file, **axes):
        f = TTFont(HERE / "fonts" / file)
        if "fvar" in f:
            f = instantiateVariableFont(f, {a.axisTag: axes.get(a.axisTag, a.defaultValue) for a in f["fvar"].axes})
        self.glyphs, self.cmap = f.getGlyphSet(), f.getBestCmap()
        self.upm = f["head"].unitsPerEm
        self.cap = f["OS/2"].sCapHeight / self.upm
        self.kern = kerning(f)

    def _advances(self, text, track):
        names = [self.cmap[ord(c)] for c in text]
        adv = [self.glyphs[n].width + (self.kern(n, names[i + 1]) + track * self.upm if i + 1 < len(names) else 0)
               for i, n in enumerate(names)]
        return names, adv

    def width(self, text, size, track=0):
        return sum(self._advances(text, track)[1]) * size / self.upm

    def path(self, text, x, y, size, fill, track=0, anchor="start", attrs=""):
        if anchor != "start":
            x -= self.width(text, size, track) * (0.5 if anchor == "middle" else 1)
        s, cx = size / self.upm, 0
        pen = SVGPathPen(self.glyphs, ntos=num)
        for n, a in zip(*self._advances(text, track)):
            self.glyphs[n].draw(TransformPen(pen, (s, 0, 0, -s, x + cx * s, y)))
            cx += a
        return f'<path d="{pen.getCommands()}" fill="{fill}"{attrs}/>'


ARCH = Face("Archivo.ttf", wght=600, wdth=92)
ARCH7 = Face("Archivo.ttf", wght=700, wdth=92)
INS7 = Face("InstrumentSans.ttf", wght=700)
INS4 = Face("InstrumentSans.ttf", wght=400)
MONO = Face("JetBrainsMono.ttf", wght=500)

# Station world (personal): Milan-metro enamel signage.
RED, GREEN, WALL, WHITE = "#e1251b", "#21955a", "#232628", "#ffffff"
# Patter world (the poster): tokens from the Patter design system.
INK, TERRA, CREAM, DOT, PEACH, PEACH_L, SIDE, MUTED = "#000", "#c97a4c", "#f6f6f4", "#dad8de", "#df9367", "#efc5ac", "#eeeeee", "#4a4a4a"

# Lucide "phone" icon (ISC licence), 24x24 box.
PHONE = ("M22 16.92v3a2 2 0 0 1-2.18 2 19.79 19.79 0 0 1-8.63-3.07 19.5 19.5 0 0 1-6-6 19.79 19.79 0 0 1-3.07-8.67"
         "A2 2 0 0 1 4.11 2h3a2 2 0 0 1 2 1.72 12.84 12.84 0 0 0 .7 2.81 2 2 0 0 1-.45 2.11L8.09 9.91a16 16 0 0 0 6 6"
         "l1.27-1.27a2 2 0 0 1 2.11-.45 12.84 12.84 0 0 0 2.81.7A2 2 0 0 1 22 16.92z")


def svg(w, h, title, defs, body, style):
    return (f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 {w} {h}" width="{w}" height="{h}" role="img">'
            f"<title>{title}</title><style>{style}"
            "@media (prefers-reduced-motion:reduce){*{animation:none!important}}</style>"
            f"<defs>{defs}</defs>{body}</svg>\n")


def patter_logo(x, y, height):
    """Official Patter lockup (mark + wordmark) scaled so its ink is `height` tall, top-left at (x, y)."""
    src = (HERE / "patter-logo.svg").read_text()
    ds = [d for d, f in re.findall(r'<path d="([^"]+)" fill="([^"]+)"', src) if f == "black"]
    bp = BoundsPen(None)
    for d in ds:
        parse_path(d, bp)
    x0, y0, x1, y1 = bp.bounds
    k = height / (y1 - y0)
    paths = "".join(f'<path d="{d}"/>' for d in ds)
    return f'<g transform="translate({num(x - x0 * k)} {num(y - y0 * k)}) scale({k:.5f})" fill="{INK}">{paths}</g>', (x1 - x0) * k


def tile(cx, cy, s, top, side, content, cls):
    """Isometric tile: a rounded square on the iso plane plus a same-shape sibling below for depth."""
    ox = cx - 0.866 * s
    plane = lambda dy: f'matrix(0.866 -0.5 0.866 0.5 {num(ox)} {num(cy + dy)})'
    face = f'<rect width="{s}" height="{s}" rx="{s * 0.17:.1f}" stroke="{INK}" stroke-width="2" vector-effect="non-scaling-stroke"'
    return (f'<g class="{cls}"><g transform="{plane(16)}">{face} fill="{side}"/></g>'
            f'<g transform="{plane(0)}">{face} fill="{top}"/>{content}</g></g>')


def tile_word(word, s):
    size = min(60, s * 0.74 / INS7.width(word, 1))
    return INS7.path(word, s / 2, s / 2 + INS7.cap * size / 2, size, INK, anchor="middle")


def hero():
    W, H = 1600, 960
    band_y, band_h, size = 72, 160, 100
    name = "Francesco Rosciano"
    base = band_y + band_h / 2 + ARCH.cap * size / 2
    nw = ARCH.width(name, size)

    wall = [f'<rect width="{W}" height="{H}" fill="{WALL}"/>',
            f'<rect width="{W}" height="{H}" filter="url(#grain)" opacity=".9"/>']

    band = [f'<rect y="{band_y + band_h}" width="{W}" height="8" fill="#000" opacity=".35"/>',
            f'<rect y="{band_y}" width="{W}" height="{band_h}" fill="{RED}"/>',
            f'<rect y="{band_y}" width="{W}" height="2" fill="#fff" opacity=".18"/>',
            ARCH.path(name, 72, base, size, WHITE),
            ARCH.path(name, 72 + nw + 220, base, size, WHITE)]  # station names repeat along the band

    sub_base = 314
    lead = "Building Patter"
    lw = ARCH.width(lead, 44)
    tail = "open-source voice AI for real phone lines"
    caption = [ARCH.path(lead, 72, sub_base, 44, WHITE),
               f'<circle cx="{num(72 + lw + 26)}" cy="{num(sub_base - ARCH.cap * 44 / 2)}" r="5" fill="{RED}"/>',
               ARCH.path(tail, 72 + lw + 52, sub_base, 44, "#a7adb0")]

    # Poster in an aluminium frame
    fx, fy, fw, fh, b = 72, 362, 1456, 538, 10
    px, py, pw, ph = fx + b, fy + b, fw - 2 * b, fh - 2 * b
    split = px + 772
    poster = [f'<rect x="{fx}" y="{fy}" width="{fw}" height="{fh}" rx="5" fill="#b8bbbc" filter="url(#shadow)"/>',
              f'<rect x="{fx + 1}" y="{fy + 1}" width="{fw - 2}" height="{fh - 2}" rx="4" fill="none" stroke="#d9dcdc" stroke-width="1.5"/>',
              f'<rect x="{px}" y="{py}" width="{pw}" height="{ph}" fill="#fff"/>',
              f'<rect x="{split}" y="{py}" width="{px + pw - split}" height="{ph}" fill="{CREAM}"/>',
              f'<rect x="{split}" y="{py}" width="{px + pw - split}" height="{ph}" fill="url(#dots)"/>',
              f'<path d="M{split} {py}V{py + ph}" stroke="{INK}" stroke-width="2"/>']
    for sx, sy in ((fx + 5, fy + 5), (fx + fw - 5, fy + 5), (fx + 5, fy + fh - 5), (fx + fw - 5, fy + fh - 5)):
        poster.append(f'<circle cx="{sx}" cy="{sy}" r="3" fill="#7d8283"/>')

    lx, col = px + 64, split - px - 128
    logo, _ = patter_logo(lx, py + 46, 58)
    hs = min(76, col / INS7.width("Give your AI agent", 1))
    b1 = py + 46 + 58 + 50 + INS7.cap * hs
    b2 = b1 + hs * 1.02
    aw = INS7.width("a ", hs)
    b3 = b2 + 62
    chip_y, chip_h = b3 + 36, 58
    cmd = "pip install getpatter"
    cw = MONO.width(cmd, 25) + 78
    facts = ["1,000+ STARS", "MIT", "TWILIO", "TELNYX", "PLIVO"]
    fb = py + ph - 46
    left = [logo,
            INS7.path("Give your AI agent", lx, b1, hs, INK, track=-0.012),
            INS7.path("a", lx, b2, hs, INK, track=-0.012),
            INS7.path("phone number.", lx + aw, b2, hs, TERRA, track=-0.012),
            INS4.path("Open-source SDK. Python and TypeScript. MIT.", lx, b3, 29, MUTED),
            f'<rect x="{lx}" y="{num(chip_y)}" width="{num(cw)}" height="{chip_h}" rx="{chip_h / 2}" fill="#fff" stroke="{INK}" stroke-width="2"/>',
            f'<circle cx="{lx + 30}" cy="{num(chip_y + chip_h / 2)}" r="6" fill="{TERRA}"/>',
            MONO.path(cmd, lx + 52, chip_y + chip_h / 2 + MONO.cap * 25 / 2, 25, INK)]
    fx2 = lx
    for i, f in enumerate(facts):
        if i:
            left.append(f'<circle cx="{num(fx2 + 16)}" cy="{num(fb - MONO.cap * 20 / 2)}" r="3" fill="#aaa"/>')
            fx2 += 32
        left.append(MONO.path(f, fx2, fb, 20, INK if i == 0 else "#666", track=0.06))
        fx2 += MONO.width(f, 20, 0.06)

    s, cx = 168, (split + px + pw) / 2
    cy = py + ph / 2 - 8
    k = s * 0.5 / 24
    phone = (f'<g transform="translate({num(s / 2 - 12 * k)} {num(s / 2 - 12 * k)}) scale({k:.4f})">'
             f'<path d="{PHONE}" fill="none" stroke="{INK}" stroke-width="3.5" stroke-linecap="round" stroke-linejoin="round" vector-effect="non-scaling-stroke"/></g>')
    stack = [tile(cx, cy + 120, s, "#fff", SIDE, phone, "t t1"),
             tile(cx, cy, s, PEACH_L, PEACH, tile_word("Patter", s), "t t2"),
             tile(cx, cy - 120, s, "#fff", SIDE, tile_word("Agent", s), "t t3")]
    stack.append(MONO.path("github.com/PatterAI/Patter", px + pw - 28, py + ph - 24, 18, "#555", anchor="end"))

    defs = ('<filter id="grain" x="0" y="0" width="100%" height="100%"><feTurbulence type="fractalNoise" baseFrequency=".85" numOctaves="2" stitchTiles="stitch"/>'
            '<feColorMatrix values="0 0 0 0 1  0 0 0 0 1  0 0 0 0 1  0 0 0 .05 0"/></filter>'
            '<filter id="shadow" x="-5%" y="-5%" width="110%" height="120%"><feDropShadow dx="0" dy="14" stdDeviation="16" flood-color="#000" flood-opacity=".55"/></filter>'
            f'<pattern id="dots" width="28" height="28" patternUnits="userSpaceOnUse"><circle cx="14" cy="14" r="2.4" fill="{DOT}"/></pattern>')
    style = ("@keyframes drop{from{transform:translateY(-70px);opacity:0}}"
             ".t{animation:drop 1s cubic-bezier(.16,1,.3,1) both}.t1{animation-delay:.15s}.t2{animation-delay:.35s}.t3{animation-delay:.55s}")
    body = "".join(wall + band + caption + poster + left + stack)
    return svg(W, H, "Francesco Rosciano. Building Patter: give your AI agent a phone number.", defs, body, style)


def lines():
    W = 1600
    ls, ps = 42, 56
    angle = 38
    sin, cos = math.sin(math.radians(angle)), math.cos(math.radians(angle))
    red_names = ["awesome-claude-call", "patter-mcp", "skills"]
    rise = max(ARCH.width(n, ls) for n in red_names) * sin
    red_y = round(40 + rise + 52)
    green_y = red_y + 180
    fall = max(ARCH.width(n, ls) for n in ["e2e-bughunt", "bugpin"]) * sin
    H = round(green_y + 44 + fall + 56)
    hub = 200

    def badge(x_end, y, label, color):
        w = ARCH7.width(label, 30) + 48
        x = x_end - w
        return x, (f'<rect x="{num(x)}" y="{y - 30}" width="{num(w)}" height="60" rx="10" fill="{color}"/>'
                   + ARCH7.path(label, x + 24, y + ARCH7.cap * 30 / 2, 30, WHITE))

    def label(x, y, text, size, face, up, delay):
        rot = -angle if up else angle
        ox, oy = (x + 16, y - 36) if up else (x + 18, y + 40 + face.cap * size)
        return (f'<g class="f" style="animation-delay:{delay:.2f}s" transform="rotate({rot} {num(ox)} {num(oy)})">'
                + face.path(text, ox, oy, size, INK) + "</g>")

    def station(x, y, color, r, sw, delay):
        return (f'<circle class="p" style="animation-delay:{delay:.2f}s" cx="{num(x)}" cy="{num(y)}" r="{r}" '
                f'fill="#fff" stroke="{color}" stroke-width="{sw}"/>')

    rx_end, red_badge = badge(W - 52, red_y, "Patter line", RED)
    gx_end, green_badge = badge(1250, green_y, "Tools line", GREEN)
    bend = hub + (green_y - red_y)
    red_len = rx_end - hub
    green_len = (green_y - red_y) * math.sqrt(2) + (gx_end - bend)
    dur = 1.6

    def at(d, length):  # when the drawing line reaches distance d (roughly, for the ease-out curve)
        return 0.15 + dur * 0.55 * (d / length) ** 1.6

    red_st = [(470, "Patter", True)] + [(x, n, False) for x, n in zip((760, 1040, 1300), red_names)]
    green_st = [(620, "e2e-bughunt"), (960, "bugpin")]
    gd = lambda x: (green_y - red_y) * math.sqrt(2) + (x - bend)

    parts = [f'<rect x="2" y="2" width="{W - 4}" height="{H - 4}" rx="22" fill="#f4f4f0" stroke="#141414" stroke-width="4"/>',
             f'<path class="lr" d="M{hub} {red_y}H{num(rx_end)}" stroke="{RED}" stroke-width="22" fill="none"/>',
             f'<path class="lg" d="M{hub} {red_y}L{bend} {green_y}H{num(gx_end)}" stroke="{GREEN}" stroke-width="22" fill="none" stroke-linejoin="round"/>',
             red_badge, green_badge]
    for x, n, big in red_st:
        t = at(x - hub, red_len)
        parts.append(station(x, red_y, INK if big else RED, 25 if big else 17, 8 if big else 7, t))
        parts.append(label(x, red_y, n, ps if big else ls, ARCH7 if big else ARCH, True, t + 0.1))
    for x, n in green_st:
        t = at(gd(x), green_len) + 0.2
        parts.append(station(x, green_y, GREEN, 17, 7, t))
        parts.append(label(x, green_y, n, ls, ARCH, False, t + 0.1))
    # Hub: this profile.
    parts.append(f'<circle cx="{hub}" cy="{red_y}" r="32" fill="#fff" stroke="{INK}" stroke-width="9"/>'
                 f'<circle cx="{hub}" cy="{red_y}" r="12" fill="{RED}"/>')
    parts.append(label(hub + 20, red_y - 6, "You are here", ls, ARCH7, True, 0))

    style = (f"@keyframes dr{{from{{stroke-dashoffset:{red_len:.0f}}}}}@keyframes dg{{from{{stroke-dashoffset:{green_len:.0f}}}}}"
             "@keyframes pop{from{opacity:0;transform:scale(.3)}}@keyframes fade{from{opacity:0}}"
             f".lr{{stroke-dasharray:{red_len:.0f};animation:dr {dur}s cubic-bezier(.16,1,.3,1) .15s both}}"
             f".lg{{stroke-dasharray:{green_len:.0f};animation:dg {dur}s cubic-bezier(.16,1,.3,1) .35s both}}"
             ".p{transform-box:fill-box;transform-origin:center;animation:pop .5s cubic-bezier(.16,1,.3,1) both}"
             ".f{animation:fade .6s ease-out both}")
    return svg(W, H, "Line map: the Patter line runs to Patter, awesome-claude-call, patter-mcp, and skills; the Tools line runs to e2e-bughunt and bugpin.",
               "", "".join(parts), style)


if __name__ == "__main__":
    OUT.mkdir(exist_ok=True)
    for name, fn in (("hero", hero), ("lines", lines)):
        data = fn()
        assert "<text" not in data and "font-family" not in data  # outlines only
        (OUT / f"{name}.svg").write_text(data)
        print(f"assets/{name}.svg  {len(data) // 1024} KB")
