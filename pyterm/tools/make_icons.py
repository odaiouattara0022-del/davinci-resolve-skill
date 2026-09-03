#!/usr/bin/env python3
"""Genere les icones et les ecrans de lancement de PyTerm.

Safari ignore les icones SVG pour l'ecran d'accueil : il faut de vraies PNG,
et des images de lancement aux dimensions exactes de chaque iPhone. Ce script
les dessine sans aucune dependance — zlib et struct suffisent.

    python3 pyterm/tools/make_icons.py

Le rendu se fait par fonctions de distance signee echantillonnees 4x4, ce qui
donne un anticrenelage propre a toutes les tailles.
"""

from __future__ import annotations

import math
import struct
import zlib
from pathlib import Path

ASSETS = Path(__file__).resolve().parent.parent / "assets"

BG = (0x1B, 0x1F, 0x27)
BLUE = (0x57, 0xA5, 0xF5)
GREEN = (0x6F, 0xCF, 0x8B)

SS = 4                      # sous-echantillons par axe
SS_OFFSETS = [(i + 0.5) / SS for i in range(SS)]


# --------------------------------------------------------------------------
# Ecriture PNG
# --------------------------------------------------------------------------

def write_png(path: Path, width: int, height: int, rows: list[bytearray]) -> None:
    """Ecrit un PNG RGB 8 bits (filtre 0, une passe zlib)."""
    raw = b"".join(b"\x00" + bytes(row) for row in rows)

    def chunk(tag: bytes, payload: bytes) -> bytes:
        return (struct.pack(">I", len(payload)) + tag + payload
                + struct.pack(">I", zlib.crc32(tag + payload) & 0xFFFFFFFF))

    png = b"\x89PNG\r\n\x1a\n"
    png += chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    png += chunk(b"IDAT", zlib.compress(raw, 9))
    png += chunk(b"IEND", b"")
    path.write_bytes(png)


# --------------------------------------------------------------------------
# Distances signees : negatif = interieur
# --------------------------------------------------------------------------

def sd_rounded_rect(px: float, py: float, cx: float, cy: float,
                    half_w: float, half_h: float, radius: float) -> float:
    dx = abs(px - cx) - (half_w - radius)
    dy = abs(py - cy) - (half_h - radius)
    outside = math.hypot(max(dx, 0.0), max(dy, 0.0))
    return outside + min(max(dx, dy), 0.0) - radius


def sd_segment(px: float, py: float, ax: float, ay: float,
               bx: float, by: float, half_width: float) -> float:
    vx, vy = bx - ax, by - ay
    wx, wy = px - ax, py - ay
    length2 = vx * vx + vy * vy
    t = 0.0 if length2 == 0 else max(0.0, min(1.0, (wx * vx + wy * vy) / length2))
    return math.hypot(wx - vx * t, wy - vy * t) - half_width


def sd_circle(px: float, py: float, cx: float, cy: float, radius: float) -> float:
    return math.hypot(px - cx, py - cy) - radius


# --------------------------------------------------------------------------
# Composition
# --------------------------------------------------------------------------

def blend(dst: bytearray, index: int, colour: tuple[int, int, int], alpha: float) -> None:
    if alpha <= 0.0:
        return
    if alpha >= 1.0:
        dst[index], dst[index + 1], dst[index + 2] = colour
        return
    inv = 1.0 - alpha
    for k in range(3):
        dst[index + k] = int(dst[index + k] * inv + colour[k] * alpha + 0.5)


def logo_shapes(cx: float, cy: float, size: float) -> list:
    """Le logo : un chevron, une barre, un point. Coordonnees absolues."""
    x0, y0 = cx - size / 2, cy - size / 2
    p = lambda u, v: (x0 + u * size, y0 + v * size)      # noqa: E731
    stroke = size * 0.088
    a, b, c = p(0.30, 0.30), p(0.50, 0.50), p(0.30, 0.70)
    d, e = p(0.58, 0.72), p(0.78, 0.72)
    dot = p(0.74, 0.30)
    return [
        ("seg", a + b + (stroke / 2,), BLUE),
        ("seg", b + c + (stroke / 2,), BLUE),
        ("seg", d + e + (stroke / 2,), BLUE),
        ("circle", dot + (size * 0.072,), GREEN),
    ]


def render(width: int, height: int, logo_size: float,
           logo_center: tuple[float, float] | None = None,
           corner_radius: float | None = None) -> list[bytearray]:
    """Fond uni + logo centre, avec coins arrondis facultatifs."""
    cx, cy = logo_center or (width / 2, height / 2)
    shapes = logo_shapes(cx, cy, logo_size)

    # Zone a echantillonner finement : le logo, et les coins si arrondis.
    margin = logo_size * 0.1
    box = (cx - logo_size / 2 - margin, cy - logo_size / 2 - margin,
           cx + logo_size / 2 + margin, cy + logo_size / 2 + margin)

    blank = bytes(BG) * width
    rows: list[bytearray] = []
    for y in range(height):
        in_logo_band = box[1] <= y + 1 and y <= box[3]
        if not in_logo_band and not corner_radius:
            rows.append(bytearray(blank))      # ligne de fond pur : rien a calculer
            continue
        row = bytearray(blank)
        x_from, x_to = 0, width
        if not corner_radius:                  # restreint au logo hors coins arrondis
            x_from = max(0, int(box[0]) - 1)
            x_to = min(width, int(box[2]) + 2)
        for x in range(x_from, x_to):
            if corner_radius:
                # Les coins arrondis exigent la transparence, impossible en RGB :
                # on assombrit vers le noir pour un rendu correct sur fond sombre.
                cover = 0.0
                for oy in SS_OFFSETS:
                    for ox in SS_OFFSETS:
                        if sd_rounded_rect(x + ox, y + oy, width / 2, height / 2,
                                           width / 2, height / 2, corner_radius) <= 0:
                            cover += 1
                cover /= SS * SS
                if cover < 1.0:
                    blend(row, x * 3, (0, 0, 0), 1.0 - cover)

            if not (in_logo_band and box[0] <= x + 1 and x <= box[2]):
                continue

            for kind, args, colour in shapes:
                cover = 0.0
                for oy in SS_OFFSETS:
                    for ox in SS_OFFSETS:
                        px, py = x + ox, y + oy
                        dist = (sd_segment(px, py, *args) if kind == "seg"
                                else sd_circle(px, py, *args))
                        if dist <= 0:
                            cover += 1
                if cover:
                    blend(row, x * 3, colour, cover / (SS * SS))
        rows.append(row)
    return rows


# --------------------------------------------------------------------------

ICONS = [
    # (fichier, cote, part du logo, rayon des coins en part du cote)
    ("icon-180.png", 180, 0.72, None),        # apple-touch-icon : iOS arrondit lui-meme
    ("icon-192.png", 192, 0.72, 0.22),
    ("icon-512.png", 512, 0.72, 0.22),
    ("icon-512-maskable.png", 512, 0.52, None),   # marge de securite pour le masquage
    ("icon-1024.png", 1024, 0.72, None),
    ("favicon-32.png", 32, 0.78, None),
]

# Ecrans de lancement iOS : dimensions exactes, sinon Safari les ignore.
SPLASHES = [
    (1290, 2796), (1179, 2556), (1284, 2778), (1170, 2532),
    (1125, 2436), (1242, 2688), (828, 1792), (750, 1334), (640, 1136),
]


def main() -> int:
    ASSETS.mkdir(parents=True, exist_ok=True)

    for name, side, logo_frac, radius_frac in ICONS:
        rows = render(side, side, side * logo_frac,
                      corner_radius=(side * radius_frac) if radius_frac else None)
        write_png(ASSETS / name, side, side, rows)
        print("  %-24s %4dx%-4d %6d o" % (name, side, side, (ASSETS / name).stat().st_size))

    splash_dir = ASSETS / "splash"
    splash_dir.mkdir(exist_ok=True)
    for width, height in SPLASHES:
        name = "launch-%dx%d.png" % (width, height)
        rows = render(width, height, min(width, height) * 0.34)
        write_png(splash_dir / name, width, height, rows)
        print("  splash/%-17s %4dx%-4d %6d o"
              % (name, width, height, (splash_dir / name).stat().st_size))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
