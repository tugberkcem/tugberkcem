#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fetch_contributions.py
======================
GitHub'in PUBLIC katki takvimini (contribution graph) herhangi bir token
GEREKTIRMEDEN HTML uzerinden parse eder ve JSON olarak kaydeder.

Neden HTML scraping?
    GitHub REST/GraphQL API'si kisisel katki takvimi icin token ister.
    Public profil sayfasinda ise takvim zaten gomulu gelir:
        https://github.com/users/<user>/contributions
    Bu uc, kimlik dogrulama istemez ve makinede okunabilir HTML dondurur.

Cikti:
    assets/data/contributions.json
    {
      "user": "tugberkcem",
      "fetched_at": "2026-...",
      "total": 1234,
      "days": [ {"date": "2026-01-01", "count": 3, "level": 2}, ... ]
    }

Kullanim:
    python scripts/fetch_contributions.py
    python scripts/fetch_contributions.py --user tugberkcem
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import re
import sys
import time
from pathlib import Path

import requests
from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "assets" / "data"
OUT_JSON = DATA_DIR / "contributions.json"

DEFAULT_USER = "tugberkcem"

# GitHub kendi sayfasini bu User-Agent ile servis ediyor; bos UA -> 404 riski
HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}


def die(msg: str) -> None:
    print("\n" + msg + "\n", file=sys.stderr)
    raise SystemExit(1)


# --------------------------------------------------------------------------
# 1) HTML cekme (retry'li)
# --------------------------------------------------------------------------
def fetch_html(user: str, retries: int = 4) -> str:
    # Bu uc, fragment olarak gomulu takvimi dondurur (auth gerektirmez)
    url = f"https://github.com/users/{user}/contributions"

    last_exc: Exception | None = None
    for attempt in range(1, retries + 1):
        try:
            print(f"  [1/3] Katki HTML'i cekiliyor (deneme {attempt}/{retries})...")
            r = requests.get(url, headers=HEADERS, timeout=30)
            if r.status_code == 200 and (
                "ContributionCalendar" in r.text or 'data-date="' in r.text
            ):
                return r.text
            if r.status_code == 404:
                die(
                    f"HATA: '{user}' kullanicisi bulunamadi (HTTP 404).\n"
                    "Kullanici adini kontrol edin."
                )
            # 429 / 5xx -> bekle ve tekrar dene
            wait = 2 ** attempt
            print(f"      [!] HTTP {r.status_code}, {wait}s bekleyip tekrar deniyorum...")
            time.sleep(wait)
            last_exc = RuntimeError(f"HTTP {r.status_code}")
        except requests.RequestException as exc:  # noqa: PERF203
            last_exc = exc
            wait = 2 ** attempt
            print(f"      [!] Ag hatasi ({exc.__class__.__name__}), {wait}s bekleniyor...")
            time.sleep(wait)

    die(
        "HATA: Katki takvimi cekilemedi.\n"
        f"Son hata: {last_exc}\n\n"
        "Olasi nedenler: internet baglantisi yok, GitHub gecici olarak yanit vermiyor\n"
        "veya kullanici adi yanlis."
    )


# --------------------------------------------------------------------------
# 2) Parse
# --------------------------------------------------------------------------
def parse_level_from_class(class_attr: str) -> int:
    """'... contribution-details ... ' class'larindan seviye (0-4) cikarir."""
    m = re.search(r"level--?(\d+)", class_attr)
    if m:
        return int(m.group(1))
    m = re.search(r"\blevel-(\d)\b", class_attr)
    if m:
        return int(m.group(1))
    return 0


def parse_contributions(html_text: str) -> dict:
    soup = BeautifulSoup(html_text, "html.parser")

    # Bazi surumlerde <td data-date=... data-level=...>, bazilarinda
    # <rect data-date=... data-level=...> geliyor. Ikisini de destekle.
    cells = soup.select("td.ContributionCalendar-day")
    if not cells:
        cells = soup.find_all(attrs={"data-date": True})

    if not cells:
        die(
            "HATA: HTML icinde katki hucreleri bulunamadi.\n"
            "GitHub sayfa yapisini degistirmis olabilir. "
            "Yedek olarak 'fetch_contributions.py' icindeki secicileri guncelleyin."
        )

    days: list[dict] = []
    for c in cells:
        date = c.get("data-date")
        if not date:
            continue

        level_attr = c.get("data-level")
        if level_attr is not None and str(level_attr).strip() != "":
            level = int(level_attr)
        else:
            level = parse_level_from_class(" ".join(c.get("class", [])))

        # Sayi (tooltip / aria-label icinden)
        count = 0
        aria = c.get("aria-label") or ""
        tooltip = c.get("data-tooltip") if hasattr(c, "get") else None
        text_blob = " ".join(filter(None, [aria, c.get("title"), tooltip]))

        m = re.search(r"(\d[\d,]*)\s+contribution", text_blob)
        if m:
            count = int(m.group(1).replace(",", ""))
        elif level > 0:
            count = level  # kaba tahmin; toplam icin asagidaki gercek toplam kullanilir

        days.append({"date": date, "count": count, "level": level})

    days.sort(key=lambda d: d["date"])

    # Toplam: sayfadaki basliktan ("1,234 contributions in the last year")
    total = 0
    heading = soup.find(string=re.compile(r"contribution", re.I))
    m = re.search(r"([\d,]+)\s+contribution", str(heading) if heading else "")
    if m:
        total = int(m.group(1).replace(",", ""))
    if total == 0:
        total = sum(d["count"] for d in days)

    return {
        "user": "",
        "fetched_at": dt.datetime.now().astimezone().isoformat(timespec="seconds"),
        "total": total,
        "days": days,
    }


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="Public GitHub katkilarini JSON'a cek")
    ap.add_argument("--user", default=DEFAULT_USER)
    ap.add_argument("--output", default=str(OUT_JSON))
    args = ap.parse_args()

    print("\n=== tugberkcem | fetch_contributions.py ===\n")

    html_text = fetch_html(args.user)
    print("  [2/3] HTML parse ediliyor...")
    data = parse_contributions(html_text)
    data["user"] = args.user

    if not data["days"]:
        die("HATA: Hicbir katki gunu parse edilemedi.")

    out = Path(args.output)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

    print(
        f"  [3/3] Kaydedildi: {out}  "
        f"({len(data['days'])} gun, toplam {data['total']} katki)"
    )
    print("\n  Bitti! Simdi:  python scripts/render_heatmap_svg.py\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
