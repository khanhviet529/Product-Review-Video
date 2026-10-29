"""
Chuyển products/<slug>/script.json (tuyến nội dung V2, xem tools/SPEC2.md) thành prompts.json + prompts.md + script.md.

    python tools/build_scripts.py 24        # một sản phẩm
    python tools/build_scripts.py --all     # mọi sản phẩm có script.json

Kiểu video (theo 7 video mẫu trong video-review-studio/video template): CHỈ QUAY SẢN PHẨM, không người dẫn.
Nền be liền, ánh sáng cửa sổ mềm, camera đẩy vào từng chi tiết, thẻ chữ tiếng Việt ngắn hiện dần, lời đọc tiếng Việt do Veo nói (ngoài khung).
Ảnh sản phẩm được gắn bởi tools/flow/run_product.py. Prompt luôn <= 1000 ký tự.
"""
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

MOTION = {
    "push in": "slow push in toward {focus}",
    "rack focus": "rack focus from the foreground to {focus}",
    "dolly in": "slow dolly in, {focus} stays centred",
    "pan": "slow lateral pan across {focus}",
    "pull back": "slow pull back from {focus} to reveal the whole product",
    "orbit": "slow orbit around the product, {focus} in view",
}
LAST = {
    "push in": "tight on {focus}",
    "rack focus": "sharp on {focus}",
    "dolly in": "close on {focus}",
    "pan": "{focus} centred",
    "pull back": "the whole product centred with space around it",
    "orbit": "{focus} seen from a new angle",
}
SET = "warm beige seamless backdrop, soft diffused window light, premium minimal editorial look"
CLOSER = ("Soft subtle sound design, no music. No watermarks, no logos except those printed on the product itself.")
SHRINK = [(", premium minimal editorial look", ""), ("Soft subtle sound design, no music. ", ""),
          ("soft diffused window light", "soft window light"), (" in clean modern Vietnamese sans-serif", "")]


def product_desc(res):
    d = res.get("product_visual_description", "").strip()
    d = re.sub(r"\s*\((?:[^()]*(?:product image|official)[^()]*)\)\.?$", "", d)
    first = re.split(r";|\. ", d)[0].strip().rstrip(".")
    if len(first) > 170:
        cut = first[:170].rfind(",")
        first = first[:cut] if cut > 60 else first[:170].rsplit(" ", 1)[0]
    return first


def text_part(title, labels):
    if not title:
        return ""
    t = f'On-screen text in clean modern Vietnamese sans-serif, small rounded cards: title "{title}"'
    if labels:
        t += ", labels " + ", ".join(f'"{x}"' for x in labels[:2])
    return t + ". "


def build(pid):
    d = next(p for p in (ROOT / "products").iterdir() if p.name.startswith(pid + "_"))
    sj = d / "script.json"
    if not sj.exists():
        return f"{d.name}: chưa có script.json"
    sc = json.loads(sj.read_text(encoding="utf-8"))
    res = json.loads((d / "research.json").read_text(encoding="utf-8"))
    model = res["chosen_model"]
    desc = product_desc(res)
    clips = []
    for c in sc["clips"]:
        role, cam = c["role"], c.get("camera", "push in")
        if cam not in MOTION:
            cam = "push in"
        focus, scene = c["focus_en"].strip(), c["scene_en"].strip()
        narr = c["narration_vi"].replace('"', "'")
        code = f"P{pid}C{c['n']:02d}"
        first = f"{scene}"
        motion = MOTION[cam].format(focus=focus)
        last = LAST[cam].format(focus=focus)
        prompt = (f"{code}. Vertical 9:16, 8 seconds, photorealistic product video on a {SET}. Product: {desc}; "
                  f"it matches the exact product in the reference image. First frame: {first}. Motion: {motion}. Last frame: {last}. "
                  f"{text_part(c.get('title_vi', ''), c.get('labels_vi', []))}"
                  f'A young male narrator speaks in Vietnamese, calm and friendly, voice-over: "{narr}" {CLOSER}')
        for a, b in SHRINK:
            if len(prompt) <= 1000:
                break
            prompt = prompt.replace(a, b)
        clips.append({
            "n": c["n"], "code": code, "role": role, "criterion": c.get("criterion", ""), "narration_vi": c["narration_vi"],
            "facts_used": c.get("facts_used", []), "source_label": c.get("source_label", ""), "title_vi": c.get("title_vi", ""),
            "labels_vi": c.get("labels_vi", []), "camera": cam, "camera_reason": c.get("camera_reason", ""),
            "focus_en": focus, "scene_en": scene, "first_frame": first, "motion": motion, "last_frame": last,
            "ref_images": ["product_main"], "flow_prompt": prompt})
    pr = {"product_id": pid, "slug": d.name, "model": model, "style": "product-only", "thesis": sc.get("thesis", ""),
          "answer_short": sc.get("answer_short", ""), "takeaway": sc.get("answer_short", ""),
          "personas": sc.get("personas", []), "as_of": sc.get("as_of", ""), "target_seconds": 8 * len(clips), "clips": clips}
    (d / "prompts.json").write_text(json.dumps(pr, ensure_ascii=False, indent=2), encoding="utf-8")

    md = [f"# {pid}. {model} · prompts Flow (chỉ quay sản phẩm)\n", f"Luận điểm: {pr['thesis']}\n",
          "Gắn ảnh sản phẩm (ref_images/product_main.jpg) cho mỗi clip. Mỗi clip 8 giây.\n"]
    for c in clips:
        md += [f"\n## Clip {c['n']:02d} · {c['role']}{' · ' + c['criterion'] if c['criterion'] else ''} · {c['narration_vi']}\n",
               "```", c["flow_prompt"], "```", f"\nChữ: {c['title_vi']} {c['labels_vi']} · Camera: {c['camera']} — {c['camera_reason']}\n"]
    (d / "prompts.md").write_text("\n".join(md), encoding="utf-8")

    sm = [f"# Tuyến nội dung · {model}\n", f"**Luận điểm:** {pr['thesis']}\n", f"**Trả lời ngắn:** {pr['answer_short']}\n",
          "**Chân dung người mua:** " + " · ".join(pr["personas"]) + "\n", f"Đối chiếu nguồn ngày {pr['as_of']}.\n",
          "| # | vai trò | tiêu chí | chữ trên hình | lời đọc | nguồn | thông số dùng |", "|---|---|---|---|---|---|---|"]
    for c in clips:
        sm.append(f"| {c['n']} | {c['role']} | {c['criterion']} | {c['title_vi']} | {c['narration_vi']} | {c['source_label']} | {', '.join(c['facts_used'])} |")
    (d / "script.md").write_text("\n".join(sm), encoding="utf-8")
    over = [c["code"] for c in clips if len(c["flow_prompt"]) > 1000]
    return f"{d.name}: {len(clips)} clip, dài nhất {max(len(c['flow_prompt']) for c in clips)}" + (f", VƯỢT 1000: {over}" if over else "")


def main():
    args = [a for a in sys.argv[1:] if not a.startswith("--")]
    if "--all" in sys.argv:
        args = sorted(p.name.split("_")[0] for p in (ROOT / "products").iterdir() if (p / "script.json").exists())
    if not args:
        sys.exit(__doc__)
    for pid in args:
        print(build(pid))


if __name__ == "__main__":
    main()
