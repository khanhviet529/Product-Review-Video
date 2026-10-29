"""
Tìm và tải ảnh tham chiếu sản phẩm vào products/<slug>/ref_images/.

Nguồn ảnh (chỉ từ nguồn chính hãng / cửa hàng lớn mà bước xác minh đã ghi trong research.json):
  1. ref_image_candidates[].url         ảnh trực tiếp do bước xác minh tìm được
  2. official_page + các nguồn loại chinh_hang / cua_hang: tự đọc HTML, lấy og:image, twitter:image,
     JSON-LD "image" và các thẻ <img>/srcset lớn

Ảnh được kiểm tra (đủ lớn, đọc được), bỏ trùng, chuẩn hóa về JPG (cạnh dài <= 2000px), đặt tên:
    product_main.jpg, product_angle_1.jpg, in_use_1.jpg ...  và ghi ref_images/_sources.json (URL gốc, trang, kích thước).

Dùng:
    python tools/find_images.py            # tất cả sản phẩm
    python tools/find_images.py 07 12      # chỉ sản phẩm id 07 và 12
"""
import hashlib
import json
import re
import sys
import urllib.parse
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import cv2
import numpy as np

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) "
      "Chrome/124.0 Safari/537.36")
MIN_SIDE = 500
MAX_SIDE = 2000


def http_get(url: str, timeout: int = 20, referer: str = ""):
    req = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "*/*", **({"Referer": referer} if referer else {})})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read(), r.headers.get("Content-Type", "")


def page_images(page_url: str, strict: bool = False):
    """Lấy URL ảnh ứng viên từ một trang sản phẩm. strict=True: chỉ ảnh đại diện của chính sản phẩm (og:image, JSON-LD)."""
    try:
        data, ctype = http_get(page_url)
    except Exception:
        return []
    html = data.decode("utf-8", errors="ignore")
    urls = []
    for m in re.finditer(r'<meta[^>]+(?:property|name)=["\'](?:og:image(?::secure_url)?|twitter:image(?::src)?)["\'][^>]*content=["\']([^"\']+)', html, re.I):
        urls.append(m.group(1))
    for m in re.finditer(r'<meta[^>]+content=["\']([^"\']+)["\'][^>]+(?:property|name)=["\'](?:og:image|twitter:image)["\']', html, re.I):
        urls.append(m.group(1))
    for m in re.finditer(r'<script[^>]+application/ld\+json[^>]*>(.*?)</script>', html, re.I | re.S):
        try:
            blob = json.loads(m.group(1))
        except Exception:
            continue
        stack = [blob]
        while stack:
            x = stack.pop()
            if isinstance(x, dict):
                for k, v in x.items():
                    if k == "image":
                        vs = v if isinstance(v, list) else [v]
                        for it in vs:
                            urls.append(it.get("url") if isinstance(it, dict) else it)
                    else:
                        stack.append(v)
            elif isinstance(x, list):
                stack.extend(x)
    # ảnh lớn trong HTML (srcset ưu tiên bản lớn nhất); bỏ qua khi strict vì dễ lẫn sản phẩm gợi ý/quảng cáo
    for m in ([] if strict else re.finditer(r'srcset=["\']([^"\']+)["\']', html, re.I)):
        parts = [p.strip().split(" ")[0] for p in m.group(1).split(",") if p.strip()]
        if parts:
            urls.append(parts[-1])
    for m in ([] if strict else re.finditer(r'<img[^>]+(?:data-src|data-original|src)=["\']([^"\']+\.(?:jpg|jpeg|png|webp)[^"\']*)["\']', html, re.I)):
        urls.append(m.group(1))
    out, seen = [], set()
    for u in urls:
        if not u or not isinstance(u, str) or u.startswith("data:"):
            continue
        u = urllib.parse.urljoin(page_url, u.replace("&amp;", "&"))
        if re.search(r"(logo|icon|sprite|favicon|avatar|banner|placeholder|loading|\.svg)", u, re.I):
            continue
        if u not in seen:
            seen.add(u)
            out.append(u)
    return out[:40]


def fetch_image(url: str, referer: str = ""):
    """Tải ảnh, trả (mảng BGR, sha1) hoặc None nếu không hợp lệ."""
    try:
        data, ctype = http_get(url, referer=referer)
    except Exception:
        return None
    if len(data) < 8_000:
        return None
    img = cv2.imdecode(np.frombuffer(data, np.uint8), cv2.IMREAD_COLOR)
    if img is None:
        return None
    h, w = img.shape[:2]
    if min(h, w) < MIN_SIDE:
        return None
    return img, hashlib.sha1(data).hexdigest()


def process_product(pdir: Path):
    rj = pdir / "research.json"
    if not rj.exists():
        return pdir.name, 0, "chua co research.json"
    res = json.loads(rj.read_text(encoding="utf-8"))
    cands = []        # (url, kind, page)
    for c in res.get("ref_image_candidates", []) or []:
        if c.get("url"):
            cands.append((c["url"], c.get("kind", "product_angle"), c.get("page", "")))
    pages = []
    if res.get("official_page"):
        pages.append(res["official_page"])
    for s in res.get("sources", []) or []:
        if s.get("type") in ("chinh_hang", "cua_hang") and s.get("url"):
            pages.append(s["url"])
    official = res.get("official_page")
    for pg in dict.fromkeys(pages):
        for u in page_images(pg, strict=(pg != official)):
            cands.append((u, "product_angle", pg))

    out_dir = pdir / "ref_images"
    out_dir.mkdir(exist_ok=True)
    for old in out_dir.glob("*"):
        if old.is_file():
            old.unlink()

    saved, seen, counters, meta = [], set(), {}, []
    for url, kind, page in cands:
        got = fetch_image(url, referer=page)
        if not got:
            continue
        img, sha = got
        if sha in seen:
            continue
        seen.add(sha)
        h, w = img.shape[:2]
        scale = MAX_SIDE / max(h, w)
        if scale < 1:
            img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_AREA)
        counters[kind] = counters.get(kind, 0) + 1
        name = "product_main.jpg" if kind == "product_main" and counters[kind] == 1 else f"{kind}_{counters[kind]}.jpg"
        ok, buf = cv2.imencode(".jpg", img, [cv2.IMWRITE_JPEG_QUALITY, 92])
        (out_dir / name).write_bytes(buf.tobytes())
        meta.append({"file": name, "url": url, "page": page, "kind": kind, "width": w, "height": h})
        saved.append(name)
        if len(saved) >= 10:
            break
    # nếu chưa có product_main thì lấy ảnh lớn nhất làm ảnh chính
    if saved and "product_main.jpg" not in saved:
        best = max(meta, key=lambda m: m["width"] * m["height"])
        src = out_dir / best["file"]
        (out_dir / "product_main.jpg").write_bytes(src.read_bytes())
        meta.append({**best, "file": "product_main.jpg", "kind": "product_main", "note": "ảnh lớn nhất được chọn làm ảnh chính"})
    (out_dir / "_sources.json").write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")
    if saved:
        repick_main(pdir)
    return pdir.name, len(saved), "ok" if saved else "khong tai duoc anh nao (xem ref_image_candidates, tu luu tay)"


def clean_score(img) -> float:
    """Điểm 'ảnh sản phẩm sạch': nền đồng nhất, ít chữ/banner, tỉ lệ khung không quá dẹt."""
    h, w = img.shape[:2]
    s = 400 / max(h, w)
    g = cv2.cvtColor(cv2.resize(img, (max(1, int(w * s)), max(1, int(h * s)))), cv2.COLOR_BGR2GRAY)
    gh, gw = g.shape
    b = max(4, int(0.08 * min(gh, gw)))
    border = np.concatenate([g[:b].ravel(), g[-b:].ravel(), g[:, :b].ravel(), g[:, -b:].ravel()])
    uniform = 1.0 / (1.0 + float(border.std()) / 18.0)
    density = float((cv2.Canny(g, 80, 160) > 0).mean())
    ar = w / h
    pen = 0.0 if 0.6 <= ar <= 1.7 else 0.6
    # vật thể: tỉ lệ pixel khác màu nền (màu trung vị của viền); ảnh rỗng hoặc phủ kín khung đều bị loại
    bg = float(np.median(border))
    cover = float((np.abs(g.astype(np.float32) - bg) > 28).mean())
    if cover < 0.10 or cover > 0.80:
        return -9.0
    # vật thể nằm giữa khung (không bị cắt ở mép) và nhìn từ chính diện/góc 3/4 thì chiếm diện tích vừa phải
    mask = (np.abs(g.astype(np.float32) - bg) > 28)
    ys, xs = np.where(mask)
    bw, bh = (xs.max() - xs.min()) / gw, (ys.max() - ys.min()) / gh
    shape_pen = 0.0 if bh > 0.30 and bw > 0.30 else 0.5      # loại ảnh nhìn nghiêng/dẹt quá (chỉ còn một vạch mỏng)
    return uniform - 6.0 * density - pen - shape_pen + 0.4 * min(cover, 0.45)


def repick_main(pdir: Path):
    """Chọn lại product_main.jpg trong số ảnh đã tải (không tải lại)."""
    d = pdir / "ref_images"
    files = [f for f in sorted(d.glob("*.jpg")) if f.name != "product_main.jpg"]
    best, best_s = None, -9
    try:
        meta = {m["file"]: m for m in json.loads((d / "_sources.json").read_text(encoding="utf-8"))}
    except Exception:
        meta = {}
    bad = re.compile(r"(tiktok|facebook|zalo|youtube|instagram|share|badge|payment|qr|banner|logo|icon)", re.I)
    for f in files:
        if bad.search(meta.get(f.name, {}).get("url", "")):
            continue
        img = cv2.imdecode(np.fromfile(str(f), np.uint8), cv2.IMREAD_COLOR)
        if img is None:
            continue
        sc = clean_score(img)
        if sc > best_s:
            best, best_s = f, sc
    if best:
        (d / "product_main.jpg").write_bytes(best.read_bytes())
        return pdir.name, best.name, round(best_s, 2)
    return pdir.name, None, 0


def main():
    if "--repick" in sys.argv:
        for d in sorted(x for x in (ROOT / "products").iterdir() if x.is_dir() and (x / "ref_images").exists()):
            print(*repick_main(d))
        return
    ids = set(sys.argv[1:])
    dirs = sorted(d for d in (ROOT / "products").iterdir() if d.is_dir() and (not ids or d.name.split("_")[0] in ids))
    with ThreadPoolExecutor(max_workers=6) as ex:
        for name, n, note in ex.map(process_product, dirs):
            print(f"{name:45s} {n:2d} anh  {note}")


if __name__ == "__main__":
    main()
