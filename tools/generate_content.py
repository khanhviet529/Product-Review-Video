"""
Goi Gemini CLI (agy) de tao research.json va script.json cho mot san pham.
Sau do tu dong chay build_scripts.py (prompts.json/md) va find_images.py (tai anh tham chieu).

    python tools/generate_content.py 01              # chi sinh research.json + script.json
    python tools/generate_content.py 01 --all-steps  # sinh + build prompts + tai anh + bang
    python tools/generate_content.py --batch 01 02 03 --all-steps   # nhieu san pham
    python tools/generate_content.py --todo --all-steps             # moi san pham chua co noi dung

Yeu cau: Antigravity CLI (agy) da cai, da dang nhap (goi `agy` chay duoc trong terminal).
agy chay headless trong sandbox tam gom: tools/SPEC.md, tools/SPEC2.md, characters/presenters.md,
va thong tin san pham tu products.csv.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent
T = ROOT / "tools"

# ------------------------------------------------------------------
# Tim agy
# ------------------------------------------------------------------

def find_agy():
    """Tim duong dan toi agy.exe (uu tien: bien moi truong > LOCALAPPDATA > which)."""
    cands = [
        os.environ.get("AGY_BIN"),
        os.path.join(os.environ.get("LOCALAPPDATA", ""), "agy", "bin", "agy.exe"),
        os.path.join(os.path.expanduser("~"), ".local", "bin", "agy"),
    ]
    for c in cands:
        if c and Path(c).exists():
            return c
    cmd = "where" if sys.platform == "win32" else "which"
    r = subprocess.run([cmd, "agy"], capture_output=True, text=True)
    if r.returncode == 0:
        hit = r.stdout.strip().splitlines()[0].strip()
        if hit:
            return hit
    return None


# ------------------------------------------------------------------
# Doc products.csv
# ------------------------------------------------------------------

def load_csv():
    import csv
    rows = {}
    with open(ROOT / "products.csv", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            rows[row["id"]] = row
    return rows


# ------------------------------------------------------------------
# Tao sandbox cho agy (headless)
# ------------------------------------------------------------------

TASK_TMPL = """# Thong tin san pham can xu ly

Thu muc san pham: `D:\\Project\\Product Review Video\\products\\{slug}\\`
(Da co brief.md mau, ref_images/, raw/, clean/ trong thu muc do)

CSV row:
```
{csv_info}
```

Nhiem vu cua ban (doc SPEC.md va SPEC2.md de biet chi tiet):
1. Buoc A-D (SPEC.md): WebSearch/WebFetch chot mau, lay thong so, gia, anh tham chieu.
2. Ghi file `research.json` vao thu muc san pham theo schema SPEC.md muc 2.
3. Buoc E-F (SPEC2.md V2): viet thesis, answer_short, 10-13 clip (moi clip 8 giay).
4. Ghi file `script.json` vao thu muc san pham theo schema SPEC2.md muc 7.
5. In bao cao ngan <= 8 dong: mau chot, gia, so clip, trang thai, van de con lai.

Chi ghi vao thu muc san pham cua ban. KHONG sua products.csv hay file nao khac.
"""

AGY_PROMPT = (
    "Doc SPEC.md, SPEC2.md, presenters.md va product_info.md trong thu muc lam viec. "
    "Thuc hien SPEC.md Buoc A-D (nghien cuu, nguon, anh tham chieu) "
    "roi SPEC2.md muc 3 (tuyen noi dung V2, 10-13 clip). "
    "Ghi research.json va script.json vao thu muc san pham neu trong product_info.md. "
    "In bao cao ngan (mau chot, gia, so clip, trang thai, van de con lai)."
)


def make_sandbox(pid, csv_row):
    d = tempfile.mkdtemp(prefix="agy-review-{}-".format(pid))
    shutil.copy(T / "SPEC.md", d)
    shutil.copy(T / "SPEC2.md", d)
    shutil.copy(ROOT / "characters" / "presenters.md", d)
    csv_info = "\n".join("{}: {}".format(k, v) for k, v in csv_row.items() if v)
    content = TASK_TMPL.format(slug=csv_row["slug"], csv_info=csv_info)
    (Path(d) / "product_info.md").write_text(content, encoding="utf-8")
    return d


# ------------------------------------------------------------------
# Goi agy
# ------------------------------------------------------------------

def run_agy(agy_bin, pid, sandbox, model, timeout_s):
    print("  [agy] Goi Gemini CLI cho san pham {}... (toi da {}s)".format(pid, timeout_s))
    r = subprocess.run(
        [agy_bin, "--new-project", "-p", AGY_PROMPT,
         "--model", model, "--print-timeout", "{}s".format(timeout_s)],
        cwd=sandbox,
        capture_output=True,
        text=True,
        timeout=timeout_s + 120,
        encoding="utf-8",
        errors="replace",
    )
    out = r.stdout or ""
    err = r.stderr or ""
    combined = (out + err).lower()
    if "no output produced" in combined:
        raise RuntimeError("agy bi chan quyen (co che an toan): {}".format((out + err).splitlines()[0][:200]))
    if "resource_exhausted" in combined or "quota" in combined:
        raise RuntimeError("agy bao het han muc quota. Doi roi chay lai.")
    if r.returncode != 0 and not out.strip():
        raise RuntimeError("agy thoat ma {}: {}. Da dang nhap chua? Thu `agy` trong terminal.".format(
            r.returncode, (err.strip() or "khong co thong bao")[:300]))
    return out


# ------------------------------------------------------------------
# Kiem tra ket qua
# ------------------------------------------------------------------

def check_output(pid):
    pdir = next(p for p in (ROOT / "products").iterdir() if p.name.startswith(pid + "_"))
    result = {}
    for name in ["research.json", "script.json"]:
        fp = pdir / name
        if fp.exists():
            try:
                data = json.loads(fp.read_text(encoding="utf-8"))
                result[name] = "OK ({} bytes)".format(len(str(data)))
            except Exception as e:
                result[name] = "LOI JSON: {}".format(e)
        else:
            result[name] = "CHUA CO"
    return result


# ------------------------------------------------------------------
# Cac buoc sau khi agy xong
# ------------------------------------------------------------------

def run_step(label, *args):
    print("\n> {}".format(label))
    r = subprocess.run([sys.executable] + list(map(str, args)), cwd=ROOT)
    if r.returncode != 0:
        print("  ! Buoc '{}' that bai (ma {}), tiep tuc...".format(label, r.returncode))


def post_process(pid, all_steps):
    if not all_steps:
        return
    # 1. Chuyen script.json -> prompts.json + prompts.md + script.md
    run_step("build_scripts {}".format(pid), T / "build_scripts.py", pid)
    # 2. Tai anh tham chieu neu chua co
    pdir = next(p for p in (ROOT / "products").iterdir() if p.name.startswith(pid + "_"))
    imgs = list((pdir / "ref_images").glob("*.jpg"))
    if not imgs:
        run_step("find_images {}".format(pid), T / "find_images.py", pid)
    else:
        print("  Anh da co ({} file), bo qua find_images".format(len(imgs)))
    # 3. Cap nhat bang dieu khien
    run_step("build_panel", T / "build_panel.py")


# ------------------------------------------------------------------
# Xu ly mot san pham
# ------------------------------------------------------------------

def process_one(pid, agy_bin, model, timeout_s, all_steps, csv_rows):
    sep = "=" * 60
    print("\n{}\nSAN PHAM {}: {}\n{}".format(sep, pid, csv_rows.get(pid, {}).get("slug", "?"), sep))

    row = csv_rows.get(pid)
    if not row:
        print("  ! Khong tim thay san pham {} trong products.csv".format(pid))
        return

    pdir = next((p for p in (ROOT / "products").iterdir() if p.name.startswith(pid + "_")), None)
    if not pdir:
        print("  ! Khong tim thay thu muc san pham id={}".format(pid))
        return

    already = (pdir / "research.json").exists() and (pdir / "script.json").exists()
    if already:
        print("  Da co research.json va script.json. Bo qua agy (dung --force de ghi de).")
        post_process(pid, all_steps)
        return

    sandbox = make_sandbox(pid, row)
    try:
        t0 = time.time()
        out = run_agy(agy_bin, pid, sandbox, model, timeout_s)
        elapsed = time.time() - t0
        print("  agy xong sau {:.0f}s".format(elapsed))
        if out.strip():
            lines = out.strip().splitlines()
            print("\n--- Bao cao agy ---")
            print("\n".join(lines[-40:]))
            print("--- Het bao cao ---")
    except subprocess.TimeoutExpired:
        print("  ! agy qua thoi gian ({}s). Kiem tra file da ghi chua.".format(timeout_s))
    except Exception as e:
        print("  ! Loi agy: {}".format(e))
    finally:
        shutil.rmtree(sandbox, ignore_errors=True)

    status = check_output(pid)
    for k, v in status.items():
        print("  {}: {}".format(k, v))

    post_process(pid, all_steps)


# ------------------------------------------------------------------
# Main
# ------------------------------------------------------------------

def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pids", nargs="*", help="ID san pham, vi du: 01 02 03")
    ap.add_argument("--batch", nargs="+", metavar="ID", help="Nhieu ID (thay the positional args)")
    ap.add_argument("--todo", action="store_true", help="Moi san pham chua co research.json")
    ap.add_argument("--force", action="store_true", help="Chay lai du da co file (backup truoc)")
    ap.add_argument("--all-steps", action="store_true",
                    help="Sau agy: chay build_scripts, find_images, build_panel")
    ap.add_argument("--model", default=os.environ.get("AGY_MODEL", "gemini-2.5-pro"),
                    help="Model agy (mac dinh: gemini-2.5-pro)")
    ap.add_argument("--timeout", type=int, default=900,
                    help="Giay toi da cho agy moi san pham (mac dinh: 900)")
    ap.add_argument("--agy", help="Duong dan toi agy.exe (mac dinh: tu tim)")
    a = ap.parse_args()

    agy_bin = a.agy or find_agy()
    if not agy_bin:
        sys.exit(
            "Khong tim thay Antigravity CLI (agy). Hay cai agy va dang nhap truoc.\n"
            "Hoac truyen --agy <path>."
        )
    print("agy: {}  model: {}".format(agy_bin, a.model))

    csv_rows = load_csv()

    ids = list(a.pids) + (a.batch or [])
    if a.todo:
        for pid_key in sorted(csv_rows.keys()):
            pdir = next((p for p in (ROOT / "products").iterdir()
                         if p.name.startswith(pid_key + "_")), None)
            if pdir and not (pdir / "research.json").exists():
                ids.append(pid_key)
        ids = sorted(set(ids))

    if not ids:
        ap.print_help()
        sys.exit("\nCan truyen ID san pham hoac --todo.")

    if a.force:
        for pdir in (ROOT / "products").iterdir():
            pid_key = pdir.name.split("_")[0]
            if pid_key in ids:
                for fn in ["research.json", "script.json"]:
                    f = pdir / fn
                    if f.exists():
                        bak = pdir / (fn + ".bak")
                        shutil.copy(f, bak)
                        f.unlink()
                        print("  Backup {} -> {}.bak".format(fn, fn))

    print("\nSe xu ly {} san pham: {}".format(len(ids), ", ".join(ids)))
    for pid in ids:
        process_one(pid.zfill(2), agy_bin, a.model, a.timeout, a.all_steps, csv_rows)

    print("\nHoan tat.")
    print("  -> Chay 1_tao_bang_dieu_khien.bat de xem ket qua trong bang dieu khien")
    print("  -> Chay 5_tao_video_flow.bat <id> --go de tao clip tren Flow")


if __name__ == "__main__":
    main()
