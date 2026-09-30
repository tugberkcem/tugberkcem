#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
setup.py  —  TEK KOMUTLA KURULUM
=================================
Bu betik, projeyi sifirdan ayaga kaldirir:

    1. .venv sanal ortamini olusturur (yoksa)
    2. Bagimliliklari kurar
    3. source-photo.jpg var mi diye bakar
    4. Varsa: foto hazirlama + ASCII SVG uretimi
    5. Her durumda: info-card.svg + contrib-heatmap.svg uretimi

Kullanim (proje kok dizininden):

    python scripts/setup.py

Sonra elde ettigin .venv'i aktive edip istedigin betigi tek tek
calistirabilirsin. Bu betik idempotenttir; birden fazla kez cagirmak zarar vermez.
"""

from __future__ import annotations

import os
import platform
import subprocess
import sys
import venv
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_DIR = ROOT / ".venv"
SCRIPTS = ROOT / "scripts"
REQUIREMENTS = SCRIPTS / "requirements.txt"

IS_WINDOWS = platform.system().lower().startswith("win")

# ANSI renkleri (desteklenmiyorsa sessizce yok sayilir)
C_OK = "\033[92m"
C_INFO = "\033[96m"
C_WARN = "\033[93m"
C_ERR = "\033[91m"
C_DIM = "\033[90m"
C_END = "\033[0m"


def say(color: str, msg: str) -> None:
    print(f"{color}{msg}{C_END}")


def banner() -> None:
    print()
    say(C_INFO, "=" * 62)
    say(C_INFO, "   tugberkcem  |  animated GitHub profile  |  kurulum")
    say(C_INFO, "=" * 62)
    print()


def venv_python() -> Path:
    if IS_WINDOWS:
        return VENV_DIR / "Scripts" / "python.exe"
    return VENV_DIR / "bin" / "python"


def run(cmd: list[str], desc: str, cwd: Path | None = None) -> bool:
    """Komutu calistir; basarisiz olursa False dondur (programi oldurme)."""
    say(C_DIM, f"   $ {' '.join(str(c) for c in cmd)}")
    try:
        subprocess.run(cmd, cwd=str(cwd or ROOT), check=True)
        return True
    except subprocess.CalledProcessError as exc:
        say(C_ERR, f"   [X] {desc} basarisiz oldu (cikis kodu {exc.returncode}).")
        return False
    except FileNotFoundError as exc:
        say(C_ERR, f"   [X] Komut bulunamadi: {exc}")
        return False


# --------------------------------------------------------------------------
def ensure_python_version() -> None:
    if sys.version_info < (3, 9):
        say(C_ERR, f"HATA: Python 3.9+ gerekiyor. Sende: {platform.python_version()}")
        raise SystemExit(1)
    say(C_OK, f"[OK] Python {platform.python_version()} uygun.")


def ensure_venv() -> Path:
    py = venv_python()
    if py.exists():
        say(C_OK, f"[OK] Sanal ortam hazir: {VENV_DIR}")
        return py

    say(C_INFO, "[..] Sanal ortam olusturuluyor (.venv)...")
    builder = venv.EnvBuilder(with_pip=True, clear=False)
    builder.create(str(VENV_DIR))
    say(C_OK, f"[OK] Sanal ortam olusturuldu: {VENV_DIR}")
    return venv_python()


def install_deps(py: Path) -> bool:
    if not REQUIREMENTS.exists():
        say(C_ERR, f"HATA: {REQUIREMENTS} bulunamadi.")
        return False

    say(C_INFO, "[..] Bagimliliklar kuruluyor (ilk seferde rembg modeli inebilir, sabir)...")
    ok = run([str(py), "-m", "pip", "install", "--upgrade", "pip"], "pip upgrade")
    if not ok:
        say(C_WARN, "[!] pip guncellenemedi, yine de devam ediliyor.")

    return run([str(py), "-m", "pip", "install", "-r", str(REQUIREMENTS)], "bagimlilik kurulumu")


def find_source_photo() -> Path | None:
    for name in ("source-photo.jpg", "source-photo.jpeg", "source-photo.png"):
        p = ROOT / name
        if p.exists():
            return p
    return None


def write_placeholder_ascii() -> None:
    """
    source-photo.jpg henuz yokken README'nin kirik resim gostermemesi icin
    gecici bir ASCII SVG yazar. Kullanici fotografi ekleyip prep_photo.py +
    make_ascii_svg.py calistirdiginda bu dosya gercek portreyle degisir.
    """
    out = ROOT / "avi-ascii.svg"
    if out.exists():
        return

    banner_txt = [
        "  _   _  _   _  ___ ___ ___ ___ _  __",
        " | |_| || | | || _ ) __| _ \\ __| |/ /",
        " |  _  || |_| || _ \\ _||   / _|| ' < ",
        " |_| |_| \\___/ |___/___|_|_\\___|_|\\_\\",
    ]
    fs = 14.0
    cw = fs * 0.60
    lh = fs * 1.5
    pad = 16.0
    w = max(len(l) for l in banner_txt) * cw + pad * 2
    h = len(banner_txt) * lh + pad * 2 + lh

    lines = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{w:.0f}" height="{h:.0f}" '
        f'viewBox="0 0 {w:.0f} {h:.0f}" font-family="ui-monospace, Menlo, Consolas, monospace" '
        f'font-size="{fs}">',
        f'<rect width="{w:.0f}" height="{h:.0f}" rx="8" fill="#0d1117" '
        f'stroke="#30363d"/>',
    ]
    for i, line in enumerate(banner_txt):
        y = pad + fs + i * lh
        lines.append(
            f'<text x="{pad:.1f}" y="{y:.1f}" fill="#00ff9c" xml:space="preserve">'
            f'{line}</text>'
        )
    y = pad + fs + len(banner_txt) * lh + lh * 0.2
    lines.append(
        f'<text x="{pad:.1f}" y="{y:.1f}" fill="#8b949e" xml:space="preserve">'
        f'// source-photo.jpg ekleyip scripts/setup.py calistir</text>'
    )
    lines.append("</svg>")

    out.write_text("\n".join(lines), encoding="utf-8")
    say(C_WARN, f"[!] Gecici placeholder olusturuldu: {out.name}")


def main() -> int:
    banner()

    ensure_python_version()
    py = ensure_venv()

    if not install_deps(py):
        say(C_ERR, "\nHATA: Bagimliliklar kurulamadi. Internet baglantini kontrol et.")
        return 1
    say(C_OK, "[OK] Bagimliliklar kuruldu.\n")

    # ---------------- Fotograf boru hatti ----------------
    photo = find_source_photo()
    if photo is None:
        say(C_WARN, "[!] 'source-photo.jpg' bulunamadi.")
        say(C_WARN, "    ASCII portre adimi ATLANIYOR.")
        say(C_WARN, "    Fotografini proje kok dizinine 'source-photo.jpg' adiyla")
        say(C_WARN, "    koyup sunlari calistir:")
        say(C_WARN, "        python scripts/prep_photo.py")
        say(C_WARN, "        python scripts/make_ascii_svg.py\n")
        write_placeholder_ascii()
    else:
        say(C_OK, f"[OK] Kaynak fotograf bulundu: {photo.name}")
        print()

        say(C_INFO, "[1/2] Fotograf hazirlaniyor (arka plan sil + CLAHE)...")
        if run([str(py), str(SCRIPTS / "prep_photo.py")], "prep_photo"):
            say(C_OK, "[OK] prep_photo tamam.")
            say(C_INFO, "[2/2] ASCII SVG uretiliyor...")
            if run([str(py), str(SCRIPTS / "make_ascii_svg.py")], "make_ascii_svg"):
                say(C_OK, "[OK] avi-ascii.svg olusturuldu.")
        print()

    # ---------------- Neofetch karti ----------------
    say(C_INFO, "[..] Neofetch bilgi karti uretiliyor...")
    if run([str(py), str(SCRIPTS / "make_info_card.py")], "make_info_card"):
        say(C_OK, "[OK] info-card.svg olusturuldu.")
    print()

    # ---------------- Isi haritasi ----------------
    say(C_INFO, "[..] GitHub katkilari cekiliyor...")
    if run([str(py), str(SCRIPTS / "fetch_contributions.py")], "fetch_contributions"):
        say(C_INFO, "[..] Isi haritasi ciziliyor...")
        if run([str(py), str(SCRIPTS / "render_heatmap_svg.py")], "render_heatmap_svg"):
            say(C_OK, "[OK] contrib-heatmap.svg olusturuldu.")
    print()

    # ---------------- Ozet ----------------
    say(C_INFO, "=" * 62)
    say(C_INFO, "   TAMAMLANDI — uretilen dosyalar")
    say(C_INFO, "=" * 62)

    produced = [
        ROOT / "avi-ascii.svg",
        ROOT / "info-card.svg",
        ROOT / "contrib-heatmap.svg",
    ]
    for f in produced:
        mark = f"{C_OK}[OK]{C_END}" if f.exists() else f"{C_WARN}[--]{C_END}"
        size = f"  ({f.stat().st_size/1024:.1f} KB)" if f.exists() else "  (uretilemedi)"
        print(f"   {mark} {f.name}{size}")

    print()
    say(C_DIM, "   Sirada ne var?")
    say(C_DIM, "     1. Uretilen SVG'leri tarayicida ac, animasyonlari kontrol et.")
    say(C_DIM, "     2. README.md zaten hazir.")
    say(C_DIM, "     3. git init && git add . && git commit -m '...' && git push")
    print()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
