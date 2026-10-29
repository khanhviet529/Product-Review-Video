"""
Tạo (và tải về) các clip của một sản phẩm trên Flow.

    python tools/flow/run_product.py 02              # chỉ xem kế hoạch (KHÔNG tạo, KHÔNG tốn tín dụng)
    python tools/flow/run_product.py 02 --go         # tạo các clip còn thiếu rồi tải về inbox/
    python tools/flow/run_product.py 02 --go --max 3 # chỉ tạo tối đa 3 clip trong lần này
    python tools/flow/run_product.py 02 --download   # chỉ tải các clip đã tạo xong trên Flow

Mỗi clip gắn 2 thành phần: nhân vật (giọng + gương mặt cố định) và ảnh sản phẩm (đúng mẫu, đúng màu).
Clip đầu của sản phẩm: tải ảnh sản phẩm lên + gắn nhân vật. Các clip sau: dùng lại thẻ trước để nạp lại cả hai.

Chốt chặn: không bấm tạo nếu chi phí hiển thị khác kỳ vọng (--cost, mặc định 12), bỏ qua clip đã có thẻ trên Flow
hoặc đã có file trong raw/, và dừng ngay khi có lỗi bất thường.
"""
import argparse
import json
import shutil
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from flow_client import Flow, sync_playwright  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
UPLOAD = Path(__file__).resolve().parent / "_upload"
CHAR_BY_PRESENTER = {"M": "NguoiDanNam"}          # nhân vật nữ sẽ thêm khi cần


def load(pid):
    d = next(p for p in (ROOT / "products").iterdir() if p.name.startswith(pid + "_"))
    return d, json.loads((d / "prompts.json").read_text(encoding="utf-8"))


def fcode(c):
    return c.get("flow_code") or c["code"]


def prepare_composer(f, clips, char, product_file):
    """Đưa ô nhập về trạng thái: ảnh sản phẩm (+ nhân vật nếu char) đã gắn, chưa có chữ. Số thành phần cần = 2 nếu có nhân vật, 1 nếu không."""
    need = 2 if char else 1
    f._close_overlays()
    f.go_project_home()
    f.clear_prompt()
    f.pg.mouse.wheel(0, -8000)
    f.settle(600)
    prev = next((fcode(c) for c in reversed(clips) if f.has_card(fcode(c))), None)   # thẻ gần nhất của sản phẩm này
    if prev and f.reuse_from(prev) and f.chip_count() == need:
        return "reuse " + prev
    f.clear_prompt()
    f.upload_asset(str(product_file))            # tải lên tự gắn vào ô nhập
    if char:
        f.add_character(char)
    if f.chip_count() != need:
        raise RuntimeError(f"Ô nhập có {f.chip_count()} thành phần, cần đúng {need}.")
    return "upload"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("pid")
    ap.add_argument("--go", action="store_true", help="thật sự bấm tạo (tốn tín dụng)")
    ap.add_argument("--download", action="store_true", help="chỉ tải clip đã tạo xong")
    ap.add_argument("--max", type=int, default=99)
    ap.add_argument("--cost", type=int, default=12, help="chi phí kỳ vọng mỗi clip (tín dụng)")
    ap.add_argument("--wait", type=int, default=360, help="giây tối đa chờ các clip tạo xong")
    a = ap.parse_args()

    d, pr = load(a.pid)
    if pr.get("style") == "product-only":
        char = None                                   # chỉ quay sản phẩm: không gắn nhân vật
    else:
        char = CHAR_BY_PRESENTER.get(pr.get("presenter"))
        if not char:
            sys.exit(f"Chưa có nhân vật Flow cho người dẫn {pr.get('presenter')}.")
    clips = pr["clips"]
    todo = [c for c in clips
            if not (d / "raw" / f"C{c['n']:02d}.mp4").exists() and not (ROOT / "inbox" / f"{c['code']}.mp4").exists()]
    n = min(len(todo), a.max)
    print(f"{d.name}: {len(clips)} clip, còn thiếu {len(todo)}, nhân vật {char or '(không, chỉ quay sản phẩm)'}")
    print(f"Ước tính: {n} clip x {a.cost} = {n * a.cost} tín dụng")
    if not a.go and not a.download:
        print("(Chỉ xem kế hoạch. Thêm --go để tạo, hoặc --download để tải.)")
        return

    UPLOAD.mkdir(exist_ok=True)
    product_file = UPLOAD / f"SP{a.pid}_main.jpg"
    if not product_file.exists():
        shutil.copy(d / "ref_images" / "product_main.jpg", product_file)

    with sync_playwright() as p:
        f = Flow(p)
        made = []
        if a.go:
            f.go_project_home()
            f.set_video_settings("9:16", "720p", 8, 1)
            for c in todo[:a.max]:
                fc = fcode(c)
                if f.has_card(fc):
                    print(f"  {c['code']}: đã có thẻ {fc} trên Flow, bỏ qua (không tạo trùng)")
                    made.append(c)
                    continue
                how = prepare_composer(f, clips, char, product_file)
                f.fill_prompt(c["flow_prompt"])
                assert f.prompt_text().startswith(fc + "."), f"prompt {fc} chưa điền đúng"
                assert f.chip_count() == (2 if char else 1), "mất thành phần trước khi tạo"
                r = f.generate(a.cost, confirm=True)
                print(f"  {c['code']}: đã bấm tạo ({how}; chi phí {r['cost']})")
                made.append(c)
                f.settle(3000)
        want = made if a.go else todo
        pending = {c["code"]: c for c in want}
        deadline = time.time() + a.wait
        while pending and time.time() < deadline:
            for code, c in list(pending.items()):
                if f.card_state(fcode(c)) == "xong":
                    dest = ROOT / "inbox" / f"{code}.mp4"
                    f.download_clip(fcode(c), str(dest))
                    print(f"  {code}: đã tải -> {dest.name}")
                    del pending[code]
            if pending:
                f.settle(8000)
        if pending:
            print("Chưa xong/không thấy:", ", ".join(pending))


if __name__ == "__main__":
    main()
