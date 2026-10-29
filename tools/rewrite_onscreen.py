"""
Viết lại prompt của một sản phẩm để MỌI clip có người dẫn nói trực tiếp trước ống kính.

Lý do (đã đo): giọng "ngoài khung" của Veo không giữ giọng nhân vật (cao độ lệch ~30% so với clip có người dẫn),
còn clip người dẫn nói trực tiếp thì dùng đúng giọng đã gắn cho nhân vật. Vì vậy sản phẩm luôn nằm trong tay / trên bàn
của người dẫn, không có cảnh "chỉ sản phẩm + lời đọc ngoài khung".

    python tools/rewrite_onscreen.py 02

Giữ nguyên lời đọc (narration_vi) và thông số; chỉ đổi flow_prompt, camera, first/motion/last frame.
Bản cũ lưu ở trường flow_prompt_voiceover của mỗi clip.
"""
import json
import re
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

ROOT = Path(__file__).resolve().parent.parent

# (loại ống kính, khung đầu, chuyển động, khung cuối, tay/sản phẩm, camera, lý do camera)
HOOK = ("medium close-up", "seated at the desk facing the camera, {noun} resting on the desk beside him, relaxed upright posture",
        "slow push in toward his face as he starts speaking, he glances at the product then back to the lens",
        "tighter on his face and shoulders, product still visible at the lower edge of the frame",
        "{noun} on the desk within reach", "push in", "tiến vào người nói để mở đầu bằng câu trả lời ngắn")
FEATURE = [
    ("medium close-up", "seated at the desk, one hand lifting {noun} toward the camera at chest height",
     "slow push in on the product in his open palm while he keeps eye contact with the lens",
     "product held close to the lens in sharp focus, his face softly blurred behind it",
     "holding {noun} in his open palm", "push in", "tiến vào đúng chi tiết sản phẩm đang nói đến"),
    ("close-up", "face and shoulders, one hand bringing {noun} up next to his cheek",
     "rack focus from the product beside his cheek to his eyes, he turns slightly toward the lens",
     "sharp on his face, product soft beside his cheek",
     "showing {noun} beside his face", "rack focus", "chuyển nét từ sản phẩm sang người nói để nối chi tiết với đánh giá"),
    ("medium shot", "seated at the desk, both hands holding {noun} at table height, looking down at it",
     "he looks up at the camera mid-sentence while the camera does a slow dolly in",
     "closer on his face with both hands and the product still in frame",
     "turning {noun} in both hands", "dolly in", "lại gần dần để tạo cảm giác trò chuyện trực tiếp"),
    ("medium shot", "standing near the window, {noun} in one hand and a smartphone in the other",
     "slow pan from the phone in his hand across to his face as he speaks",
     "centred on his face, phone and product low in the frame",
     "holding {noun} and a phone", "pan", "lia từ thiết bị sang người nói để cho thấy cách dùng thực tế"),
    ("medium close-up", "seated at the desk, {noun} held out toward the camera at arm's length",
     "he draws the product back toward himself as the camera pulls back to reveal the desk",
     "wider shot of him at the desk, product held at chest height",
     "pulling {noun} back from the lens", "pull back", "mở rộng khung hình để thấy quy mô sản phẩm so với người"),
]
CAVEAT = [
    ("medium close-up", "seated at the desk, thoughtful expression, {noun} held loosely in one hand",
     "slow dolly in as he tilts his head slightly and raises his eyebrows while speaking",
     "closer on his face, product lowered out of focus",
     "holding {noun} loosely", "dolly in", "tiến gần để nhấn vào điểm cần cân nhắc một cách thẳng thắn"),
    ("medium shot", "seated at the desk, {noun} set down in front of him, hands open",
     "slow pull back as he gestures with one open hand",
     "wide on him and the desk, product small at the centre of the table",
     "with {noun} on the desk in front of him", "pull back", "lùi ra để đặt điểm yếu trong bức tranh chung"),
]
FIT = ("medium close-up", "leaning slightly forward at the desk, {noun} beside him, open friendly posture",
       "slow dolly in as he gestures with an open hand toward the camera",
       "close on his smiling face, product visible at the edge",
       "with {noun} beside him", "dolly in", "lại gần như nói chuyện với đúng người cần sản phẩm này")
OUTRO = ("medium shot", "seated at the desk, {noun} on the table, bright smile toward the camera",
         "slow pull back while he gives a small friendly wave at the end",
         "wide on him and the desk with the product, warm and relaxed",
         "with {noun} on the desk", "pull back", "lùi ra khép lại video một cách thân thiện")

SCENE = ("The presenter from the character reference sits in a bright minimalist desk studio, light oak desk, soft window light "
         "from the left, plain warm-white wall.")
CLOSER = ("No on-screen text, no captions, no subtitles, no watermarks. "
          "Clean audio: clear Vietnamese speech, soft room tone, no music.")


def noun_of(res):
    name = re.split(r"[(,]", res["chosen_model"])[0].strip()
    return f"the {name} earbuds" if "tai nghe" in res.get("takeaway", "").lower() else f"the {name}"


def pick(role, i, feat_i):
    if role == "hook":
        return HOOK
    if role == "caveat":
        return CAVEAT[i % len(CAVEAT)]
    if role == "fit":
        return FIT
    if role == "outro":
        return OUTRO
    return FEATURE[feat_i % len(FEATURE)]


def main():
    pid = sys.argv[1]
    d = next(p for p in (ROOT / "products").iterdir() if p.name.startswith(pid + "_"))
    pr = json.loads((d / "prompts.json").read_text(encoding="utf-8"))
    res = json.loads((d / "research.json").read_text(encoding="utf-8"))
    noun = noun_of(res)
    feat_i = cav_i = 0
    for c in pr["clips"]:
        role = c["role"]
        shot, first, motion, last, hold, cam, why = pick(role, cav_i, feat_i)
        if role == "feature":
            feat_i += 1
        if role == "caveat":
            cav_i += 1
        c.setdefault("flow_prompt_voiceover", c["flow_prompt"])
        first, motion, last, hold = (t.format(noun=noun) for t in (first, motion, last, hold))
        he_says = c["narration_vi"].replace('"', "'")
        c["first_frame"], c["motion"], c["last_frame"] = first, motion, last
        c["camera"], c["camera_reason"] = cam, why
        c["ref_images"] = ["presenter_front", "product_main"]
        c["flow_prompt"] = (
            f"{c['code']}. Vertical 9:16, 8 seconds, photorealistic, {shot}. First frame: {first}. Motion: {motion}. "
            f"Last frame: {last}. {SCENE} He speaks to the camera in Vietnamese, upbeat, "
            f'lips in sync: "{he_says}" He is {hold}; the product matches the exact one in the product reference image. '
            f"{CLOSER}")
        for a, b in ((", soft window light from the left, plain warm-white wall.", ", soft window light."),
                     ("in a bright minimalist desk studio, light oak desk,", "at a light oak desk,"),
                     ("clear Vietnamese speech, soft room tone, no music", "Vietnamese speech, room tone, no music"),
                     ("no captions, no subtitles, no watermarks", "no captions, no watermarks")):
            if len(c["flow_prompt"]) <= 1000:
                break
            c["flow_prompt"] = c["flow_prompt"].replace(a, b)
    pr["onscreen_presenter"] = True
    (d / "prompts.json").write_text(json.dumps(pr, ensure_ascii=False, indent=2), encoding="utf-8")
    # prompts.md
    lines = [f"# {pid}. {res['chosen_model']} · prompts Flow (người dẫn nói trực tiếp trước ống kính)\n",
             "Gắn nhân vật NguoiDanNam + ảnh sản phẩm (ref_images/product_main.jpg) cho mỗi clip. Mỗi clip 8 giây.\n"]
    for c in pr["clips"]:
        lines += [f"\n## Clip {c['n']:02d} · {c['role']} · {c['narration_vi']}\n", "```", c["flow_prompt"], "```",
                  f"\nCamera: {c['camera']} — {c['camera_reason']}\n"]
    (d / "prompts.md").write_text("\n".join(lines), encoding="utf-8")
    over = [c["code"] for c in pr["clips"] if len(c["flow_prompt"]) > 1000]
    print(f"{d.name}: viết lại {len(pr['clips'])} clip; vượt 1000 ký tự: {over or 'không'}; "
          f"dài nhất {max(len(c['flow_prompt']) for c in pr['clips'])}")
    print(pr["clips"][2]["flow_prompt"])


if __name__ == "__main__":
    main()
