#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
render_heatmap_svg.py
=====================
`assets/data/contributions.json` dosyasini okur ve GitHub'in katki takvimine
benzeyen, CAPRAZ KAYMA (diagonal wipe) animasyonlu bir SVG uretir.

Cikti:
    contrib-heatmap.svg

Animasyon:
    Her hucre (gun), grid'deki konumuna gore (sutun + satir) gecikmeli olarak
    soldan saga dogru acilir. Boylece izleyici, katkilarin sol ust koseden
    sag alt koseye dogru "dalga halinde" belirdigini gorur.

Kullanim:
    python scripts/render_heatmap_svg.py
    python scripts/render_heatmap_svg.py --cell 12
"""

from __future__ import annotations

import argparse
import datetime as dt
import html
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
IN_JSON = ROOT / "assets" / "data" / "contributions.json"
OUTPUT_SVG = ROOT / "contrib-heatmap.svg"

# GitHub'in resmi yesil paleti (0-4)
LEVEL_COLORS = ["#161b22", "#0e4429", "#006d32", "#26a641", "#39d353"]
BG = "#0d1117"
BORDER = "#30363d"
TEXT = "#8b949e"

MONTHS = ["Jan", "Feb", "Mar", "Apr", "May", "Jun",
          "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"]
WEEKDAYS = ["", "Mon", "", "Wed", "", "Fri", ""]  # GitHub boyle gosteriyor


def die(msg: str) -> None:
    print("\n" + msg + "\n", file=sys.stderr)
    raise SystemExit(1)


def esc(t: str) -> str:
    return html.escape(str(t), quote=True)


# --------------------------------------------------------------------------
# Grid'e yerlestirme
# --------------------------------------------------------------------------
def build_grid(days: list[dict]) -> tuple[list[list[dict | None]], dt.date, int]:
    """
    Gunleri haftalik sutunlara yerlestirir.
    Donen: (weeks, first_sunday, num_weeks)
      weeks[week_index][weekday_sun_0_6] = day dict veya None
    """
    parsed: list[dict] = []
    for d in days:
        try:
            date = dt.date.fromisoformat(d["date"])
        except (KeyError, ValueError):
            continue
        parsed.append({"date": date, "count": d.get("count", 0), "level": d.get("level", 0)})

    if not parsed:
        die("HATA: JSON icinde gecerli tarih bulunamadi.")

    parsed.sort(key=lambda x: x["date"])
    first = parsed[0]["date"]

    # Ilk gunu iceren haftanin Pazar'i
    first_sunday = first - dt.timedelta(days=(first.weekday() + 1) % 7)

    num_weeks = ((parsed[-1]["date"] - first_sunday).days // 7) + 1
    weeks: list[list[dict | None]] = [[None] * 7 for _ in range(num_weeks)]

    for item in parsed:
        delta = (item["date"] - first_sunday).days
        w, r = divmod(delta, 7)
        if 0 <= w < num_weeks:
            weeks[w][r] = item

    return weeks, first_sunday, num_weeks


# --------------------------------------------------------------------------
# SVG
# --------------------------------------------------------------------------
def build_svg(
    weeks: list[list[dict | None]],
    total: int,
    cell: float,
    gap: float,
    stagger: float,
    user: str,
) -> str:
    left_label = cell * 3.4          # gun isimleri icin
    top_label = cell * 2.0           # ay isimleri icin
    pad = cell * 1.2

    step = cell + gap
    num_weeks = len(weeks)

    grid_w = num_weeks * step - gap
    grid_h = 7 * step - gap

    width = left_label + grid_w + pad * 2
    height = top_label + grid_h + pad * 2 + cell * 2.6  # altta legend + toplam

    gx = pad + left_label
    gy = pad + top_label

    p: list[str] = []
    p.append(
        f'<svg xmlns="http://www.w3.org/2000/svg" '
        f'width="{width:.0f}" height="{height:.0f}" '
        f'viewBox="0 0 {width:.0f} {height:.0f}" '
        f'font-family="ui-monospace, SFMono-Regular, Menlo, Consolas, '
        f"'DejaVu Sans Mono', monospace\" font-size=\"{cell*0.95:.1f}\">"
    )

    # Kart arka plani
    p.append(
        f'<rect x="0.5" y="0.5" width="{width-1:.1f}" height="{height-1:.1f}" '
        f'rx="10" fill="{BG}" stroke="{BORDER}" stroke-width="1"/>'
    )

    # --- Ay etiketleri ------------------------------------------------------
    # Not: Ay etiketleri bolgenin basindaki haftalarda dogar. Iki etiket
    # birbirine cok yakinsa ("SepOct" gibi) ust uste biner; bu yuzden
    # aralarinda en az MIN_LABEL_WEEKS hafta olmasini zorluyoruz.
    MIN_LABEL_WEEKS = 4
    p.append(f'<g fill="{TEXT}">')
    last_month = -1
    last_label_week = -MIN_LABEL_WEEKS - 1
    for w in range(num_weeks):
        # Sutunun ilk dolu gunune bak
        for r in range(7):
            day = weeks[w][r]
            if day:
                m = day["date"].month
                if m != last_month:
                    last_month = m
                    # Cakismayi engelle: yeterince yer var mi?
                    if w - last_label_week >= MIN_LABEL_WEEKS:
                        x = gx + w * step
                        p.append(
                            f'<text x="{x:.1f}" y="{gy - cell*0.6:.1f}" '
                            f'xml:space="preserve">{MONTHS[m-1]}</text>'
                        )
                        last_label_week = w
                break
    p.append("</g>")

    # --- Gun etiketleri -----------------------------------------------------
    p.append(f'<g fill="{TEXT}">')
    for r, name in enumerate(WEEKDAYS):
        if not name:
            continue
        y = gy + r * step + cell * 0.82
        p.append(
            f'<text x="{pad:.1f}" y="{y:.1f}" xml:space="preserve">{name}</text>'
        )
    p.append("</g>")

    # --- Hucreler (capraz kayma animasyonu) --------------------------------
    for w in range(num_weeks):
        for r in range(7):
            day = weeks[w][r]
            if day is None:
                continue

            x = gx + w * step
            y = gy + r * step
            lvl = max(0, min(4, int(day.get("level", 0))))
            fill = LEVEL_COLORS[lvl]

            # Capraz (diagonal) gecikme: sol ustten sag alta dalga
            begin = (w * stagger) + (r * stagger * 0.6)

            title = (
                f'{day["count"]} contribution'
                f'{"s" if day["count"] != 1 else ""} on '
                f'{day["date"].strftime("%b %d, %Y")}'
            )

            # Baslangicta hafif asagi kaymis ve seffaf; sonra yerine oturur
            p.append(
                f'<rect x="{x:.1f}" y="{y:.1f}" width="{cell:.1f}" '
                f'height="{cell:.1f}" rx="{cell*0.18:.1f}" fill="{fill}" '
                f'opacity="0">'
                f'<title>{esc(title)}</title>'
                f'<animate attributeName="opacity" from="0" to="1" '
                f'begin="{begin:.2f}s" dur="0.45s" fill="freeze"/>'
                f'<animateTransform attributeName="transform" type="translate" '
                f'from="-6 -6" to="0 0" begin="{begin:.2f}s" dur="0.45s" '
                f'fill="freeze" calcMode="spline" keySplines="0.2 0 0.2 1"/>'
                f"</rect>"
            )

    # --- Alt bilgi: toplam + legend ----------------------------------------
    footer_y = gy + grid_h + cell * 2.0

    summary = f'{total} contributions in the last year'
    p.append(
        f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" '
        f'dur="0.5s" begin="{num_weeks*stagger + 0.3:.2f}s" fill="freeze"/>'
        f'<text x="{pad + left_label:.1f}" y="{footer_y:.1f}" fill="{TEXT}" '
        f'xml:space="preserve">{esc(summary)}</text></g>'
    )

    # Legend: Less [0][1][2][3][4] More
    lx = width - pad - (5 * (cell + gap) + cell * 4.2)
    ly = footer_y - cell
    p.append(
        f'<g opacity="0"><animate attributeName="opacity" from="0" to="1" '
        f'dur="0.5s" begin="{num_weeks*stagger + 0.3:.2f}s" fill="freeze"/>'
    )
    p.append(
        f'<text x="{lx - cell*3.2:.1f}" y="{footer_y:.1f}" fill="{TEXT}" '
        f'xml:space="preserve">Less</text>'
    )
    cx = lx
    for c in LEVEL_COLORS:
        p.append(
            f'<rect x="{cx:.1f}" y="{ly:.1f}" width="{cell:.1f}" '
            f'height="{cell:.1f}" rx="{cell*0.18:.1f}" fill="{c}"/>'
        )
        cx += cell + gap
    p.append(
        f'<text x="{cx + gap:.1f}" y="{footer_y:.1f}" fill="{TEXT}" '
        f'xml:space="preserve">More</text>'
    )
    p.append("</g>")

    p.append("</svg>")
    return "\n".join(p)


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Katki isi haritasini SVG olarak uret")
    ap.add_argument("--input", default=str(IN_JSON))
    ap.add_argument("--output", default=str(OUTPUT_SVG))
    ap.add_argument("--cell", type=float, default=11.0, help="Hucre boyutu (px)")
    ap.add_argument("--gap", type=float, default=2.6, help="Hucreler arasi bosluk (px)")
    ap.add_argument("--stagger", type=float, default=0.035, help="Kademeli gecikme (sn)")
    args = ap.parse_args()

    print("\n=== tugberkcem | render_heatmap_svg.py ===\n")

    in_path = Path(args.input)
    if not in_path.exists():
        die(
            "HATA: 'assets/data/contributions.json' bulunamadi!\n\n"
            "Once su komutu calistirin:\n"
            "    python scripts/fetch_contributions.py"
        )

    data = json.loads(in_path.read_text(encoding="utf-8"))
    days = data.get("days", [])
    total = int(data.get("total", 0))
    user = data.get("user", "tugberkcem")

    print(f"  Kullanici : {user}")
    print(f"  Gun sayisi: {len(days)}")

    weeks, first_sunday, num_weeks = build_grid(days)
    print(f"  Grid      : {num_weeks} hafta x 7 gun")

    svg = build_svg(
        weeks=weeks,
        total=total,
        cell=args.cell,
        gap=args.gap,
        stagger=args.stagger,
        user=user,
    )

    out = Path(args.output)
    out.write_text(svg, encoding="utf-8")
    print(f"  Cikti     : {out.name}  ({out.stat().st_size/1024:.1f} KB)")
    print("\n  Bitti!\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
