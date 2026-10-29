"""
Kiểm tra chất lượng dữ liệu từng sản phẩm và cập nhật products.csv.

    python tools/validate.py            # kiểm tra tất cả, in bảng + danh sách lỗi
    python tools/validate.py 07         # chỉ sản phẩm 07
Ghi lại products.csv (trạng thái, mẫu đã chốt, giá, số clip, số nguồn) và tools/validation_report.md.
"""
import csv
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
BANNED = ["đỉnh cao", "đỉnh của chóp", "hoàn hảo", "số 1", "số một", "tốt nhất", "vô đối", "siêu phẩm", "thần thánh",
          "không thể bỏ qua", "bí mật", "bạn sẽ không tin", "chắc chắn", "cam kết", "đừng mua", "phí tiền", "áp đảo",
          "vượt trội", "sáng giá nhất", "hôm nay mình sẽ", "hãy cùng khám phá", "nâng tầm", "trải nghiệm tuyệt vời"]
SYMBOLS = re.compile(r"[%/~×—→]|[\U0001F300-\U0001FAFF]")
CLOSER = "no on-screen text"
CREDITS_PER_CLIP = 12


def check_product(pdir: Path):
    errs, warns = [], []
    rj, pj = pdir / "research.json", pdir / "prompts.json"
    info = {"status": "chua_lam", "model": "", "price": "", "clips": 0, "sources": 0}
    if not rj.exists() or not pj.exists():
        return info, ["thieu research.json hoac prompts.json"], warns
    try:
        res = json.loads(rj.read_text(encoding="utf-8"))
        pr = json.loads(pj.read_text(encoding="utf-8"))
    except Exception as e:
        return info, [f"JSON loi: {e}"], warns
    pid = pdir.name.split("_")[0]
    info.update(status=res.get("status", "?"), model=res.get("chosen_model", ""), sources=len(res.get("sources", [])))
    pv = res.get("price_vnd") or {}
    if pv.get("low"):
        info["price"] = f"{pv['low']:,}-{pv.get('high', pv['low']):,}".replace(",", ".")
    spec_ids = {s["id"]: s for s in res.get("specs", [])}
    src_ids = {s["id"] for s in res.get("sources", [])}
    for s in res.get("specs", []):
        if s.get("source") not in src_ids:
            errs.append(f"thong so {s['id']} tro toi nguon khong ton tai ({s.get('source')})")
    if not res.get("ref_image_candidates"):
        warns.append("khong co ref_image_candidates")
    product_only = pr.get("style") == "product-only"
    presenter = pr.get("presenter")
    if not product_only and presenter != "M":
        warns.append(f"nguoi dan {presenter}, quy uoc M")
    clips = pr.get("clips", [])
    info["clips"] = len(clips)
    if not 6 <= len(clips) <= 16:
        warns.append(f"so clip {len(clips)} ngoai khoang 6-16")
    seen_nums = {}
    for c in clips:
        n, code = c.get("n"), c.get("code", "")
        tag = f"clip {n}"
        if code != f"P{pid}C{int(n):02d}":
            errs.append(f"{tag}: ma slot sai ({code})")
        nar = c.get("narration_vi", "")
        words = len(nar.split())
        if words > 22:
            errs.append(f"{tag}: loi doc {words} tu (>22)")
        low = nar.lower()
        for b in BANNED:
            if b in low:
                errs.append(f"{tag}: tu cam '{b}'")
        if SYMBOLS.search(nar):
            warns.append(f"{tag}: ky hieu trong loi doc")
        if re.search(r"\d", nar):
            warns.append(f"{tag}: con chu so trong loi doc (nen viet bang chu)")
        for fid in c.get("facts_used", []):
            sp = spec_ids.get(fid)
            if not sp and fid == "price":
                if (res.get("price_vnd") or {}).get("confidence") not in ("cao", "vua"):
                    errs.append(f"{tag}: dung gia nhung do tin cay gia thap")
                continue
            if not sp:
                other = next((x for x in (res.get("strengths", []) + res.get("caveats", [])) if x.get("id") == fid), None)
                if other:
                    if other.get("source") not in src_ids:
                        errs.append(f"{tag}: {fid} tro toi nguon khong ton tai")
                    continue
            if not sp:
                errs.append(f"{tag}: facts_used {fid} khong co trong specs")
            elif sp.get("confidence") not in ("cao", "vua"):
                errs.append(f"{tag}: dung thong so {fid} do tin cay thap")
        fp = c.get("flow_prompt", "")
        if not fp.startswith((c.get("flow_code") or code) + "."):
            errs.append(f"{tag}: flow_prompt khong bat dau bang ma slot")
        if len(fp) > 1000:
            errs.append(f"{tag}: flow_prompt {len(fp)} ky tu (>1000)")
        if not product_only and CLOSER not in fp.lower():
            errs.append(f"{tag}: thieu cau ket 'No on-screen text...'")
        if nar and nar[:25] not in fp:
            errs.append(f"{tag}: flow_prompt khong chua loi doc")
        if not ("Vietnamese" in fp):
            warns.append(f"{tag}: prompt khong noi ro tieng Viet")
        for t in re.findall(r"\b[a-zA-ZÀ-ỹ]+\b", nar):
            pass
        seen_nums[n] = True
    if sorted(seen_nums) != list(range(1, len(clips) + 1)):
        errs.append("so thu tu clip khong lien tuc")
    return info, errs, warns


def main():
    ids = set(a for a in sys.argv[1:])
    rows = list(csv.DictReader(open(ROOT / "products.csv", encoding="utf-8-sig")))
    report = ["# Báo cáo kiểm tra\n"]
    total_clips = 0
    n_err = n_warn = 0
    for row in rows:
        if ids and row["id"] not in ids:
            continue
        pdir = ROOT / "products" / row["slug"]
        info, errs, warns = check_product(pdir)
        total_clips += info["clips"]
        n_err += len(errs)
        n_warn += len(warns)
        row["trang_thai"] = info["status"]
        if info["model"]:
            row["mau_da_chot"] = info["model"]
        row["gia_vn"] = info["price"]
        row["so_clip"] = info["clips"]
        row["so_nguon"] = info["sources"]
        row["credit"] = info["clips"] * CREDITS_PER_CLIP
        flag = "OK " if not errs else "LOI"
        print(f"{row['id']} {flag} {info['status']:14s} clip={info['clips']:2d} nguon={info['sources']:2d}  {info['model'][:55]}")
        report.append(f"## {row['id']} {info['model'] or row['mau_ung_vien']}  ({info['status']}, {info['clips']} clip)\n")
        for e in errs:
            report.append(f"- LỖI: {e}")
        for w in warns:
            report.append(f"- cảnh báo: {w}")
        report.append("")
    if not ids:
        fields = list(rows[0].keys())
        for extra in ("so_clip", "so_nguon", "credit"):
            if extra not in fields:
                fields.append(extra)
        with open(ROOT / "products.csv", "w", encoding="utf-8-sig", newline="") as f:
            w = csv.DictWriter(f, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    (ROOT / "tools" / "validation_report.md").write_text("\n".join(report), encoding="utf-8")
    months = total_clips * CREDITS_PER_CLIP / 1000
    print(f"\nTong: {total_clips} clip = {total_clips * CREDITS_PER_CLIP} credit = khoang {months:.1f} thang (1000 credit/thang). "
          f"Loi: {n_err}, canh bao: {n_warn}. Chi tiet: tools/validation_report.md")


if __name__ == "__main__":
    main()
