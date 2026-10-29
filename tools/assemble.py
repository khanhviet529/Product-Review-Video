"""
Ghép các clip đã xóa logo của một sản phẩm thành video hoàn chỉnh: final/<slug>.mp4

    python tools/assemble.py 07            # sản phẩm 07
    python tools/assemble.py --all         # mọi sản phẩm đủ clip
    python tools/assemble.py 07 --partial  # ghép dù thiếu clip

Mặc định chỉ ghép khi đủ mọi clip theo prompts.json. Chuẩn hóa 1080x1920, 30fps, H.264 + AAC, fade âm 25ms ở chỗ nối
để không bị tiếng lách, và chuẩn hóa độ lớn tiếng nói (loudnorm).
"""
import json
import subprocess
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
W, H, FPS = 1080, 1920, 30


def assemble(pdir: Path, partial: bool = False):
    pj = pdir / "prompts.json"
    if not pj.exists():
        return "chua co prompts.json"
    clips = json.loads(pj.read_text(encoding="utf-8"))["clips"]
    want = [f"C{c['n']:02d}.mp4" for c in clips]
    have = [pdir / "clean" / n for n in want if (pdir / "clean" / n).exists()]
    miss = [n for n in want if not (pdir / "clean" / n).exists()]
    if miss and not partial:
        return f"thieu {len(miss)}/{len(want)} clip: {', '.join(m[:3] for m in miss)}"
    if not have:
        return "chua co clip clean nao"
    (ROOT / "final").mkdir(exist_ok=True)
    out = ROOT / "final" / f"{pdir.name}.mp4"
    cmd = ["ffmpeg", "-y", "-v", "error"]
    for p in have:
        cmd += ["-i", str(p)]
    parts, ins = [], []
    for i in range(len(have)):
        parts.append(f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=decrease,pad={W}:{H}:(ow-iw)/2:(oh-ih)/2,setsar=1,fps={FPS},format=yuv420p[v{i}]")
        parts.append(f"[{i}:a]aresample=48000,afade=t=in:d=0.025,areverse,afade=t=in:d=0.025,areverse[a{i}]")
        ins.append(f"[v{i}][a{i}]")
    parts.append(f"{''.join(ins)}concat=n={len(have)}:v=1:a=1[v][a0]")
    parts.append("[a0]loudnorm=I=-16:TP=-1.5:LRA=11,aresample=48000[a]")
    cmd += ["-filter_complex", ";".join(parts), "-map", "[v]", "-map", "[a]",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", str(out)]
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        return "ffmpeg loi: " + r.stderr[-300:]
    return f"ok -> final/{out.name}  ({len(have)} clip)" + (f", thieu {len(miss)}" if miss else "")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    partial = "--partial" in sys.argv
    dirs = sorted(d for d in (ROOT / "products").iterdir() if d.is_dir())
    if "--all" not in sys.argv:
        dirs = [d for d in dirs if d.name.split("_")[0] in args]
    if not dirs:
        print("Dung: assemble.py <id...> | --all [--partial]")
        return 2
    for d in dirs:
        print(f"{d.name:45s} {assemble(d, partial)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
