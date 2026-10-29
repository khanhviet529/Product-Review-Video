# Nhân vật dẫn (dùng chung cho mọi sản phẩm)

Quy tắc: mô tả bằng **đặc điểm nhìn thấy được**, không dùng tên riêng trong prompt (Veo nhận diện tốt hơn).
Hai người dẫn luân phiên: sản phẩm có số **lẻ → Người dẫn F**, số **chẵn → Người dẫn M**.

## Người dẫn F (khối mô tả, dán nguyên vào mọi prompt có người dẫn)
```
a Vietnamese woman in her late 20s with shoulder-length straight black hair and light side-swept bangs, warm light-brown skin, small gold stud earrings, natural makeup, wearing a plain white crew-neck t-shirt under a light beige overshirt, friendly confident expression
```

## Người dẫn M
```
a handsome young Vietnamese man in his mid-20s, textured black quiff hairstyle, clear skin, sharp jawline, bright confident smile, athletic build, olive bomber jacket over a white t-shirt, upbeat energetic expression
```

## Bối cảnh cố định (STUDIO)
```
a bright modern minimalist desk studio, light oak desk, soft natural window light from the left, plain warm-white wall, shallow depth of field
```

## Tạo ảnh nhân vật tham chiếu (làm 1 lần, dùng cho mọi video)
Dán vào công cụ tạo ảnh của Flow (hoặc Whisk / Imagen), lưu ảnh vào thư mục `characters/`:

- `presenter_F_front.png`:
  `Photorealistic portrait, vertical 9:16, <KHỐI MÔ TẢ F>, seated at a light oak desk in <STUDIO>, facing the camera, hands resting on the desk, neutral soft smile, sharp focus on face, natural skin texture`
- `presenter_F_side.png`: cùng mô tả, đổi thành `three-quarter view looking slightly to the right`
- `presenter_M_front.png` và `presenter_M_side.png`: tương tự với khối mô tả M.

Khi tạo clip, tải ảnh `presenter_*_front.png` lên Flow làm ảnh tham chiếu (ingredient) cùng với ảnh sản phẩm
để khuôn mặt nhất quán giữa các clip.

## Chọn giọng nói cho nhân vật (trong Flow: Nhân vật → Chọn giọng nói)

Gắn giọng vào nhân vật để mọi clip dùng **cùng một giọng**. Làm sau khi đã có ảnh nhân vật.

1. **Thử tiếng Việt trước khi chọn.** Dán câu này vào ô "Hội thoại mẫu" (tối đa 120 ký tự) rồi bấm Xem trước:
   `Xin chào, mình review nhanh tai nghe này. Pin dùng được khoảng mười tiếng, sạc nhanh mười phút nghe thêm hai tiếng.`
   Chọn giọng đọc tiếng Việt tự nhiên, đúng dấu, không giọng nước ngoài.
2. **Gợi ý giọng** (xem thêm các giọng ở cuối danh sách):
   - Người dẫn nam trẻ, năng động: `Achird` (Male, friendly, mid pitch). Nếu có, thử thêm giọng ghi "upbeat", "youthful", "excitable".
   - Người dẫn nữ: `Autonoe` (Female, bright, mid pitch) hoặc `Achernar` (Female, soft, high pitch). Tránh giọng "gravelly", "low pitch" vì nghe già và nặng.
3. **Ô "Tuỳ chỉnh đặc điểm giọng nói"** (dán nguyên):
   - Nam: `Young, energetic and friendly male Vietnamese voice, clear standard pronunciation, upbeat pace, natural smile in the voice, not too deep`
   - Nữ: `Young, bright and friendly female Vietnamese voice, clear standard pronunciation, upbeat pace, warm and confident, natural smile in the voice`
   Nếu muốn giọng miền Nam hoặc miền Bắc, thêm vào cuối: `Northern Vietnamese accent` hoặc `Southern Vietnamese accent`. Dùng một giọng vùng cho cả 40 video.
4. Bấm **Thêm vào nhân vật**. Từ giờ tạo clip bằng cách chọn đúng nhân vật này thay vì chỉ tải ảnh lên.
