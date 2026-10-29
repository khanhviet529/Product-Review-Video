"""
Xóa logo hàng loạt: products/<slug>/raw/Cnn.mp4 -> products/<slug>/clean/Cnn.mp4

    python tools/clean_batch.py            # mọi clip chưa có bản clean
    python tools/clean_batch.py 07 12      # chỉ sản phẩm 07 và 12
    python tools/clean_batch.py --force    # làm lại cả clip đã có

Dùng tool xóa logo trong tools/logo_remover (Reverse Alpha Blending + inpaint dải viền, giữ nguyên âm thanh).
"""
import sys
import time
import traceback
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "tools" / "logo_remover"))
from watermark_remover import VideoWatermarkRemover  # noqa: E402


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    force = "--force" in sys.argv
    jobs = []
    for d in sorted((ROOT / "products").iterdir()):
        if not d.is_dir() or (args and d.name.split("_")[0] not in args):
            continue
        for raw in sorted((d / "raw").glob("C*.mp4")):
            out = d / "clean" / raw.name
            if force or not out.exists():
                jobs.append((raw, out))
    if not jobs:
        print("Khong co clip nao can xu ly.")
        return 0
    print(f"{len(jobs)} clip can xoa logo")
    ok = fail = 0
    for i, (raw, out) in enumerate(jobs, 1):
        out.parent.mkdir(exist_ok=True)
        t0 = time.time()
        try:
            r = VideoWatermarkRemover(str(raw), output_path=str(out))
            if r.alpha is None:
                print(f"  CANH BAO {raw.name}: khong dung duoc alpha map (kich thuoc {r.width}x{r.height}), dung che do du phong")
            r.process()
            print(f"[{i}/{len(jobs)}] {raw.parent.parent.name}/{raw.name}  {time.time() - t0:.1f}s")
            ok += 1
        except Exception:
            print(f"[{i}/{len(jobs)}] LOI {raw}")
            traceback.print_exc()
            fail += 1
    print(f"\nXong: {ok} clip, loi: {fail}")
    return 1 if fail else 0


if __name__ == "__main__":
    raise SystemExit(main())
