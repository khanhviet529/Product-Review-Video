import json
from pathlib import Path

p = Path("products/01_anker-soundcore-p20i/prompts.json")
data = json.loads(p.read_text(encoding="utf-8"))
data["style"] = "product-only"
if "presenter" in data:
    del data["presenter"]
if "onscreen_presenter" in data:
    del data["onscreen_presenter"]

desc = "Anker Soundcore P20i true wireless earbuds with compact charging case, matching the reference image"

motions = [
    ("slow push in toward the open charging case with earbuds seated inside", "the open charging case centred on a warm beige surface", "tight on the earbuds in the case"),
    ("slow dolly in toward the charging port and indicator light on the case", "close view of the charging case exterior", "crisp focus on the battery status LED"),
    ("slow pan across the short stem and silicone ear tip of one earbud", "one earbud resting on the matte podium", "sharp focus on the Soundcore logo on the earbud stem"),
    ("rack focus from the smooth matte case surface to the IPX5 acoustic mesh", "close-up on the earbud sound nozzle", "acoustic mesh in crisp high definition"),
    ("slow orbit around the earbuds and charging case", "both earbuds placed neatly in front of the open case", "both earbuds seen from a slight three-quarter angle"),
    ("slow lateral slider move across the case with warm directional lighting", "side profile of the compact pocketable case", "case resting cleanly in the frame"),
    ("gentle push in on the earbud touch sensor surface", "earbud resting on an off-white circular display stand", "close on the touch control area"),
    ("slow pull back revealing the earbuds and case together", "tight shot on the earbud tip", "full charging case and earbuds in the center of the frame"),
    ("slow dolly in highlighting the lightweight design and modern contours", "the earbuds displayed cleanly under soft window light", "sharp focus on the subtle curvature of the buds"),
    ("slow cinematic pull back to a wide studio display", "the complete Soundcore P20i earbuds and case resting stably", "wide centered shot with clean negative space around the product")
]

for i, c in enumerate(data["clips"]):
    c["ref_images"] = ["product_main"]
    motion_text, first_f, last_f = motions[i % len(motions)]
    c["first_frame"] = first_f
    c["motion"] = motion_text
    c["last_frame"] = last_f
    narr = c["narration_vi"].replace('"', "'")
    code = c["code"]
    c["flow_prompt"] = (
        f"{code}. Vertical 9:16, 8 seconds, photorealistic commercial product cinematography, 85mm prime lens. "
        f"Product: {desc}. "
        f"Environment: Warm beige seamless studio background (#E8E0D0), soft diffused window light from the left, soft-edged natural shadows, premium minimal aesthetic. "
        f"First frame: {first_f}. Motion: {motion_text}. Last frame: {last_f}. "
        f"Camera: smooth steady motion, razor-sharp focus on the product, natural depth of field with creamy background blur. "
        f"Voice-over: A calm friendly Vietnamese narrator speaks off-screen: \"{narr}\". "
        f"Cleanliness: No on-screen text, no typography, no watermarks, no human hands, no people. Pristine studio commercial look."
    )
    if "flow_prompt_voiceover" in c:
        del c["flow_prompt_voiceover"]

p.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
print("Updated 01_anker-soundcore-p20i/prompts.json to product-only style!")
