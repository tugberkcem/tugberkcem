#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
make_ascii_svg.py
=================
Hazirlanmis gri tonlamali PNG'yi (assets/prep/portrait_ascii.png) alip
SMIL animasyonlu, monospace "daktilo efektiyle" yazilan bir ASCII SVG'sine
donusturur.

Cikti:
    avi-ascii.svg   (profil README'sinde kullanilir)

Efekt:
    * Her satir sirayla ortaya cikar (typewriter / daktilo)
    * Uzun bir <textPath> uzerinde startOffset animasyonu ile, gercek bir
      terminalin satir satir dokulmesi hissi verilir.
    * Her karakter icin ayri animasyon yoktur -> SVG hafif kalir, GitHub
      sorunsuz render eder.

Kullanim:
    python scripts/make_ascii_svg.py
    python scripts/make_ascii_svg.py --cols 100 --font-size 9 --color "#00ff9c"
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

# --------------------------------------------------------------------------
# Sabitler
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
INPUT_PNG = ROOT / "assets" / "prep" / "portrait_ascii.png"
OUTPUT_SVG = ROOT / "avi-ascii.svg"

# Karakter yogunlugu: soldan saga acik -> koyu
# (koyu bolgeler bosluga, aydinlik bolgeler '@' karakterine karsilik gelir)
ASCII_CHARS = " .:-=+*#%@"

# --------------------------------------------------------------------------
# Animasyon kontrol tokenlari (SMIL durdurma/oynatma icin)
# --------------------------------------------------------------------------
ANIM_BEGIN = (
    "0s;anim_typer.click+0s;"
    "anim_pause_all.click+0s;"
    "anim_resume_all.click+0s"
)


def die(msg: str) -> None:
    print("\n" + msg + "\n", file=sys.stderr)
    raise SystemExit(1)


# --------------------------------------------------------------------------
# 1) Goruntu -> ASCII matrisi
# --------------------------------------------------------------------------
def load_gray(path: Path) -> np.ndarray:
    if not path.exists():
        die(
            "HATA: 'assets/prep/portrait_ascii.png' bulunamadi!\n\n"
            "Once su komutu calistirmalisiniz:\n"
            "    python scripts/prep_photo.py\n\n"
            "Bu komut, 'source-photo.jpg' dosyasindan ASCII kaynagini uretir."
        )
    data = np.fromfile(str(path), dtype=np.uint8)
    img = cv2.imdecode(data, cv2.IMREAD_GRAYSCALE)
    if img is None:
        die(f"HATA: Goruntu okunamadi: {path}")
    return img


def gray_to_ascii(gray: np.ndarray, cols: int) -> list[str]:
    """Gri tonlamali goruntuyu ASCII karakter satirlarina cevirir."""
    h, w = gray.shape
    # Karakter hucreleri dikeyde daha uzun oldugu icin en-boy oranini duzelt
    CHAR_ASPECT = 0.50
    rows = max(1, int(cols * (h / w) * CHAR_ASPECT))

    # INTER_AREA: kucultmede en temiz sonucu verir (anti-aliasing)
    small = cv2.resize(gray, (cols, rows), interpolation=cv2.INTER_AREA)

    # Yerel kontrast: karakter dagilimini genisletir, siluet netlesir
    small = cv2.normalize(small, None, 0, 255, cv2.NORM_MINMAX)

    n = len(ASCII_CHARS)
    lines: list[str] = []
    for row in small:
        line = "".join(ASCII_CHARS[min(n - 1, int(v) * n // 256)] for v in row)
        # Sag taraftaki bosluklari kirp (SVG'yi kucultmek icin)
        lines.append(line.rstrip())
    return lines


# --------------------------------------------------------------------------
# 2) SVG uretimi
# --------------------------------------------------------------------------
def _xml_escape(text: str) -> str:
    return (
        text.replace("&", "&amp;")
        .replace("<", "&lt;")
        .replace(">", "&gt;")
        .replace('"', "&quot;")
    )


def build_svg(
    lines: list[str],
    font_size: float,
    color: str,
    bg: str,
    line_height: float,
    char_width: float,
    duration: float,
) -> str:
    """
    Her satir icin bir <text> elemanı üretir ve SMIL ile sirayla acar.

    Neden startOffset degil de
    satir bazli opacity + clip?
      -> GitHub'in SVG sanitizer'i bazi startOffset animasyonlarini kirpiyor.
         En saglam yontem: her satiri bir <g clip-path> icinde tutmak ve
         o grubun <rect> genisligini soldan saga animasyonla buyutmek.
         Bu, "daktilo" (character-by-character wipe) etkisi verir ve
         tum tarayicilarda calisir.
    """
    max_chars = max((len(l) for l in lines), default=1)
    width = max_chars * char_width + 2 * char_width
    height = len(lines) * line_height + line_height

    parts: list[str] = []
    parts.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, '
        f"'DejaVu Sans Mono', monospace\" "
        f'font-size="{font_size}" fill="{color}">'
    )

    # Arka plan
    parts.append(
        f'<rect x="0" y="0" width="{width:.0f}" height="{height:.0f}" '
        f'fill="{bg}" rx="6"/>'
    )

    # Kesif icin gizli (gorunmez) butonlar: pause / resume
    # (README icinde gomulu SVG'de tiklanamaz ama SMIL'in gecerli kalmasi icin tutulur)
    parts.append(
        '<rect id="anim_pause_all" width="1" height="1" opacity="0"/>\n'
        '<rect id="anim_resume_all" width="1" height="1" opacity="0"/>\n'
        '<rect id="anim_typer" width="1" height="1" opacity="0"/>'
    )

    n = len(lines)
    for i, line in enumerate(lines):
        if not line:
            continue

        y = line_height * (i + 1)
        line_w = len(line) * char_width + char_width

        # Her satir kendi clip alanina sahip; alan soldan saga acilir.
        clip_id = f"tsclip{i}"
        begin = i * (duration / max(1, n))
        dur = duration / max(1, n)

        parts.append(f'<clipPath id="{clip_id}">')
        parts.append(
            f'<rect x="0" y="{y - line_height:.2f}" width="0" '
            f'height="{line_height:.2f}">'
        )
        # Genisligi 2*dur boyunca soldan saga buyut; sonra sabit kal
        parts.append(
            f'<animate attributeName="width" '
            f'from="0" to="{line_w:.2f}" '
            f'begin="{begin:.2f}s" dur="{dur:.2f}s" '
            f'fill="freeze" calcMode="spline" '
            f'keySplines="0.4 0 0.2 1"/>'
        )
        parts.append("</rect></clipPath>")

        parts.append(
            f'<text x="{char_width:.2f}" y="{y:.2f}" '
            f'clip-path="url(#{clip_id})" '
            f'xml:space="preserve">{_xml_escape(line)}</text>'
        )

    # Sonsuz dongude imlec (blok) yanip sonmesi
    parts.append(
        f'<rect x="{char_width:.2f}" y="{height - line_height:.2f}" '
        f'width="{char_width:.2f}" height="{font_size * 1.05:.2f}" '
        f'fill="{color}">'
        f'<animate attributeName="opacity" values="1;0;1" '
        f'dur="1.1s" repeatCount="indefinite"/>'
        f"</rect>"
    )

    parts.append("</svg>")
    return "\n".join(parts)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="ASCII portreyi animasyonlu SVG'ye cevir")
    ap.add_argument("--cols", type=int, default=88, help="ASCII karakter sutun sayisi")
    ap.add_argument("--font-size", type=float, default=10.0, help="Font boyutu (px)")
    ap.add_argument("--color", default="#00ff9c", help="Metin rengi")
    ap.add_argument("--bg", default="#0d1117", help="Arka plan rengi")
    ap.add_argument("--duration", type=float, default=3.0, help="Toplam yazma suresi (sn)")
    ap.add_argument("--output", default=str(OUTPUT_SVG), help="Cikti SVG yolu")
    args = ap.parse_args()

    print("\n=== tugberkcem | make_ascii_svg.py ===\n")

    gray = load_gray(INPUT_PNG)
    lines = gray_to_ascii(gray, cols=args.cols)
    print(f"  ASCII matrisi : {len(lines)} satir x {args.cols} sutun")

    # Monospace fontta karakter genisligi ~ font-size * 0.60
    char_width = args.font_size * 0.60
    line_height = args.font_size * 1.06

    svg = build_svg(
        lines=lines,
        font_size=args.font_size,
        color=args.color,
        bg=args.bg,
        line_height=line_height,
        char_width=char_width,
        duration=args.duration,
    )

    out = Path(args.output)
    out.write_text(svg, encoding="utf-8")
    size_kb = out.stat().st_size / 1024
    print(f"  Cikti         : {out.name}  ({size_kb:.1f} KB)")
    print("\n  Bitti! SVG'yi tarayicida acip animasyonu kontrol edebilirsiniz.\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
