# QUY CHUẨN CHUNG (đọc hết trước khi làm)

Dự án: 40 video review sản phẩm công nghệ tại **Việt Nam**, dọc 9:16, tiếng Việt, tạo bằng Google Flow (Veo).
Veo có giọng nói riêng: **lời đọc nằm trong prompt** và Veo tự nói. Mỗi clip dài **8 giây**. Mỗi sản phẩm ghép nhiều clip
thành video **khoảng 1–2 phút (8–15 clip, tùy lượng thông tin)**.

Nguyên tắc trung tính (từ skill gemini-product-compare): chỉ nói điều có nguồn, công bằng, không quảng cáo, không hạ bệ.
Mỗi video có cả điểm mạnh và điểm cần cân nhắc. Không bịa số liệu, URL, câu trích dẫn.

## 1. Việc của bạn cho MỖI sản phẩm được giao

Thư mục sản phẩm: `D:\Project\Product Review Video\products\<slug>\` (đã có `brief.md` mẫu, `ref_images/`, `raw/`, `clean/`).
Dòng của sản phẩm trong `D:\Project\Product Review Video\products.csv` (cột `mau_ung_vien`, `goc_review`) cho biết ứng viên.
**Chỉ ghi vào thư mục sản phẩm của bạn. KHÔNG sửa products.csv hay file nào khác.**

### Bước A. Chốt mẫu (dùng WebSearch, WebFetch; nếu chưa có công cụ thì ToolSearch `select:WebSearch,WebFetch`)
- Chọn **một mẫu cụ thể, còn bán ở Việt Nam** (đời mới nhất hợp lý, không chọn hàng đã ngừng bán). Ghi tên đầy đủ + mã model.
- Ứng viên ghi 2 mẫu hoặc "xác định mẫu" → bạn quyết định và nêu lý do ngắn; ghi mẫu bị loại vào `alternatives_rejected`.
- Hôm nay là 2026-10-22; ưu tiên thông tin còn hiệu lực.

### Bước B. Thông số và giá, **có nguồn uy tín**
- Thông số: ưu tiên trang chính hãng (sản phẩm, datasheet, hướng dẫn), sau đó đánh giá độc lập uy tín (ví dụ RTINGS, Notebookcheck,
  GSMArena, Tom's Hardware, các trang công nghệ lớn Việt Nam như Tinh Tế, Genk, Thế Giới Di Động, FPT Shop, CellphoneS, Phong Vũ,
  Hà Nội Computer). Mỗi số liệu phải kèm `source_url` thật bạn đã mở và đọc.
- Giá: trang bán ở Việt Nam (Thế Giới Di Động, FPT Shop, CellphoneS, Phong Vũ, Shopee Mall chính hãng...), ghi **ngày** và khoảng giá.
  Nhiều nguồn lệch nhau → ghi khoảng, `confidence: "vua"`.
- Mỗi thông số: `confidence` ∈ `cao` (chính trang nguồn nói đúng ý này) | `vua` | `thap`.
  **Chỉ `cao`/`vua` mới được dùng trong lời đọc.** Không tìm được → đưa vào `unverified`, **không** dùng trong lời đọc.
- Số liệu đo ở điều kiện khác nhau phải ghi điều kiện (ví dụ pin "bật ANC" / "tắt ANC"). Không so hai số khác điều kiện.
- Thông tin cốt lõi theo nhóm hàng (phải có hoặc ghi rõ chưa xác minh):
  - Tai nghe, loa: thời lượng pin, chống ồn, đeo lâu có đau tai, kết nối và độ trễ, chống nước.
  - Sạc, sạc dự phòng, hub: công suất/dung lượng thật, số cổng và chuẩn, thiết bị sạc được, kích thước/khối lượng, mang lên máy bay.
  - Màn hình, máy tính bảng, laptop: kích thước, độ phân giải, tần số quét, cổng, pin, hợp việc gì.
  - Đồng hồ/vòng đeo: màn hình, pin, GPS, theo dõi sức khỏe, chống nước, tương thích điện thoại.
  - Chuột, bàn phím: kết nối, pin, cảm giác phím/độ ồn, thiết bị ghép đôi, kích thước.
  - Router/mạng: chuẩn Wi-Fi, tốc độ, số cổng, vùng phủ, phù hợp diện tích.
  - Camera: độ phân giải, góc nhìn, hồng ngoại, lưu trữ, chống nước, cách xem từ xa.
  - Lưu trữ, thẻ nhớ: dung lượng, tốc độ đọc/ghi, giao tiếp, độ bền.
  - Đèn, quạt, mic, webcam: thông số kỹ thuật chính, pin/nguồn, độ ồn, hợp đối tượng nào.

### Bước C. Điều tra góc người mua (ngắn)
Tìm vài đánh giá thật (độc lập hoặc người dùng) để rút `strengths` (3–5) và `caveats` (2–4) **có nguồn**.
Caveat là điểm thật người dùng/đánh giá nhắc tới. Không bịa. Không tìm được → ghi `unverified`.

### Bước D. Ảnh tham chiếu (rất quan trọng)
Tìm trang chính hãng của sản phẩm và các **URL ảnh sản phẩm trực tiếp** (ảnh nền trắng, ảnh góc nghiêng, ảnh đang dùng).
Ghi 4–8 ứng viên vào `ref_image_candidates` (`url` là link ảnh trực tiếp .jpg/.png/.webp bạn đã thấy trong HTML/trang;
`page` là trang chứa nó). Chỉ lấy từ trang chính hãng hoặc cửa hàng lớn. Không ghi URL bạn không thấy thật.
Cũng ghi `official_page` và `product_visual_description` (màu, hình dáng, đặc điểm nhận dạng nhìn thấy được,
**lấy từ trang nguồn**, bằng tiếng Anh, 1–2 câu).

### Bước E. Câu mang về và dàn ý
Viết một câu mang về dạng điều kiện ("Cần X thì chọn sản phẩm này; cần Y thì cân nhắc..."), rồi chọn số clip
(8–15; sản phẩm đơn giản 8, nhiều thông tin 12–15). Mỗi clip một ý.
Khung: clip 1 HOOK (đưa luôn câu trả lời ngắn có điều kiện) → các ý chính (mỗi clip 1 ý; ý mạnh thứ nhì đặt sớm, mạnh nhất để cuối)
→ 1–2 clip điểm cần cân nhắc → clip HỢP VỚI AI → clip KẾT (CTA trung tính: "Lưu lại trước khi mua", "Bạn đang dùng loại nào?").

### Bước F. Viết prompt Flow cho TỪNG clip

**Lời đọc (`narration_vi`)**
- Tiếng Việt tự nhiên, ngôi thứ nhất, giọng bạn bè: **≤ 22 từ**, 1–2 câu, đọc xong trong khoảng 7 giây.
- Mỗi clip chỉ một ý. Mỗi số chỉ nói một lần trong cả video (trừ câu tóm tắt).
- Số và đơn vị viết **như người nói**: "hai mươi nghìn mi-li-am-pe giờ", "sáu mươi lăm oát", "một nghìn tám trăm nghìn đồng"
  (không dùng ký hiệu %, /, ~, ×, —, emoji). Tên model giữ nguyên.
- Nhịp: "A làm tốt X. Đổi lại, Y." Kết luận có điều kiện. Không tuyên bố thắng toàn diện.
- Cấm: đỉnh cao, hoàn hảo, số 1, tốt nhất, vô đối, siêu phẩm, thần thánh, không thể bỏ qua, bí mật, bạn sẽ không tin, chắc chắn, cam kết,
  đừng mua, phí tiền, áp đảo, vượt trội, và mọi lời hứa kết quả. Không "Hôm nay mình sẽ...", không "Hãy cùng khám phá". Không giọng quảng cáo.
- Chỉ dùng thông số `cao`/`vua`. Mỗi clip ghi `facts_used` = danh sách id thông số (`s1`, `s2`...) đã dùng.

**Khung prompt (`flow_prompt`) — tiếng Anh, 1 đoạn văn liền, 450–900 ký tự, theo cấu trúc ViMax: khung đầu, chuyển động, khung cuối**
Bắt đầu bằng mã slot `P<id>C<nn>.` (ví dụ `P07C03.`) để tên file tải về chứa mã slot. Sau đó theo thứ tự:
1. `Vertical 9:16, 8 seconds, photorealistic, <loại cảnh/ống kính>.`
2. **First frame**: bố cục tĩnh lúc bắt đầu (người dẫn hay chỉ sản phẩm, vị trí, ánh sáng). Là ảnh tĩnh, không có hành động đang diễn ra.
3. **Motion**: tách rõ chuyển động camera (dùng thuật ngữ: push in, dolly in, pull back, pan, tilt, orbit, rack focus, macro) và chuyển động trong khung. Mỗi chuyển động camera phải có **lý do** (ghi vào trường `camera_reason`).
   Gợi ý lý do: push in = tiến vào đúng chi tiết quan trọng; pull back = mở từ chi tiết ra để thấy quy mô; widen = giữ một đối tượng rồi lộ thêm.
4. **Last frame**: ảnh tĩnh lúc kết thúc, khớp với chuyển động.
5. Người dẫn (nếu có): dán **nguyên văn khối mô tả** người dẫn F hoặc M (xem `characters/presenters.md`; sản phẩm số lẻ dùng F, số chẵn dùng M)
   và bối cảnh STUDIO. Nhân vật nói câu lời đọc bằng tiếng Việt: `She/He says in Vietnamese, in a natural friendly tone: "<narration_vi>"`.
6. Sản phẩm: nhắc `exact product shown in the reference image` và dùng `product_visual_description` làm mô tả. Không tự thêm tính năng không có.
7. Cuối câu luôn có: `No on-screen text, no captions, no subtitles, no watermarks. Clean audio: clear Vietnamese speech, soft room tone, no music.`
- Không mô tả nhân vật bằng tên riêng. Mô tả bằng đặc điểm nhìn thấy được. Không văn hoa. Chỉ thông tin hình dung được.
- Các clip xen kẽ: cảnh có người dẫn nói (hook, hợp với ai, kết) và cảnh sản phẩm cận cảnh/dùng thật (lời đọc là giọng người dẫn ngoài khung: `voice-over by the presenter, off-screen`).
- Cảnh cận cảnh dùng đúng ảnh tham chiếu sản phẩm; trường `ref_images` liệt kê **loại** ảnh nên tải lên Flow cho clip đó
  (`product_main`, `product_angle`, `presenter_front`).

## 2. File phải tạo trong thư mục sản phẩm

### `research.json` (UTF-8, JSON hợp lệ)
```json
{
  "id": "07",
  "slug": "<tên thư mục>",
  "status": "xac_minh | mot_phan | khong_tim_duoc",
  "chosen_model": "Tên đầy đủ + mã model",
  "alternatives_rejected": [{"model": "...", "reason": "..."}],
  "official_page": "https://...",
  "price_vnd": {"low": 0, "high": 0, "as_of": "2026-10-22", "sources": ["s_price1"], "confidence": "vua"},
  "specs": [{"id": "s1", "key": "Pin", "value_vi": "...", "condition": "...", "source": "src1", "confidence": "cao"}],
  "strengths": [{"text": "...", "source": "src2"}],
  "caveats": [{"text": "...", "source": "src3"}],
  "sources": [{"id": "src1", "url": "https://...", "title": "...", "type": "chinh_hang | cua_hang | danh_gia | nguoi_dung"}],
  "unverified": ["điều không tìm được nguồn và cách xử lý"],
  "product_visual_description": "English, from the source page",
  "ref_image_candidates": [{"url": "https://...jpg", "page": "https://...", "kind": "product_main | product_angle | in_use"}],
  "takeaway": "câu mang về",
  "buyer_personas": ["...", "..."]
}
```

### `prompts.json`
```json
{
  "product_id": "07", "slug": "...", "model": "...", "presenter": "F",
  "takeaway": "...", "target_seconds": 96,
  "clips": [
    {"n": 1, "code": "P07C01", "role": "hook | feature | caveat | fit | outro",
     "narration_vi": "...", "facts_used": ["s1"],
     "camera": "push in", "camera_reason": "...",
     "first_frame": "...", "motion": "...", "last_frame": "...",
     "ref_images": ["product_main", "presenter_front"],
     "flow_prompt": "P07C01. Vertical 9:16, ... (toàn bộ văn bản để dán vào Flow)"}
  ]
}
```
`flow_prompt` phải đầy đủ, **tự đứng được** (đã chèn khối nhân vật, bối cảnh, lời đọc). `first_frame/motion/last_frame` chỉ để tham khảo.

### `brief.md` (ghi đè file mẫu, tiếng Việt, gọn)
Mẫu đã chốt + lý do · giá và ngày · bảng thông số (giá trị, điều kiện, nguồn, độ tin cậy) · điểm mạnh · điểm cần cân nhắc ·
chưa xác minh · câu mang về · dàn ý các clip (1 dòng mỗi clip: vai trò + ý chính) · danh sách nguồn (URL đầy đủ).

### `prompts.md`
Mỗi clip một mục: `## Clip nn · vai trò · lời đọc`, bên dưới là `flow_prompt` trong code fence, kèm dòng "Ảnh cần tải lên: ...".

## 3. Kiểm tra trước khi xong
- JSON hợp lệ (đọc lại bằng python -c "import json;json.load(open(...,encoding='utf-8'))").
- Mỗi `narration_vi` ≤ 22 từ, không từ cấm, mọi số trong lời đọc đều khớp thông số `cao`/`vua`.
- Mỗi `flow_prompt` bắt đầu bằng mã slot, ≤ 1000 ký tự, có khối nhân vật hoặc "voice-over, off-screen", có câu kết "No on-screen text...".
- Không có URL, số liệu nào bạn chưa thấy thật trong nguồn.
- Cuối cùng trả về cho người điều phối **báo cáo ngắn** (≤ 12 dòng): mỗi sản phẩm một dòng gồm mẫu đã chốt, giá, số clip, trạng thái, vấn đề còn lại.
