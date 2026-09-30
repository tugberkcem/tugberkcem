#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_info_card.py
=================
Neofetch tarzi, renkli, SMIL animasyonlu bir terminal bilgi karti uretir.

Cikti:
    info-card.svg

Ozellikler:
    * Sol tarafta ASCII "logo" blogu (OS logolari gibi), sag tarafta key/value.
    * Key'ler turkuaz/kirmizi (neofetch renk semasi), value'lar beyaz.
    * Her satir sirayla "yaziliyor" gibi acilir.
    * Basliga sahte bir shell prompt'u: tugberkcem@github ~ $ neofetch
    * Sag altta renk paleti bloklari (neofetch klasigi).

Kullanim:
    python scripts/make_info_card.py
"""

from __future__ import annotations

import argparse
import html
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
OUTPUT_SVG = ROOT / "info-card.svg"

# --------------------------------------------------------------------------
# Icerik
# --------------------------------------------------------------------------
KEY_COLOR = "#5eead4"       # neofetch "user@host" turkuaz
ACCENT = "#f97583"          # kirmizi vurgu
VALUE_COLOR = "#e6edf3"     # beyaz
DIM = "#8b949e"
BG = "#0d1117"

ROWS: list[tuple[str, str]] = [
    ("OS",         "Linux / Unix (openEuler, OpenWrt)"),
    ("Role",       "Software Engineer — Backend & Embedded"),
    ("Languages",  "C++, Python, C, SQL"),
    ("Frameworks", "Qt, PyQt, FastAPI, Flask, Flutter"),
    ("Hardware",   "STM32, Arduino, ARM Cortex-M"),
    ("Focus",      "Embedded · Network Analysis · DSP · MVC"),
    ("Projects",   "PetMate Assistant, CoMedic, DSP Audio Filters"),
    ("Education",  "Software Eng. (GPA 3.14 / 4.00)"),
    ("Status",     "Open to opportunities"),
]

LOGO = [
    "        .--.        ",
    "       |o_o |       ",
    "       |:_/ |       ",
    "      //   \\ \\      ",
    "     (|     | )     ",
    "    /'\\_   _/`\\     ",
    "    \\___)=(___/     ",
]


def esc(t: str) -> str:
    """XML (metin) icerigi icin kacis. & -> &amp; dahil."""
    return html.escape(t, quote=False)


def esc_attr(t: str) -> str:
    """XML attribute degeri icin kacis (tirnak dahil)."""
    return html.escape(t, quote=True)


def _char_width(font_size: float) -> float:
    return font_size * 0.602


def build_svg(row_delay: float = 0.16, font_size: float = 13.0) -> str:
    cw = _char_width(font_size)
    lh = font_size * 1.62           # satir yuksekligi
    pad = 22.0
    title_h = font_size * 1.9       # ust baslik (trafik isiklari) alani

    logo_w = max(len(l) for l in LOGO) * cw
    gap = cw * 3
    text_x = pad + logo_w + gap

    label_w = max(len(k) for k, _ in ROWS) + 1     # "Highlights:" dahil
    longest_value = max(len(v) for _, v in ROWS)
    prompt_chars = len("tugberkcem@github ~ $ neofetch")
    content_chars = max(label_w + longest_value, prompt_chars)

    palette = ["#ff5f56", "#ffbd2e", "#27c93f", "#5eead4",
               "#58a6ff", "#bc8cff", "#f97583", "#e6edf3"]
    width = text_x + content_chars * cw + pad

    # --- Dikey yerlesim: HER SEY gercek icerikten hesaplanir ---------------
    top = pad + title_h

    logo_block_h = len(LOGO) * lh
    rows_h = len(ROWS) * lh
    prompt_h = lh * 2.0
    palette_h = lh * 1.4
    cursor_h = lh * 1.1

    # Logo blogu ile metin blogunun ikisi de top'tan baslar; yuksekligi
    # buyuk olan belirler.
    columns_h = max(logo_block_h, prompt_h + rows_h + palette_h + cursor_h)
    height = top + columns_h + pad

    p: list[str] = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, '
        f"'DejaVu Sans Mono', monospace\" font-size=\"{font_size}\">"
    )

    # Arka plan + cerceve
    p.append(
        f'<rect x="0.5" y="0.5" width="{width-1:.1f}" height="{height-1:.1f}" '
        f'rx="8" fill="{BG}" stroke="#30363d" stroke-width="1"/>'
    )

    # macOS tarzi "trafik isiklari"
    for i, c in enumerate(("#ff5f56", "#ffbd2e", "#27c93f")):
        p.append(
            f'<circle cx="{pad + 5 + i*18:.1f}" cy="{pad + title_h*0.5:.1f}" '
            f'r="5" fill="{c}"/>'
        )

    # --- Sol logo blogu -----------------------------------------------------
    logo_y = top + cw  # ilk baseline
    p.append(
        f'<g fill="{ACCENT}" opacity="0">'
        f'<animate attributeName="opacity" from="0" to="0.95" dur="0.6s" '
        f'begin="0.1s" fill="freeze"/>'
    )
    for i, line in enumerate(LOGO):
        p.append(
            f'<text x="{pad:.1f}" y="{logo_y + i*lh:.1f}" '
            f'xml:space="preserve">{esc(line)}</text>'
        )
    p.append("</g>")

    # --- Ust satir: prompt --------------------------------------------------
    prompt_y = top + cw
    prompt_parts = [
        ("tugberkcem", KEY_COLOR),
        ("@", DIM),
        ("github", KEY_COLOR),
        (" ~ ", DIM),
        ("$ ", "#f97583"),
        ("neofetch", VALUE_COLOR),
    ]
    x = text_x
    p.append('<g opacity="0"><animate attributeName="opacity" from="0" to="1" '
             'dur="0.3s" begin="0.2s" fill="freeze"/>')
    for txt, col in prompt_parts:
        p.append(
            f'<text x="{x:.2f}" y="{prompt_y:.1f}" fill="{col}" '
            f'xml:space="preserve">{esc(txt)}</text>'
        )
        x += len(txt) * cw
    p.append("</g>")

    # --- Key / value satirlari (sirayla yazilir) ---------------------------
    row_y = prompt_y + lh * 1.7
    for i, (key, value) in enumerate(ROWS):
        begin = 0.55 + i * row_delay
        label = f"{key}:"
        p.append(
            f'<g opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" dur="0.01s" '
            f'begin="{begin:.2f}s" fill="freeze"/>'
            f'<text x="{text_x:.2f}" y="{row_y:.1f}" fill="{KEY_COLOR}" '
            f'font-weight="bold" xml:space="preserve">{esc(label)}</text>'
            f"</g>"
        )
        vx = text_x + label_w * cw
        p.append(
            f'<g opacity="0">'
            f'<animate attributeName="opacity" from="0" to="1" dur="0.01s" '
            f'begin="{begin + 0.08:.2f}s" fill="freeze"/>'
            f'<text x="{vx:.2f}" y="{row_y:.1f}" fill="{VALUE_COLOR}" '
            f'xml:space="preserve">{esc(value)}</text>'
            f"</g>"
        )
        row_y += lh

    # --- Renk paleti (neofetch klasigi) ------------------------------------
    row_y += lh * 0.30
    bx = text_x
    bh = font_size * 0.85
    p.append(
        f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" '
        f'dur="0.4s" begin="0.9s" fill="freeze"/>'
    )
    for c in palette:
        p.append(
            f'<rect x="{bx:.2f}" y="{row_y - bh:.1f}" width="{cw*2.2:.2f}" '
            f'height="{bh:.2f}" rx="2" fill="{c}"/>'
        )
        bx += cw * 2.2 + 3
    p.append("</g>")

    # Yanip sonen imlec
    p.append(
        f'<rect x="{text_x:.2f}" y="{row_y + lh*0.35:.1f}" '
        f'width="{cw:.2f}" height="{font_size*0.95:.2f}" fill="{VALUE_COLOR}">'
        f'<animate attributeName="opacity" values="1;0;1" dur="1.1s" '
        f'repeatCount="indefinite"/>'
        f"</rect>"
    )

    p.append("</svg>")
    return "\n".join(p)


def main() -> int:
    ap = argparse.ArgumentParser(description="Neofetch tarzi info-card.svg uret")
    ap.add_argument("--output", default=str(OUTPUT_SVG))
    ap.add_argument("--font-size", type=float, default=13.0)
    args = ap.parse_args()

    print("\n=== tugberkcem | make_info_card.py ===\n")
    svg = build_svg(font_size=args.font_size)

    out = Path(args.output)
    out.write_text(svg, encoding="utf-8")
    print(f"  Cikti : {out.name}  ({out.stat().st_size/1024:.1f} KB)")
    print("\n  Bitti!\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
