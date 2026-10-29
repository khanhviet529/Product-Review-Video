# 40 video review đồ công nghệ (Google Flow / Veo, dọc 9:16, tiếng Việt)

> **Dự án này tự chạy độc lập**, không cần thư mục "Làm bài tập xóa logo". Công cụ xóa logo và dữ liệu logo đã nằm trong
> `tools/logo_remover/`. Cài một lần: `setup.bat` (tạo `.venv` riêng; cần FFmpeg trong PATH và Google Chrome).
> Làm trọn một sản phẩm: `6_lam_het_mot_san_pham.bat <id> --go` (tạo clip trên Flow → tải về → xóa logo → ghép video trong `final/`).


Mọi thứ đã được chuẩn bị sẵn: 40 sản phẩm đã chốt mẫu, có thông số và nguồn, ảnh tham chiếu, và prompt cho từng clip.
Việc của bạn chỉ còn: **copy prompt → dán vào Flow → tải video về → thả vào `inbox/`**. Phần còn lại do công cụ làm.

## Chế độ tự động (đã chạy thật với sản phẩm 02, ra video 88 giây)
1. `0_mo_chrome_flow.bat` → đăng nhập Google một lần trong cửa sổ Chrome riêng (giữ phiên cho các lần sau).
2. `5_tao_video_flow.bat 02` → xem kế hoạch (không tốn tín dụng). Thêm `--go` để tool tự: tải ảnh sản phẩm lên, gắn nhân vật,
   điền prompt, bấm tạo từng clip (chốt chặn: dừng nếu giá hiển thị ≠ 12 tín dụng), đợi xong và tải về `inbox/` đúng tên slot.
3. `3_nhap_video_va_xoa_logo.bat` → xếp clip vào sản phẩm + xóa logo. 4. `4_ghep_video.bat 02` → `final/02_qcy-t13.mp4`.

Phát hiện khi chạy thật (đã đo):
- **Giá 12 tín dụng/clip** (720p, 8 giây) → 417 clip ≈ 5000 tín dụng ≈ 5 tháng với 1000/tháng.
- **Tên file Flow tự đặt theo nội dung** (ví dụ `Man_speaking_about_earbuds_...mp4`), **không chứa mã slot** → tool tự tải đúng thẻ theo mã ở đầu prompt.
- **Giọng ngoài khung (voice-over) không giữ giọng nhân vật** (cao độ lệch ~30%). Vì vậy mọi clip để người dẫn nói trực tiếp trước ống kính
  (`tools/rewrite_onscreen.py <id>` viết lại prompt của một sản phẩm theo kiểu này). Đã làm cho sản phẩm 02; các sản phẩm khác chạy lệnh này trước khi tạo.
- Phải gắn **ảnh sản phẩm** (không chỉ nhân vật), nếu không Veo vẽ sai màu/kiểu (hộp trắng thay vì đen).
- Hiện chỉ có nhân vật nam (NguoiDanNam). Sản phẩm số lẻ (người dẫn nữ) cần đặt tên và gắn giọng cho nhân vật nữ rồi thêm vào `CHAR_BY_PRESENTER`.

## Cách làm thủ công (bấm đúp các file .bat theo số)

| Bước | Việc | Cách |
|---|---|---|
| 0 (một lần) | Tạo ảnh nhân vật dẫn | Mở `control_panel.html` → nút **Nhân vật** → copy 4 prompt → tạo ảnh trong Flow → lưu vào `characters/` |
| 1 | Mở bảng điều khiển | `1_tao_bang_dieu_khien.bat` |
| 2 | Lấy prompt | Bấm **Copy clip kế tiếp** (hoặc chọn sản phẩm rồi **Copy prompt** từng clip) |
| 3 | Tạo trên Flow | Dán prompt, tải lên ảnh ghi ở dòng "ảnh tải lên" (ảnh sản phẩm: `products/<slug>/ref_images/product_main.jpg`; ảnh người dẫn: `characters/`) → Generate → tải về |
| 4 | Nhập và xóa logo | Thả video vào `inbox/` rồi bấm `3_nhap_video_va_xoa_logo.bat` |
| 5 | Ghép video | Khi một sản phẩm đủ clip: `4_ghep_video.bat 07` hoặc `4_ghep_video.bat --all` → `final/` |

Mỗi prompt bắt đầu bằng mã slot (ví dụ `P07C03`). Tên file Flow tải về thường chứa mã này nên công cụ tự xếp đúng chỗ.
**Hãy thử với clip đầu tiên** để xác nhận tên file có chứa mã; nếu không, dùng
`python tools/import_inbox.py --assign "<tên file>" P07C03`.

## Cấu trúc
```
products.csv            40 sản phẩm: mẫu đã chốt, giá, số clip, credit, trạng thái xác minh
control_panel.html      bảng điều khiển (copy prompt, theo dõi tiến độ, đếm credit)
characters/             nhân vật dẫn + prompt tạo ảnh
products/NN_<mẫu>/      brief.md (thông số + nguồn) · prompts.md/json · research.json
                        ref_images/ (ảnh tham chiếu) · raw/ (gốc có logo) · clean/ (đã xóa logo)
inbox/                  thả video tải từ Flow
final/                  video hoàn chỉnh của từng sản phẩm
tools/                  find_images · import_inbox · clean_batch (xóa logo) · assemble · validate · build_panel
tools/SPEC.md           quy chuẩn viết prompt và xác minh
tools/validation_report.md   cảnh báo chất lượng dữ liệu
```

## Credit
Tổng cộng **417 clip × 12 credit = 5004 credit**, khoảng **5 tháng** với 1000 credit/tháng (giá 12 đã đo trên Flow, không phải 15). Bảng điều khiển hiển thị credit đã dùng.
Muốn rút ngắn: giảm số clip của từng sản phẩm (xóa bớt clip `feature` ở `prompts.json` rồi chạy lại `1_tao_bang_dieu_khien.bat`).

## Những điều cần kiểm tay (xem `tools/validation_report.md` và từng `brief.md`, mục "Chưa xác minh")
- Một số sản phẩm đang hết hàng ở Việt Nam hoặc chỉ một nguồn giá. Kiểm tra lại giá và tồn kho **trước khi đăng**.
- Ảnh chính (`product_main.jpg`) được chọn tự động; hãy xem lại ở sản phẩm 13, 15, 31 và chọn ảnh khác trong `ref_images/` nếu cần.
- Giọng nói của Veo có thể khác nhau giữa các clip. Nếu ghép nghe lệch, báo lại để chuyển sang giọng đọc tạo ở bước dựng.
