"""
Xếp video tải từ Flow vào đúng sản phẩm / đúng clip.

Cách dùng: thả TẤT CẢ file .mp4 tải từ Flow vào thư mục inbox/ (không cần đổi tên), rồi chạy:
    python tools/import_inbox.py

Tool nhận ra mã slot (ví dụ P07C03) trong tên file, vì mỗi prompt bắt đầu bằng mã đó nên Flow đặt tên file có chứa nó.
File được COPY sang products/<slug>/raw/C03.mp4, bản gốc chuyển vào inbox/_da_nhap/.
File không nhận ra mã: nằm lại trong inbox/ và được liệt kê; gán tay bằng:
    python tools/import_inbox.py --assign "tên file.mp4" P07C03
"""
import json
import re
import shutil
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
INBOX = ROOT / "inbox"
SLOT = re.compile(r"P(\d{2})C(\d{2})", re.I)


def probe(path: Path):
    try:
        out = subprocess.run(
            ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries", "stream=width,height,duration",
             "-show_entries", "format=duration", "-of", "json", str(path)],
            capture_output=True, text=True, timeout=30).stdout
        j = json.loads(out)
        s = j["streams"][0]
        dur = float(s.get("duration") or j["format"]["duration"])
        return int(s["width"]), int(s["height"]), dur
    except Exception:
        return None


def has_audio(path: Path) -> bool:
    out = subprocess.run(["ffprobe", "-v", "error", "-select_streams", "a:0", "-show_entries", "stream=codec_name",
                          "-of", "csv=p=0", str(path)], capture_output=True, text=True).stdout.strip()
    return bool(out)


def product_dir(pid: str):
    for d in (ROOT / "products").iterdir():
        if d.is_dir() and d.name.startswith(pid + "_"):
            return d
    return None


def place(src: Path, pid: str, nn: str) -> str:
    pdir = product_dir(pid)
    if not pdir:
        return f"khong co san pham id {pid}"
    info = probe(src)
    warn = []
    if info:
        w, h, dur = info
        if h <= w:
            warn.append(f"video NGANG {w}x{h} (can doc 9:16)")
        if not 5.5 <= dur <= 10.5:
            warn.append(f"do dai {dur:.1f}s la la (clip thuong 8s)")
    else:
        warn.append("khong doc duoc bang ffprobe")
    if not has_audio(src):
        warn.append("KHONG co am thanh")
    dst = pdir / "raw" / f"C{nn}.mp4"
    dst.parent.mkdir(exist_ok=True)
    existed = dst.exists()
    shutil.copy2(src, dst)
    done = INBOX / "_da_nhap"
    done.mkdir(exist_ok=True)
    shutil.move(str(src), str(done / src.name))
    return f"-> {pdir.name}/raw/{dst.name}" + (" (GHI DE ban cu)" if existed else "") + ("  CANH BAO: " + "; ".join(warn) if warn else "")


def main():
    INBOX.mkdir(exist_ok=True)
    if len(sys.argv) >= 4 and sys.argv[1] == "--assign":
        f = INBOX / sys.argv[2]
        m = SLOT.fullmatch(sys.argv[3])
        if not f.exists() or not m:
            print("Dung: --assign <ten file trong inbox> P07C03")
            return 2
        print(f.name, place(f, m.group(1), m.group(2)))
        return 0
    files = sorted([p for p in INBOX.iterdir() if p.is_file() and p.suffix.lower() in (".mp4", ".mov", ".webm")])
    if not files:
        print("inbox/ trong. Tha video tai tu Flow vao day roi chay lai.")
        return 0
    unmatched = []
    for f in files:
        m = SLOT.search(f.name)
        if m:
            print(f"{f.name[:60]:60s}", place(f, m.group(1), m.group(2)))
        else:
            unmatched.append(f)
    if unmatched:
        print("\nKHONG nhan ra ma slot (can gan tay):")
        for f in unmatched:
            info = probe(f)
            print(f"  {f.name}   {info if info else ''}")
        print('  python tools/import_inbox.py --assign "<ten file>" P07C03')
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
