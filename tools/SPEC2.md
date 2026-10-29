# QUY CHUẨN NỘI DUNG V2 (thay cho phần "dàn ý" của SPEC.md)

Học từ `D:\Project\video-review-studio` (skill gemini-product-compare + kịch bản Philips/Lock&Lock v2). Giữ nguyên các quy tắc trung lập,
nguồn và từ cấm của SPEC.md; chỉ đổi **tuyến nội dung** và cách viết cảnh.

## 1. Mỗi video có một LUẬN ĐIỂM, không phải danh sách thông số
Viết trước `thesis` dạng "Đừng chọn <loại hàng> chỉ bằng <con số hay bị nhìn> — hãy chọn theo <cách bạn dùng>".
Ví dụ: "Đừng chọn tai nghe chống ồn chỉ bằng số đê-xi-ben, hãy xem bạn đi đâu và nghe bao lâu".
Rồi `answer_short`: câu trả lời ngắn có điều kiện (cần X thì mẫu này; cần Y thì xem loại khác). Mọi clip phải phục vụ luận điểm.

## 2. Ba chân dung người mua
Chọn 3 chân dung thật sự khác nhau cho loại hàng (xem `buyer_personas` trong research.json, bổ sung nếu thiếu). Hook đánh vào nỗi lo của chân dung đông nhất,
dùng từ ngữ người mua. Phần "hợp với ai" dùng các chân dung này.

## 3. Tuyến nội dung (10–13 clip, mỗi clip 8 giây, một ý)
| # | role | Nội dung | Ghi chú |
|---|---|---|---|
| 1 | `hook` | Câu hỏi theo nhu cầu + luận điểm + trả lời ngắn có điều kiện | Câu đầu 5–10 từ, nói luôn nỗi lo/lợi ích. Không chào hỏi. |
| 2 | `identify` | "Đây là <đúng tên mẫu>. Mình sẽ xem <3 tiêu chí> trước khi chọn." (+ giá nếu có nguồn và ngày) | Giá chỉ khi price_vnd.confidence cao/vua; nói rõ "theo <cửa hàng>, cập nhật <ngày>". |
| 3.. | `criterion` | **Chương theo tiêu chí** người mua hỏi (3–5 tiêu chí cốt lõi của loại hàng). Mỗi tiêu chí 1–2 clip: <br>(a) SỰ THẬT có nhãn nguồn: "Hãng công bố…", "Theo bài đo của <trang>…", "Nhiều người dùng phản ánh…" <br>(b) Ý NGHĨA/NHẬN ĐỊNH có điều kiện: "Nghĩa là…", "Nếu bạn…, thì…" | Mở chương bằng câu hỏi người mua; đóng bằng ý nhận định. Số liệu đo ở điều kiện khác nhau phải nói điều kiện. |
| n-2 | `limits` | Giới hạn: đây là tổng hợp thông tin công bố và đánh giá, chưa phải tự đo; nêu 1–2 điều cần kiểm tra trước khi mua (phiên bản, giá, bảo hành, tồn kho) | Nói thẳng, không rào đón dài. Có thể kèm điểm yếu thật có nguồn. |
| n-1 | `fit` | Hai nhánh nhu cầu: "Nếu bạn <chân dung A>, hợp vì…; nếu bạn <chân dung B>, cân nhắc <hướng khác> vì…" | Không tuyên bố thắng toàn diện. |
| n | `outro` | Một câu chốt + CTA trung tính + "thông tin đối chiếu ngày <as_of>" | Không thêm thông số mới. |

Sắp xếp tiêu chí: ý mạnh thứ nhì đặt sớm, ý quyết định nhất để cuối chương trước `limits`. Nối các ý bằng "nhưng / vì vậy / đổi lại", không bằng "và".
Câu hỏi mở phải được trả lời ngay clip sau.

## 4. Ba lớp trong lời đọc: sự thật → ý nghĩa → khuyến nghị
Không trộn ý kiến vào câu nêu sự thật. Mỗi clip `criterion` nên có nhãn nguồn nói thành lời ("hãng công bố", "theo <tên trang>", "theo cảm nhận của người dùng").
`source_label` ∈ `hang` | `danh_gia` | `nguoi_dung` | `cua_hang` | `nhan_dinh` (nhận định của người dẫn, không có số).

## 5. Quy tắc lời đọc (giữ từ SPEC.md, bổ sung)
- ≤ 22 từ/clip (1–2 câu), mỗi câu ≤ 20 từ. Số và đơn vị viết bằng chữ như người nói. Không ký hiệu.
- Nhịp ưu–nhược: "A làm tốt X. Đổi lại, Y."
- Chỉ nói điều có trong research.json (spec `cao`/`vua`, strengths, caveats có nguồn). Mỗi clip ghi `facts_used`. Không giá nếu không có nguồn + ngày.
- Không "không có" khi thực ra "chưa thấy công bố". Điều chưa xác minh: bỏ khỏi video, hoặc nói đúng "cần kiểm tra trước khi mua". Không tạo cả clip nói về việc chưa xác minh.
- Cấm: đỉnh cao, hoàn hảo, số 1, tốt nhất, vô đối, siêu phẩm, thần thánh, không thể bỏ qua, bí mật, chắc chắn, cam kết, đừng mua, phí tiền, áp đảo, vượt trội, "cùng so sánh"; không giọng quảng cáo; không câu triết lý rỗng.
- Không văn AI: tránh "nâng tầm", "trải nghiệm tuyệt vời", "không chỉ… mà còn…", "Hãy cùng khám phá".

## 6. Hình: mỗi clip nhìn một thứ khác nhau (quan sát → bằng chứng → ý nghĩa)
Người dẫn nam LUÔN ở trong khung và tự nói (để giữ đúng giọng nhân vật); sản phẩm nằm trong tay hoặc ngay trước mặt.
Mỗi clip có `focus_en`: **một bộ phận nhìn thấy được của sản phẩm** mà lời đọc đang nói tới (ví dụ "the USB-C port", "the charging case lid", "the keycaps"),
chỉ lấy từ `product_visual_description` hoặc phần thật sự có ở loại sản phẩm đó; không bịa tính năng, nút, đèn hay chữ trên sản phẩm.
`action_en`: người dẫn làm gì với sản phẩm (ví dụ "presses the case lid open with his thumb"). Hai clip liền nhau không trùng `focus_en` và không trùng `camera`.
`camera` ∈ `push in` | `rack focus` | `dolly in` | `pan` | `pull back` | `orbit`. `camera_reason`: lý do chọn bằng một câu tiếng Việt
(push in = tiến vào đúng chi tiết đang nói; rack focus = nối chi tiết với người nói; pan = lia từ thiết bị sang người nói; pull back = mở ra để thấy quy mô; orbit = xem sản phẩm từ nhiều góc).
Không chữ trên màn hình, không phụ đề (Veo không vẽ chữ đáng tin); mọi nhãn nguồn phải nằm trong lời nói.

## 7. File đầu ra cho mỗi sản phẩm: `products/<slug>/script.json`
```json
{
  "product_id": "24", "as_of": "2026-10-22",
  "thesis": "...", "answer_short": "...",
  "personas": ["...", "...", "..."],
  "clips": [
    {"n": 1, "role": "hook", "criterion": "", "source_label": "nhan_dinh",
     "narration_vi": "...", "facts_used": [],
     "focus_en": "the product on the desk in front of him", "action_en": "resting one hand beside the product",
     "camera": "push in", "camera_reason": "..."}
  ]
}
```
Giữ đúng `n` từ 1, `role` đúng bảng trên. Sau khi ghi, tự kiểm tra: JSON hợp lệ; lời đọc ≤ 22 từ; không từ cấm; mọi số khớp thông số `cao`/`vua`; không giá trừ khi có nguồn+ngày;
không clip nào trùng `focus_en`/`camera` với clip kề; có đủ hook, identify, ≥ 3 criterion, limits, fit, outro. Báo cáo ≤ 6 dòng.
**Chỉ ghi file script.json trong thư mục sản phẩm của bạn. Không sửa file khác.**
