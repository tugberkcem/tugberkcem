#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
prep_photo.py
=============
`source-photo.jpg` dosyasini alir, arka planini siler, kontrast/parlaklik
iyilestirmesi (CLAHE) uygular ve ASCII donusumu icin hazir, yuksek kontrastli
tek kanalli bir PNG uretir.

Cikti:
    assets/prep/portrait_cut.png   -> arka plani silinmis, seffaf PNG
    assets/prep/portrait_ascii.png -> ASCII icin hazirlanmis gri tonlamali PNG

Kullanim:
    python scripts/prep_photo.py
    python scripts/prep_photo.py --source source-photo.jpg --width 200
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import cv2
import numpy as np

# --------------------------------------------------------------------------
# Yollar
# --------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_SOURCE = ROOT / "source-photo.jpg"
PREP_DIR = ROOT / "assets" / "prep"

CUT_PATH = PREP_DIR / "portrait_cut.png"
ASCII_READY_PATH = PREP_DIR / "portrait_ascii.png"

# rembg'in destekledigi girdi formatlari
SUPPORTED_EXT = {".jpg", ".jpeg", ".png", ".webp", ".bmp", ".tif", ".tiff"}


# --------------------------------------------------------------------------
# Yardimcilar
# --------------------------------------------------------------------------
def find_source(explicit: str | None) -> Path:
    """Kaynak fotografi bul. Yoksa anlasilir bir hata ver."""
    if explicit:
        p = Path(explicit).expanduser().resolve()
        if not p.exists():
            _die(
                f"Belirtilen dosya bulunamadi: {p}\n"
                f"Lutfen gecerli bir yol verin."
            )
        return p

    if DEFAULT_SOURCE.exists():
        return DEFAULT_SOURCE

    # Kullanicinin isini kolaylastir: ayni isimde farkli uzantilari da ara
    for ext in SUPPORTED_EXT:
        candidate = ROOT / f"source-photo{ext}"
        if candidate.exists():
            return candidate

    _die(
        "HATA: 'source-photo.jpg' bulunamadi!\n\n"
        f"Beklenen konum : {DEFAULT_SOURCE}\n\n"
        "Yapmaniz gereken:\n"
        "  1. Vesikalik / portre fotografinizi proje ana klasorune kopyalayin\n"
        "  2. Adini tam olarak 'source-photo.jpg' yapin\n"
        "  3. Sonra tekrar calistirin:  python scripts/prep_photo.py\n\n"
        "Ipucu: Fotograf tercihen tek renkli (duz) bir arka plana sahip olsun."
    )


def _die(message: str) -> None:
    print("\n" + message + "\n", file=sys.stderr)
    sys.exit(1)


def load_bgr(path: Path) -> np.ndarray:
    """Unicode yollara ve TIFF/WebP gibi formatlara dayanikli okuma."""
    data = np.fromfile(str(path), dtype=np.uint8)  # non-ASCII path fix
    img = cv2.imdecode(data, cv2.IMREAD_COLOR)
    if img is None:
        _die(f"HATA: Goruntu okunamadi veya bozuk: {path}")
    return img


def imwrite_unicode(path: Path, img: np.ndarray) -> None:
    """
    cv2.imwrite, Turkce/Unicode karakter iceren Windows yollarinda SESSIZCE
    basarisiz olur (dosya hic olusmaz, hata da vermez). Bu yuzden once bellekte
    encode edip, sonra diske tofile() ile yaziyoruz.
    """
    path = Path(path)
    ext = path.suffix if path.suffix else ".png"
    ok, buf = cv2.imencode(ext, img)
    if not ok:
        _die(f"HATA: Goruntu kodlanamadi (uzanti: {ext}).")
    buf.tofile(str(path))


# --------------------------------------------------------------------------
# 1) Arka plan silme
# --------------------------------------------------------------------------
def remove_background(img_bgr: np.ndarray) -> np.ndarray:
    """
    rembg ile arka plani siler. rembg kurulu degilse veya model indirilemezse
    GrabCut tabanli yedek (fallback) algoritmaya duser; boylece akis asla kirilmaz.

    Donen: BGRA (4 kanal) goruntu
    """
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)

    try:
        from rembg import remove  # type: ignore

        print("  [1/4] rembg ile arka plan siliniyor (ilk calismada model inebilir)...")
        cut_rgba = remove(rgb)  # numpy array in -> PIL/np out
        cut_rgba = np.array(cut_rgba.convert("RGBA"))
        return cv2.cvtColor(cut_rgba, cv2.COLOR_RGBA2BGRA)

    except Exception as exc:  # noqa: BLE001
        print(f"  [!] rembg kullanilamadi ({exc.__class__.__name__}).")
        print("  [1/4] GrabCut yedek algoritmasi ile arka plan siliniyor...")
        return _grabcut_fallback(img_bgr)


def _grabcut_fallback(img_bgr: np.ndarray) -> np.ndarray:
    """
    rembg olmadan, kaba ama is goren arka plan silme.
    Kenarlardan 8%'lik cerceveyi 'kesin arka plan' varsayar, merkezi 'muhtemel on plan'.
    """
    h, w = img_bgr.shape[:2]
    mask = np.zeros((h, w), np.uint8)

    mx, my = int(w * 0.08), int(h * 0.08)
    rect = (mx, my, w - 2 * mx, h - 2 * my)

    bgd = np.zeros((1, 65), np.float64)
    fgd = np.zeros((1, 65), np.float64)

    cv2.grabCut(img_bgr, mask, rect, bgd, fgd, 5, cv2.GC_INIT_WITH_RECT)
    fg_mask = np.where((mask == cv2.GC_FGD) | (mask == cv2.GC_PR_FGD), 255, 0).astype(np.uint8)

    # Kenar yumusatma: sac kenarlarindaki testere dislerini temizler
    fg_mask = cv2.GaussianBlur(fg_mask, (5, 5), 0)

    b, g, r = cv2.split(img_bgr)
    return cv2.merge([b, g, r, fg_mask])


# --------------------------------------------------------------------------
# 2) Kirpma + kare alma
# --------------------------------------------------------------------------
def crop_to_subject(img_bgra: np.ndarray, margin: float = 0.04) -> np.ndarray:
    """Seffaf olmayan piksellerin sinir kutusuna gore kirpar."""
    alpha = img_bgra[:, :, 3]
    ys, xs = np.where(alpha > 12)
    if len(xs) == 0:
        return img_bgra

    x0, x1 = xs.min(), xs.max()
    y0, y1 = ys.min(), ys.max()

    pad_x = int((x1 - x0) * margin)
    pad_y = int((y1 - y0) * margin)

    x0 = max(0, x0 - pad_x)
    y0 = max(0, y0 - pad_y)
    x1 = min(img_bgra.shape[1] - 1, x1 + pad_x)
    y1 = min(img_bgra.shape[0] - 1, y1 + pad_y)

    return img_bgra[y0:y1 + 1, x0:x1 + 1]


# --------------------------------------------------------------------------
# 3) CLAHE kontrast
# --------------------------------------------------------------------------
def crop_upper_body(img_bgra: np.ndarray, keep_top: float) -> np.ndarray:
    """
    Portre gorunumu icin konunun ust kismini tutar.

    keep_top = 1.0 -> hicbir sey yapmaz (tam boy)
    keep_top = 0.62 -> bas + omuz + gogus (onerilen)

    Neden: boydan veya uzun bir fotograf ASCII'ye cevrilince portre, yanindaki
    bilgi kartina gore asiri uzun kaliyor. Bas-omuz kirpmasi hem daha okunur
    bir yuz saglar hem de iki blogu gorsel olarak dengeler.
    """
    if keep_top >= 0.999:
        return img_bgra

    keep_top = max(0.30, min(1.0, keep_top))

    # Kirpma sonrasi seffaf alanlari da kirp ki bos siyah serit kalmasin
    h = img_bgra.shape[0]
    cut = img_bgra[: max(1, int(h * keep_top)), :, :]
    return crop_to_subject(cut, margin=0.02)


def apply_clahe(img_bgra: np.ndarray, clip: float = 2.4, grid: int = 8) -> np.ndarray:
    """
    Luminance (LAB'in L kanali) uzerinde CLAHE uygular.
    Boylece golgelerdeki yuz detaylari ASCII'de kaybolmaz, renkler bozulmaz.
    """
    bgr = img_bgra[:, :, :3]
    alpha = img_bgra[:, :, 3]

    lab = cv2.cvtColor(bgr, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)

    clahe = cv2.createCLAHE(clipLimit=clip, tileGridSize=(grid, grid))
    l_eq = clahe.apply(l)

    merged = cv2.merge([l_eq, a, b])
    out_bgr = cv2.cvtColor(merged, cv2.COLOR_LAB2BGR)

    return cv2.merge([out_bgr[:, :, 0], out_bgr[:, :, 1], out_bgr[:, :, 2], alpha])


# --------------------------------------------------------------------------
# 4) Arka plani duz siyaha cevir + gri tonlama
# --------------------------------------------------------------------------
def flatten_on_black(img_bgra: np.ndarray) -> np.ndarray:
    """Seffaf alani siyahla doldurup 3 kanalli BGR dondurur."""
    alpha = (img_bgra[:, :, 3:4].astype(np.float32)) / 255.0
    bgr = img_bgra[:, :, :3].astype(np.float32)
    flat = bgr * alpha  # siyah (0,0,0) zemin uzerine alpha-blend
    return flat.astype(np.uint8)


def to_ascii_ready(bgr: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    ASCII donusumu icin:
      - gri tonlama
      - yuzu one cikaran gamma
      - normalize (kontrasti min-max ile tam acma)

    Donen: (gri_img, alpha_olcekli_gri)  -> ikincisi siluet olusturmak icin
    """
    gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)

    # Gamma < 1 -> koyu bolgeleri aydinlatir (sac/yuz golgeleri)
    inv_gamma = 1.0 / 1.25
    lut = ((np.arange(256) / 255.0) ** inv_gamma * 255.0).astype(np.uint8)
    gray = cv2.LUT(gray, lut)

    # Yerel kontrast
    gray = cv2.normalize(gray, None, 0, 255, cv2.NORM_MINMAX)

    # Hafif yumusatma -> ASCII'de tek piksel gurultusunu engeller
    gray = cv2.medianBlur(gray, 3)

    return gray, gray


# --------------------------------------------------------------------------
# main
# --------------------------------------------------------------------------
def main() -> int:
    ap = argparse.ArgumentParser(description="GitHub profil ASCII portresi icin foto hazirlama")
    ap.add_argument("--source", default=None, help="Kaynak fotograf yolu (varsayilan: source-photo.jpg)")
    ap.add_argument("--width", type=int, default=200, help="ASCII icin hedef genislik (px)")
    ap.add_argument("--clahe", type=float, default=2.4, help="CLAHE clip limit")
    ap.add_argument(
        "--keep-top",
        type=float,
        default=0.62,
        help="Konunun ust yuzdesini tut (1.0 = tam boy, 0.62 = bas-omuz)",
    )
    args = ap.parse_args()

    print("\n=== tugberkcem | prep_photo.py ===\n")

    src = find_source(args.source)
    print(f"  Kaynak : {src}")

    img = load_bgr(src)
    print(f"  Boyut  : {img.shape[1]}x{img.shape[0]} px")

    PREP_DIR.mkdir(parents=True, exist_ok=True)

    # 1. Arka plan
    cut = remove_background(img)

    # 2. Kirp
    cut = crop_to_subject(cut)
    cut = crop_upper_body(cut, keep_top=args.keep_top)
    print(f"  [2/4] Konuya kirpildi -> {cut.shape[1]}x{cut.shape[0]} px")

    # 3. CLAHE
    cut = apply_clahe(cut, clip=args.clahe)
    print("  [3/4] CLAHE kontrast uygulandi")

    # Seffaf PNG'yi kaydet (istedigin zaman yeniden kullanabilirsin)
    imwrite_unicode(CUT_PATH, cut)

    # 4. ASCII icin hazirla
    flat = flatten_on_black(cut)
    gray, _ = to_ascii_ready(flat)

    # Hedef genislige olceklendir (oran korunur)
    target_w = max(60, args.width)
    scale = target_w / gray.shape[1]
    target_h = max(1, int(gray.shape[0] * scale))
    gray = cv2.resize(gray, (target_w, target_h), interpolation=cv2.INTER_AREA)

    imwrite_unicode(ASCII_READY_PATH, gray)
    print(f"  [4/4] ASCII kaynagi hazir -> {ASCII_READY_PATH.name} ({target_w}x{target_h})")

    print("\n  Bitti! Simdi calistir:  python scripts/make_ascii_svg.py\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
