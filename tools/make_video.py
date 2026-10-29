"""
Chạy TRỌN quy trình cho một sản phẩm: tạo clip trên Flow -> tải về -> nhập đúng chỗ -> xóa logo -> ghép video.

    python tools/make_video.py 24            # chỉ xem kế hoạch, KHÔNG tốn tín dụng
    python tools/make_video.py 24 --go       # chạy thật (tốn ~12 tín dụng mỗi clip)
    python tools/make_video.py 24 --go --max 3   # chỉ tạo 3 clip đầu (để thử)

Cần: Chrome đã mở bằng 0_mo_chrome_flow.bat và đã đăng nhập Google. Mọi bước đều chạy lại an toàn: clip đã có thì bỏ qua.
"""
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "tools"


def run(*args):
    print("\n$", " ".join(str(a) for a in args[1:]))
    r = subprocess.run([sys.executable, *map(str, args)], cwd=ROOT)
    if r.returncode != 0:
        sys.exit(f"Bước thất bại (mã {r.returncode}). Dừng.")


def main():
    if len(sys.argv) < 2:
        sys.exit(__doc__)
    pid, rest = sys.argv[1], sys.argv[2:]
    go = "--go" in rest
    if not go:
        run(T / "flow" / "run_product.py", pid)
        print("\n(Chỉ xem kế hoạch. Thêm --go để chạy thật.)")
        return
    run(T / "flow" / "run_product.py", pid, *rest)      # tạo + tải về inbox/
    run(T / "import_inbox.py")                          # xếp vào products/<id>/raw
    run(T / "clean_batch.py", pid)                      # xóa logo -> clean/
    run(T / "assemble.py", pid)                         # ghép -> final/
    run(T / "validate.py", pid)                         # cập nhật trạng thái
    print("\nXong. Video: final/ (xem thử trước khi đăng).")


if __name__ == "__main__":
    main()
