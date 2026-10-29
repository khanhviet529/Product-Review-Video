"""
=============================================================================
ĐỀ TÀI: XÓA WATERMARK / LOGO TRÊN VIDEO SỬ DỤNG OPENCV & FFMPEG
=============================================================================
Mô tả:
    Chương trình tự động phát hiện tỉ lệ khung hình (16:9, 9:16), định vị
    tọa độ logo (như logo Google Flow / Veo / Gemini) và khôi phục các pixel
    bị logo che khuất một cách liền mạch với bối cảnh xung quanh.

Cơ chế tính toán và chèn pixel:
    1. Reverse Alpha Blending (phương pháp chính):
       - Logo Google Flow là lớp phủ TRẮNG bán trong suốt:
             I(x,y) = (1 - a(x,y)) * B(x,y) + a(x,y) * 255
         với I là pixel quan sát được, B là nền thật, a là độ đục của logo.
       - Bản đồ alpha a(x,y) được ước lượng từ chính video (cảnh nền gần đen
         ở cuối clip, nơi B ~ hằng số) và lưu ở star_alpha_1080p.png.
       - Khôi phục nền:  B = (I - a*255) / (1 - a)
         => giữ nguyên texture da / vải / da tai nghe, không bị nhòe.
    2. Image Inpainting (phương pháp bổ trợ):
       - Fast Marching Method (Telea, 2004) hoặc Navier-Stokes (Bertalmio, 2001)
         chỉ dùng cho: (a) ngôi sao phụ ở cảnh intro, (b) video không có alpha map
         (fallback). Dải viền quanh logo được xử lý bằng median + khử nhiễu màu/thời gian.
    3. Thích ứng theo cảnh (Scene-Aware):
       - Tự dò điểm cắt cảnh đầu tiên để biết ngôi sao phụ biến mất ở frame nào.
    4. Tối ưu hóa hiệu năng (ROI-based):
       - Chỉ xử lý vùng lân cận logo thay vì toàn bộ khung 1920x1080.
    5. Giữ nguyên âm thanh và chất lượng:
       - Kết hợp FFmpeg để ghép luồng âm thanh gốc và xuất video H.264 (CRF 18).
=============================================================================
"""

import os
import sys
import argparse
import subprocess
import tempfile
import threading
import queue
import time
from typing import Tuple, Optional, Callable
import cv2
import numpy as np

# Đảm bảo in tiếng Việt trên console Windows không bị lỗi font
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")


class VideoWatermarkRemover:
    """Lớp xử lý xóa watermark và nội suy pixel cho video."""

    # Tỉ lệ tọa độ tương đối mặc định cho các định dạng chuẩn của Google Flow / Veo
    # Tọa độ chuẩn dạng tỷ lệ phần trăm [x_ratio, y_ratio, w_ratio, h_ratio]
    PRESETS = {
        "16:9": {
            "name": "Màn hình ngang 16:9 (Bottom-Right)",
            # 1700/1920 = 0.8854, 860/1080 = 0.7963, 80/1920 = 0.0417, 80/1080 = 0.0741
            "coords_ratio": (0.8854, 0.7963, 0.0417, 0.0741),
        },
        "9:16": {
            "name": "Màn hình dọc 9:16 (Bottom-Right)",
            # Tọa độ góc dưới phải cho video dọc 1080x1920
            "coords_ratio": (0.8400, 0.8800, 0.0750, 0.0420),
        },
    }

    # Cấu trúc thư mục dự án: assets/ (dữ liệu logo), input/ (video gốc), output/ (video đã xóa logo)
    PROJECT_DIR = os.path.dirname(os.path.abspath(__file__))
    ASSET_DIR = os.path.join(PROJECT_DIR, "assets")
    INPUT_DIR = os.path.join(PROJECT_DIR, "input")
    OUTPUT_DIR = os.path.join(PROJECT_DIR, "output")

    # Dữ liệu logo ở độ phân giải tham chiếu 1920x1080
    REF_W, REF_H = 1920, 1080
    ALPHA_FILE = "star_alpha_1080p.png"      # alpha 16-bit của ngôi sao chính
    ALPHA_ORIGIN = (1675, 835)               # góc trên-trái của alpha map ở 1080p
    ENCODE_THREADS = max(2, (os.cpu_count() or 4) // 2)   # chừa CPU cho xử lý ảnh, tránh tranh chấp luồng
    EDGE_ALPHA_FLOOR = 0.35                  # mức nội suy dải viền tối thiểu khi vành đai có biên thật
    CHROMA_SIGMA_STRONG = 0.0                # >0: làm mượt màu mạnh hơn trong vùng logo
    BAND_MEDIAN = 7                          # cỡ lọc median ở dải viền (lẻ: 3, 5, 7)
    ENCODE_PRESET = "veryfast"               # x264 preset: veryfast ~2.5x nhanh hơn fast, chất lượng CRF 18 gần như tương đương
    MODEL_FILE = "star_model_1080p.npz"      # mô hình a/c từng pixel-kênh (calibrate_logo.py)
    UNION_MASK_FILE = "exact_google_flow_mask_1080p.png"  # mặt nạ cả 2 ngôi sao (intro)

    def __init__(
        self,
        input_path: str,
        output_path: Optional[str] = None,
        inpaint_method: str = "telea",
        inpaint_radius: int = 2,
    ):
        self.input_path = input_path
        if not os.path.exists(input_path):
            raise FileNotFoundError(f"Không tìm thấy file video: {input_path}")

        if output_path is None:
            # Mặc định: output/<tên video>_cleaned.mp4 (tách riêng khỏi input)
            os.makedirs(self.OUTPUT_DIR, exist_ok=True)
            name = os.path.splitext(os.path.basename(input_path))[0]
            self.output_path = os.path.join(self.OUTPUT_DIR, f"{name}_cleaned.mp4")
        else:
            self.output_path = output_path

        self.inpaint_method = inpaint_method.lower()
        self.inpaint_radius = inpaint_radius

        # Đọc thông tin video
        self.cap = cv2.VideoCapture(self.input_path)
        if not self.cap.isOpened():
            raise ValueError(f"Không thể mở video bằng OpenCV: {input_path}")

        self.width = int(self.cap.get(cv2.CAP_PROP_FRAME_WIDTH))
        self.height = int(self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
        self.fps = self.cap.get(cv2.CAP_PROP_FPS) or 24.0
        self.total_frames = int(self.cap.get(cv2.CAP_PROP_FRAME_COUNT))
        self.duration = self.total_frames / self.fps if self.fps > 0 else 0
        self.cap.release()

        # Xác định tỉ lệ khung hình
        self.aspect_ratio_str = self._detect_aspect_ratio()

        # Chuẩn bị alpha map / mặt nạ và dò cảnh intro có 2 ngôi sao
        self._prepare_masks()
        self.intro_last_frame = self._scan_intro()

    def _detect_aspect_ratio(self) -> str:
        """Tự động phân tích tỉ lệ khung hình của video."""
        ratio = self.width / max(1, self.height)
        if abs(ratio - 16 / 9) < 0.15:
            return "16:9"
        elif abs(ratio - 9 / 16) < 0.15:
            return "9:16"
        elif abs(ratio - 1.0) < 0.1:
            return "1:1"
        return "custom"

    def get_preset_bbox(self, preset_key: Optional[str] = None) -> Tuple[int, int, int, int]:
        """
        Tính toán tọa độ pixel thực tế (x, y, w, h) từ tỉ lệ định sẵn.
        """
        key = preset_key or self.aspect_ratio_str
        if key in self.PRESETS:
            xr, yr, wr, hr = self.PRESETS[key]["coords_ratio"]
            x = int(round(xr * self.width))
            y = int(round(yr * self.height))
            w = int(round(wr * self.width))
            h = int(round(hr * self.height))
            return (x, y, w, h)

        # Mặc định góc dưới bên phải nếu tỉ lệ khác
        w = int(self.width * 0.05)
        h = int(self.height * 0.08)
        x = int(self.width - w - (self.width * 0.07))
        y = int(self.height - h - (self.height * 0.12))
        return (x, y, w, h)

    # ------------------------------------------------------------------
    # Alpha map & mặt nạ
    # ------------------------------------------------------------------
    @staticmethod
    def _read_image(path: str, flags=cv2.IMREAD_UNCHANGED) -> Optional[np.ndarray]:
        """Đọc ảnh an toàn với đường dẫn Unicode trên Windows."""
        if not os.path.exists(path):
            return None
        try:
            return cv2.imdecode(np.fromfile(path, dtype=np.uint8), flags)
        except Exception:
            return None

    def _logo_scale(self) -> float:
        """Logo có kích thước pixel cố định theo cạnh ngắn của video (1.0 ở 1080p, cả ngang lẫn dọc)."""
        return min(self.width, self.height) / self.REF_H

    def _place_layer(self, small: np.ndarray, origin: Tuple[int, int], interp) -> np.ndarray:
        """
        Đặt layer nhỏ (tọa độ tham chiếu 1920x1080) lên canvas kích thước video thật.
        Logo neo vào GÓC DƯỚI PHẢI (khoảng cách tới mép phải/dưới không đổi), nên dùng được cho cả
        video ngang 16:9 lẫn dọc 9:16 (đã kiểm chứng: vị trí khớp đến từng pixel).
        """
        s = self._logo_scale()
        if s != 1.0:
            small = cv2.resize(
                small, (max(1, round(small.shape[1] * s)), max(1, round(small.shape[0] * s))),
                interpolation=interp,
            )
        canvas = np.zeros((self.height, self.width), dtype=small.dtype)
        ox = self.width - round((self.REF_W - origin[0]) * s)
        oy = self.height - round((self.REF_H - origin[1]) * s)
        sx0, sy0 = max(0, -ox), max(0, -oy)                      # phần layer nằm ngoài khung bên trái/trên
        dx0, dy0 = max(0, ox), max(0, oy)
        w = min(small.shape[1] - sx0, self.width - dx0)
        h = min(small.shape[0] - sy0, self.height - dy0)
        if h > 0 and w > 0:
            canvas[dy0:dy0 + h, dx0:dx0 + w] = small[sy0:sy0 + h, sx0:sx0 + w]
        return canvas

    def _align_roi(self, x1: int, y1: int, x2: int, y2: int) -> Tuple[int, int, int, int]:
        """Căn ROI cho YUV 4:2:0: tọa độ chẵn và chiều cao chia hết cho 4 (bố cục I420 của OpenCV)."""
        x1, y1 = max(0, x1) & ~1, max(0, y1) & ~1
        x2, y2 = min(self.width, (x2 + 1) & ~1), min(self.height, (y2 + 1) & ~1)
        while (y2 - y1) % 4:
            if y2 + 2 <= self.height:
                y2 += 2
            else:
                y1 -= 2
        return x1, y1, x2, y2

    def _prepare_masks(self):
        """Nạp alpha map & dựng các mặt nạ; fallback hình chữ nhật nếu thiếu file / sai tỉ lệ."""
        d = self.ASSET_DIR
        alpha16 = self._read_image(os.path.join(d, self.ALPHA_FILE))
        union = self._read_image(os.path.join(d, self.UNION_MASK_FILE), cv2.IMREAD_GRAYSCALE)

        self.alpha: Optional[np.ndarray] = None  # (H, W, 1) float32, None nếu không có alpha map
        if alpha16 is not None and alpha16.dtype == np.uint16:
            a = self._place_layer(alpha16.astype(np.float32) / 65535.0, self.ALPHA_ORIGIN, cv2.INTER_LINEAR)
            self.alpha = np.clip(a, 0.0, 0.95)[:, :, np.newaxis]
            m1 = (a > 0.01).astype(np.uint8) * 255
            m1 = cv2.morphologyEx(m1, cv2.MORPH_CLOSE, np.ones((3, 3), np.uint8))
        else:
            m1 = np.zeros((self.height, self.width), np.uint8)
            x, y, w, h = self.get_preset_bbox()
            m1[max(0, y):y + h, max(0, x):x + w] = 255

        if union is not None and self.alpha is not None:
            uys, uxs = np.where(union > 0)                       # cắt riêng vùng logo rồi neo vào góc dưới phải
            if len(uxs):
                u0x, u0y = int(uxs.min()), int(uys.min())
                union = self._place_layer(union[u0y:int(uys.max()) + 1, u0x:int(uxs.max()) + 1], (u0x, u0y), cv2.INTER_NEAREST)
                union = cv2.dilate(union, np.ones((3, 3), np.uint8))
            else:
                union = m1.copy()
        else:
            union = m1.copy()

        self.mask_star1 = m1                              # ngôi sao chính (xuyên suốt video)
        self.mask_union = cv2.bitwise_or(union, m1)       # cả 2 ngôi sao (cảnh intro)

        # Dải viền (~5px mỗi phía): nơi khử alpha còn sai số sub-pixel và nhiễu rung (ringing) của bộ nén
        # quanh cạnh logo -> lọc median mềm, sau đó bơm lại texture để dải này không mịn hơn nền.
        # (11/11 + median 7 được chọn bằng đo năng lượng viền/độ nhám trên nhiều cảnh.)
        band = cv2.subtract(cv2.dilate(m1, np.ones((11, 11), np.uint8)), cv2.erode(m1, np.ones((11, 11), np.uint8)))
        self.band_w = cv2.GaussianBlur(band.astype(np.float32) / 255.0, (0, 0), 1.2)
        # Ngôi sao phụ (cảnh intro) -> inpaint, vì không có alpha map riêng cho nó
        self.mask_star2 = cv2.subtract(self.mask_union, cv2.dilate(m1, np.ones((5, 5), np.uint8)))

        ys, xs = np.where(self.mask_union > 0)
        pad = 24
        rx1, ry1 = max(0, int(xs.min()) - pad), max(0, int(ys.min()) - pad)
        rx2, ry2 = min(self.width, int(xs.max()) + pad + 1), min(self.height, int(ys.max()) + pad + 1)
        self.roi = self._align_roi(rx1, ry1, rx2, ry2)

        # Mô hình hiệu chỉnh từng pixel/kênh (nếu có): I = (1-a)*B + c, chính xác cả ở viền logo
        self.model_a: Optional[np.ndarray] = None
        self.model_c: Optional[np.ndarray] = None
        model_path = os.path.join(d, self.MODEL_FILE)
        if self.alpha is not None and os.path.exists(model_path):
            try:
                mdl = np.load(model_path)
                ox, oy = (int(v) for v in mdl["origin"])
                ma = np.stack([self._place_layer(mdl["a"][:, :, j], (ox, oy), cv2.INTER_LINEAR) for j in range(3)], 2)
                mc = np.stack([self._place_layer(mdl["c"][:, :, j], (ox, oy), cv2.INTER_LINEAR) for j in range(3)], 2)
                rx1, ry1, rx2, ry2 = self.roi
                self.model_a = np.clip(ma[ry1:ry2, rx1:rx2], 0.0, 0.9).astype(np.float32)
                self.model_c = mc[ry1:ry2, rx1:rx2].astype(np.float32)
            except Exception:
                self.model_a = self.model_c = None

        # Vùng khử nhiễu: chỉ áp dụng quanh logo (mềm biên) để không đụng phần ảnh còn lại
        grow = np.ones((11, 11), np.uint8)
        x1, y1, x2, y2 = self.roi
        self.dn_w_star1 = self._feather(cv2.dilate(m1, grow)[y1:y2, x1:x2])
        self.dn_w_union = self._feather(cv2.dilate(self.mask_union, grow)[y1:y2, x1:x2])
        self._prev_roi: Optional[np.ndarray] = None  # trạng thái bộ lọc thời gian

        # Trọng số theo độ sâu bên trong logo: lõi = 1, mũi nhọn/biên -> 0 (giữ chi tiết thật ở mũi sao)
        dist = cv2.distanceTransform(m1, cv2.DIST_L2, 3)
        self.core_w = np.clip((dist - 1.0) / 6.0, 0.0, 1.0)[y1:y2, x1:x2, np.newaxis].astype(np.float32)
        ring = cv2.subtract(cv2.dilate(m1, np.ones((41, 41), np.uint8)), cv2.dilate(m1, np.ones((15, 15), np.uint8)))
        self.ring_sel = ring[y1:y2, x1:x2] > 0

        # Dải ngay ngoài / ngay trong biên logo, dùng để khớp màu theo biên
        self.out_strip = (cv2.dilate(m1, np.ones((9, 9), np.uint8)) - cv2.dilate(m1, np.ones((3, 3), np.uint8)))[y1:y2, x1:x2] > 0
        self.in_strip = (cv2.erode(m1, np.ones((3, 3), np.uint8)) - cv2.erode(m1, np.ones((9, 9), np.uint8)))[y1:y2, x1:x2] > 0
        self.bnd = (cv2.dilate(m1, np.ones((3, 3), np.uint8)) - cv2.erode(m1, np.ones((3, 3), np.uint8)))[y1:y2, x1:x2] > 0
        self.inner_w = cv2.GaussianBlur(cv2.erode(m1, np.ones((3, 3), np.uint8))[y1:y2, x1:x2].astype(np.float32) / 255.0, (0, 0), 1.5)[:, :, np.newaxis]

        # Hằng số của phép khớp biên (không đổi theo frame) -> tính một lần
        wo = self.out_strip.astype(np.float32)
        wi = self.in_strip.astype(np.float32)
        self._wo, self._wi = wo[:, :, None], wi[:, :, None]
        self._inv_bo = (1.0 / (cv2.GaussianBlur(wo, (0, 0), 4.0) + 1e-4))[:, :, None]
        self._inv_bi = (1.0 / (cv2.GaussianBlur(wi, (0, 0), 4.0) + 1e-4))[:, :, None]
        bnd_f = self.bnd.astype(np.float32)
        self._bnd = bnd_f[:, :, None]
        self._inv_wide = (1.0 / (cv2.GaussianBlur(bnd_f, (0, 0), 12.0) + 1e-4))[:, :, None]

        # Hộp bao lõi logo (trong tọa độ ROI): texture chỉ cần tính trong hộp này
        cys, cxs = np.where(self.core_w[:, :, 0] > 0.05)
        m_ = 8
        self._tb = (max(0, int(cys.min()) - m_), min(self.core_w.shape[0], int(cys.max()) + m_ + 1),
                    max(0, int(cxs.min()) - m_), min(self.core_w.shape[1], int(cxs.max()) + m_ + 1))
        self._tex_age = 0
        # Nội suy dải viền khi nền mịn: Telea inpaint từ các điểm gần nhất ở hai phía dải viền
        self._band_mask = (self.band_w[y1:y2, x1:x2] > 0.3).astype(np.uint8) * 255
        # Texture được bơm vào cả lõi lẫn dải viền (dải viền vừa bị median làm mịn)
        self._tex_w = np.maximum(self.core_w[:, :, 0], self.band_w[y1:y2, x1:x2])

        # Ứng viên "donor texture": cùng cửa sổ ROI nhưng dịch sang vùng không có logo
        self._donors = {False: [], True: []}
        for intro in (False, True):
            logo = cv2.dilate(self.mask_union if intro else m1, np.ones((9, 9), np.uint8))
            for rad in (80, 95, 115, 140):
                for ang in range(0, 360, 45):
                    dx, dy = int(round(rad * np.cos(np.radians(ang)))), int(round(rad * np.sin(np.radians(ang))))
                    if x1 + dx < 0 or y1 + dy < 0 or x2 + dx > self.width or y2 + dy > self.height:
                        continue
                    shifted = np.roll(np.roll(m1, dy, axis=0), dx, axis=1)
                    if np.any(cv2.bitwise_and(shifted, logo)):
                        continue
                    self._donors[intro].append((dx, dy))
        self._donor_pick: Optional[Tuple[int, int]] = None
        self._score_pick = 0.0

    @staticmethod
    def _feather(mask: np.ndarray) -> np.ndarray:
        return cv2.GaussianBlur(mask.astype(np.float32) / 255.0, (0, 0), 3.0)[:, :, np.newaxis]

    def _denoise(self, cleaned: np.ndarray, intro: bool, temporal: bool, frame: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Khử nhiễu vùng vừa khôi phục. Phép chia cho (1-a) khuếch đại nhiễu nén H.264
        (nhất là nhiễu màu ở vùng tối), nên:
          1. Làm mượt kênh màu Cr/Cb (mắt người kém nhạy với nhiễu màu tần số thấp).
          2. Lọc thời gian thích ứng chuyển động: chỗ tĩnh trộn với frame trước,
             chỗ chuyển động / cắt cảnh giữ nguyên frame hiện tại (không bị bóng mờ).
        """
        ycc = cv2.cvtColor(cleaned, cv2.COLOR_BGR2YCrCb)
        # Màu: chroma khôi phục đã khớp vùng xung quanh (đã đo, sai lệch ~1-2 mức) -> chỉ cần làm mượt
        ycc[:, :, 1:] = cv2.GaussianBlur(ycc[:, :, 1:], (0, 0), 3.0)
        if self.CHROMA_SIGMA_STRONG > 0:
            # Chroma của video nguồn có độ phân giải thấp nên quầng màu quanh cạnh logo loang rộng: làm mượt mạnh hơn
            # trong vùng logo (trọng số mềm), vì mắt nhạy với độ sáng hơn nhiều so với màu.
            strong = cv2.GaussianBlur(ycc[:, :, 1:], (0, 0), self.CHROMA_SIGMA_STRONG).astype(np.float32)
            wc = self._tex_w[:, :, None]
            ycc[:, :, 1:] = (strong * wc + ycc[:, :, 1:].astype(np.float32) * (1.0 - wc)).astype(np.uint8)
        dn = cv2.cvtColor(ycc, cv2.COLOR_YCrCb2BGR).astype(np.float32)

        reset = True
        if temporal:
            prev = self._prev_roi
            reset = prev is None
            if prev is not None and prev.shape == dn.shape:
                diff = cv2.GaussianBlur(np.abs(dn - prev).mean(axis=2), (0, 0), 2.0)
                w_prev = (0.6 * np.exp(-(diff / 5.0) ** 2))[:, :, np.newaxis]
                dn = dn * (1.0 - w_prev) + prev * w_prev
                reset = float(diff.mean()) > 12.0   # cắt cảnh / chuyển cảnh nhanh -> chọn lại donor
            self._prev_roi = dn.copy()

        w = self.dn_w_union if intro else self.dn_w_star1
        out = dn * w + cleaned.astype(np.float32) * (1.0 - w)
        out = self._add_texture(out, frame, intro, reset)
        return np.clip(out, 0, 255).astype(np.uint8)

    def _match_boundary(self, img: np.ndarray) -> np.ndarray:
        """
        Khớp màu theo biên: đo chênh lệch trung bình giữa dải ngay ngoài và ngay trong biên logo
        (chuẩn hóa tích chập), nội suy mượt vào lõi rồi cộng bù. Sửa sai lệch sáng/màu nhỏ còn sót
        (nhìn như hình thoi mờ trên nền phẳng); giới hạn +-5 mức nên không phá biên thật.
        """
        sig = 4.0
        delta = (cv2.GaussianBlur(img * self._wo, (0, 0), sig) * self._inv_bo
                 - cv2.GaussianBlur(img * self._wi, (0, 0), sig) * self._inv_bi)
        delta = np.clip(delta, -5.0, 5.0) * self._bnd
        # Nội suy rất mượt (sigma 12): làm ở 1/4 độ phân giải cho nhanh, kết quả gần như không đổi
        h, w = delta.shape[:2]
        small = cv2.GaussianBlur(cv2.resize(delta, (w // 4, h // 4), interpolation=cv2.INTER_AREA), (0, 0), 3.0)
        wide = cv2.resize(small, (w, h), interpolation=cv2.INTER_LINEAR) * self._inv_wide
        wide = np.clip(wide, -5.0, 5.0)
        return img + wide * self.inner_w

    def _add_texture(self, img: np.ndarray, frame: Optional[np.ndarray], intro: bool, reset: bool) -> np.ndarray:
        """
        Vùng dưới logo mất chi tiết nhỏ do nén nên mịn hơn nền (nhìn như một mảng trong suốt).
        Bù bằng chi tiết tần số cao lấy từ vùng lân cận cùng khung hình (donor), chọn donor có độ sáng và
        độ nhám gần vùng quanh logo nhất, biên độ vừa đủ để lấp phần thiếu hụt. Vì donor lấy từ cùng
        khung hình nên vân di chuyển cùng camera (không nhấp nháy như nhiễu ngẫu nhiên).
        """
        cands = self._donors[intro]
        if frame is None or not cands or not self.ring_sel.any():
            return img
        x1, y1, x2, y2 = self.roi
        t0, t1, u0, u1 = self._tb                       # hộp bao lõi (tọa độ ROI)
        core = (self.core_w[t0:t1, u0:u1, 0] > 0.8)
        if not core.any():
            return img
        if reset:
            self._donor_pick, self._tex_age = None, 0

        def gray_hf(win):
            if win.ndim == 2:   # mặt phẳng luma limited-range (16..235) -> thang 0..255 như BGR
                y = (win.astype(np.float32) - 16.0) * (255.0 / 219.0)
            else:
                y = cv2.cvtColor(win, cv2.COLOR_BGR2GRAY).astype(np.float32)
            return y, y - cv2.GaussianBlur(y, (0, 0), 2.5)

        # thống kê vùng hiện tại: lõi trong hộp, vành đai trên ROI (cần rộng hơn hộp)
        box = np.ascontiguousarray(np.clip(img[t0:t1, u0:u1], 0, 255).astype(np.uint8))
        cur_y, cur_hf = gray_hf(box)
        core_s = float(np.median(np.abs(cur_hf[core]))) / 0.6745
        ring_y = cv2.cvtColor(np.clip(img, 0, 255).astype(np.uint8), cv2.COLOR_BGR2GRAY).astype(np.float32)
        ring_hf = ring_y - cv2.GaussianBlur(ring_y, (0, 0), 2.5)
        ring_mean = float(ring_y[self.ring_sel].mean())
        ring_s = float(np.median(np.abs(ring_hf[self.ring_sel]))) / 0.6745
        deficit = ring_s ** 2 - core_s ** 2
        if deficit <= 0.04:
            return img

        def donor_hf(dx, dy):
            win = frame[y1 + dy + t0:y1 + dy + t1, x1 + dx + u0:x1 + dx + u1]
            return gray_hf(win)

        # Chấm điểm toàn bộ donor chỉ khi bắt đầu cảnh / định kỳ; các frame còn lại giữ donor cũ (vân ổn định)
        if self._donor_pick is None or self._tex_age >= 12:
            best = None
            for dx, dy in cands:
                y, hf = donor_hf(dx, dy)
                sc = abs(float(y[core].mean()) - ring_mean) + 3.0 * abs(float(np.median(np.abs(hf[core]))) / 0.6745 - ring_s)
                if best is None or sc < best[0]:
                    best = (sc, (dx, dy))
            if self._donor_pick is None or best[0] < 0.7 * self._score_pick:
                self._donor_pick, self._score_pick = best[1], best[0]
            self._tex_age = 0
        self._tex_age += 1

        _, hf = donor_hf(*self._donor_pick)
        d_s = float(np.median(np.abs(hf[core]))) / 0.6745
        if d_s < 1e-3:
            return img
        lim = 2.5 * d_s
        hf = np.clip(hf, -lim, lim)           # triệt biên mạnh (cạnh da/vật thể) khỏi bị sao chép
        k = min(1.5, np.sqrt(deficit) / d_s)
        out = img.copy()
        out[t0:t1, u0:u1] += (hf * k * self._tex_w[t0:t1, u0:u1])[:, :, np.newaxis]
        return out

    def _soft(self, mask: np.ndarray) -> np.ndarray:
        """Mặt nạ mềm (Gaussian feathering) trong ROI để hòa trộn không lộ viền."""
        x1, y1, x2, y2 = self.roi
        return cv2.GaussianBlur(mask[y1:y2, x1:x2].astype(np.float32) / 255.0, (5, 5), 1.0)[:, :, np.newaxis]

    def _scan_intro(self) -> int:
        """
        Trả về chỉ số frame cuối cùng còn ngôi sao phụ (-1 nếu video không có).
        Ngôi sao phụ chỉ xuất hiện ở cảnh đầu: xác nhận sự hiện diện ở frame 0 bằng độ tương
        phản so với vùng xung quanh, rồi tìm điểm cắt cảnh đầu tiên.
        """
        cap = cv2.VideoCapture(self.input_path)
        ret, first = cap.read()
        if not ret:
            cap.release()
            return -1

        star2_only = cv2.subtract(self.mask_union, cv2.dilate(self.mask_star1, np.ones((9, 9), np.uint8)))
        ring = cv2.subtract(
            cv2.dilate(star2_only, np.ones((25, 25), np.uint8)),
            cv2.dilate(self.mask_union, np.ones((9, 9), np.uint8)),
        )
        core = cv2.erode(star2_only, np.ones((9, 9), np.uint8))  # lõi sao phụ, tránh viền mặt nạ
        if core.sum() == 0 or ring.sum() == 0:
            cap.release()
            return -1
        gray = cv2.cvtColor(first, cv2.COLOR_BGR2GRAY).astype(np.float32)
        if gray[core > 0].mean() - gray[ring > 0].mean() < 12.0:
            cap.release()
            return -1

        def small_gray(img):
            return cv2.resize(cv2.cvtColor(img, cv2.COLOR_BGR2GRAY), (96, 54), interpolation=cv2.INTER_AREA).astype(np.float32)

        prev = small_gray(first)
        limit = int(4 * self.fps)
        last = limit  # không thấy cắt cảnh trong 4s đầu thì giữ đến hết 4s
        for i in range(1, limit):
            ret, f = cap.read()
            if not ret:
                last = i - 1
                break
            cur = small_gray(f)
            if float(np.abs(cur - prev).mean()) > 20.0:  # cắt cảnh
                last = i - 1
                break
            prev = cur
        cap.release()
        return last

    # ------------------------------------------------------------------
    # Lõi khử logo
    # ------------------------------------------------------------------
    def clean_roi(self, roi_bgr: np.ndarray, intro: bool = False, temporal: bool = False,
                  frame: Optional[np.ndarray] = None) -> np.ndarray:
        """
        Khử logo trên vùng ROI (BGR uint8).
        - Có alpha map: Reverse Alpha Blending, sau đó lọc median dải viền còn sót (+ inpaint sao phụ ở intro).
        - Không có alpha map: inpaint toàn bộ mặt nạ (phương pháp thuần inpainting).
        temporal=True: bật lọc thời gian (dùng khi xử lý tuần tự các frame liên tiếp).
        frame: khung hình đầy đủ (chưa sửa) để lấy texture từ vùng lân cận; None thì bỏ bước này.
        """
        x1, y1, x2, y2 = self.roi
        flag = cv2.INPAINT_TELEA if self.inpaint_method == "telea" else cv2.INPAINT_NS
        radius = self.inpaint_radius or 2

        if self.alpha is None:
            return cv2.inpaint(roi_bgr, self.mask_union[y1:y2, x1:x2], radius, flag)

        a = self.alpha[y1:y2, x1:x2]
        if self.model_a is not None:
            restored = (roi_bgr.astype(np.float32) - self.model_c) / (1.0 - self.model_a)
        else:
            restored = (roi_bgr.astype(np.float32) - a * 255.0) / (1.0 - a)
        restored = np.clip(self._match_boundary(restored), 0, 255).astype(np.uint8)
        # Median giữ biên (da/nền) tốt hơn inpaint: không kéo màu tối từ xa vào mũi sao
        w = self.band_w[y1:y2, x1:x2, np.newaxis]
        cleaned = (cv2.medianBlur(restored, self.BAND_MEDIAN) * w + restored * (1.0 - w))
        # Nền mịn (ít vân, ít biên) thì đường viền mảnh còn sót rất dễ thấy, nhưng cũng rất dễ xóa sạch:
        # nội suy dải viền từ vùng sạch hai bên. Nền có vân / có biên thật thì giữ nguyên (alpha ~ 0).
        alpha = self._smooth_alpha(restored)
        if alpha > 0.0:
            est = cv2.inpaint(restored, self._band_mask, 3, cv2.INPAINT_TELEA).astype(np.float32)
            wb = w * alpha
            cleaned = cleaned * (1.0 - wb) + est * wb
        cleaned = np.clip(cleaned, 0, 255).astype(np.uint8)
        if intro:
            # Inpaint chỉ trong hộp bao của sao phụ (nhanh hơn nhiều so với cả ROI)
            ys, xs = np.where(self.mask_star2[y1:y2, x1:x2] > 0)
            if len(xs):
                pad = 8
                h, w = cleaned.shape[:2]
                by0, by1 = max(0, int(ys.min()) - pad), min(h, int(ys.max()) + pad + 1)
                bx0, bx1 = max(0, int(xs.min()) - pad), min(w, int(xs.max()) + pad + 1)
                sub = np.ascontiguousarray(cleaned[by0:by1, bx0:bx1])
                cleaned[by0:by1, bx0:bx1] = cv2.inpaint(sub, np.ascontiguousarray(self.mask_star2[y1:y2, x1:x2][by0:by1, bx0:bx1]), radius, flag)
        return self._denoise(cleaned, intro, temporal, frame)

    def _smooth_alpha(self, restored: np.ndarray) -> float:
        """Mức nội suy dải viền (0..1) theo độ mịn của vành đai quanh logo; giảm khi có biên/gradient mạnh."""
        g = cv2.cvtColor(restored, cv2.COLOR_BGR2GRAY).astype(np.float32)
        ring = self.ring_sel
        hf = g - cv2.GaussianBlur(g, (0, 0), 2.5)
        s = float(np.median(np.abs(hf[ring]))) / 0.6745                     # độ nhám (vân)
        e = float(cv2.GaussianBlur(g, (0, 0), 3.0)[ring].std())              # biến thiên chậm (biên/gradient)
        a_tex = float(np.clip((2.2 - s) / 1.4, 0.0, 1.0))
        a_edge = float(np.clip(1.2 - e / 30.0, self.EDGE_ALPHA_FLOOR, 1.0))
        # Sai số của mô hình logo bị nhân lên theo độ sáng nền: nền tối (dưới ~70) vệt không thể thấy và nội suy
        # chỉ tạo bước lệch nhỏ -> chỉ bật khi nền đủ sáng.
        a_bright = float(np.clip((float(g[ring].mean()) - 70.0) / 50.0, 0.0, 1.0))
        return a_tex * a_edge * a_bright

    def _read_frame(self, t: float) -> np.ndarray:
        cap = cv2.VideoCapture(self.input_path)
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ret, frame = cap.read()
        if not ret or frame is None:
            cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
            ret, frame = cap.read()
        cap.release()
        if not ret or frame is None:
            raise RuntimeError("Không đọc được khung hình từ video.")
        return frame

    def preview_frame(
        self,
        frame_time_sec: float = 2.0,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        use_exact_mask: bool = True,
    ) -> Tuple[np.ndarray, np.ndarray]:
        """Trích một khung hình, trả về (ảnh gốc đã đánh dấu vùng logo, ảnh đã xóa logo)."""
        frame = self._read_frame(frame_time_sec)
        marked_frame = frame.copy()

        if use_exact_mask:
            intro = int(frame_time_sec * self.fps) <= self.intro_last_frame
            cur_mask = self.mask_union if intro else self.mask_star1
            label = "Google Flow: 2 Stars (Intro)" if intro else "Google Flow: 1 Star"
            contours, _ = cv2.findContours(cur_mask, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
            cv2.drawContours(marked_frame, contours, -1, (0, 255, 0), 2)
            cv2.putText(
                marked_frame, label,
                (int(self.width * 0.78), int(self.height * 0.77)),
                cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2,
            )
            x1, y1, x2, y2 = self.roi
            cleaned_frame = frame.copy()
            cleaned_frame[y1:y2, x1:x2] = self.clean_roi(frame[y1:y2, x1:x2], intro, frame=frame)
        else:
            if bbox is None:
                bbox = self.get_preset_bbox()
            x, y, w, h = bbox
            cv2.rectangle(marked_frame, (x, y), (x + w, y + h), (0, 255, 0), 2)
            cleaned_frame = self.inpaint_single_frame(frame.copy(), bbox)

        return marked_frame, cleaned_frame

    def inpaint_frame_with_mask(self, frame: np.ndarray, mask: np.ndarray) -> np.ndarray:
        """Inpaint theo mặt nạ bất kỳ với Soft Feathered Blending để triệt tiêu viền mép."""
        fh, fw = frame.shape[:2]
        ys, xs = np.where(mask > 0)
        if len(xs) == 0:
            return frame

        pad = 20
        x1, y1 = max(0, int(np.min(xs)) - pad), max(0, int(np.min(ys)) - pad)
        x2, y2 = min(fw, int(np.max(xs)) + pad), min(fh, int(np.max(ys)) + pad)

        roi_frame = frame[y1:y2, x1:x2].copy()
        roi_mask = mask[y1:y2, x1:x2]

        flag = cv2.INPAINT_TELEA if self.inpaint_method == "telea" else cv2.INPAINT_NS
        cleaned_roi = cv2.inpaint(roi_frame, roi_mask, inpaintRadius=self.inpaint_radius or 2, flags=flag)

        soft_mask = cv2.GaussianBlur(roi_mask.astype(np.float32) / 255.0, (5, 5), 1.0)[:, :, np.newaxis]
        blended = (cleaned_roi.astype(np.float32) * soft_mask + roi_frame.astype(np.float32) * (1.0 - soft_mask)).astype(np.uint8)

        frame[y1:y2, x1:x2] = blended
        return frame

    def inpaint_single_frame(self, frame: np.ndarray, bbox: Tuple[int, int, int, int]) -> np.ndarray:
        """Inpaint bằng bounding box chữ nhật tùy chỉnh có làm mềm biên."""
        x, y, w, h = bbox
        fh, fw = frame.shape[:2]
        mask = np.zeros((fh, fw), dtype=np.uint8)
        mask[max(0, y):min(fh, y + h), max(0, x):min(fw, x + w)] = 255
        return self.inpaint_frame_with_mask(frame, mask)

    def process(
        self,
        bbox: Optional[Tuple[int, int, int, int]] = None,
        use_exact_mask: bool = True,
        start_time_sec: float = 0.0,
        end_time_sec: Optional[float] = None,
        progress_callback: Optional[Callable[[int, int, float], None]] = None,
    ) -> str:
        """
        Xử lý video theo luồng YUV 4:2:0 gốc:
          - FFmpeg giải mã ra YUV420 thô, chỉ vùng ROI quanh logo được chuyển sang BGR để xử lý;
          - phần THAY ĐỔI (sau - trước, cùng đi qua một phép chuyển màu) được cộng ngược vào YUV gốc,
            nên mọi pixel ngoài logo giữ nguyên như video gốc (không bị lệch màu/độ sáng do BGR<->YUV);
          - FFmpeg nén H.264 một lần, ghép âm thanh gốc.
        Nếu use_exact_mask=False thì inpaint hình chữ nhật `bbox` (chế độ thủ công).
        """
        if self.width % 2 or self.height % 2:
            raise ValueError("Video có kích thước lẻ, H.264 4:2:0 không hỗ trợ.")

        flag = cv2.INPAINT_TELEA if self.inpaint_method == "telea" else cv2.INPAINT_NS
        radius = self.inpaint_radius or 2
        W, H = self.width, self.height

        if use_exact_mask:
            rx1, ry1, rx2, ry2 = self.roi
        else:
            if bbox is None:
                bbox = self.get_preset_bbox()
            bx, by, bw, bh = bbox
            rx1, ry1, rx2, ry2 = self._align_roi(bx - 20, by - 20, bx + bw + 20, by + bh + 20)
            manual = np.zeros((ry2 - ry1, rx2 - rx1), dtype=np.uint8)
            manual[max(0, by - ry1):min(ry2 - ry1, by + bh - ry1), max(0, bx - rx1):min(rx2 - rx1, bx + bw - rx1)] = 255
            manual_soft = cv2.GaussianBlur(manual.astype(np.float32) / 255.0, (5, 5), 1.0)[:, :, np.newaxis]
        rh, rw = ry2 - ry1, rx2 - rx1

        start_frame = int(start_time_sec * self.fps)
        if end_time_sec is not None and end_time_sec > 0:
            end_frame = min(self.total_frames, int(end_time_sec * self.fps))
        else:
            end_frame = self.total_frames
        frames_to_process = max(1, end_frame - start_frame)

        dec = self._open_decoder(start_time_sec, frames_to_process)
        enc = self._open_encoder(start_time_sec, frames_to_process / self.fps)

        y_size, c_size = W * H, (W // 2) * (H // 2)
        frame_size = y_size + 2 * c_size
        read_q: "queue.Queue" = queue.Queue(maxsize=8)
        write_q: "queue.Queue" = queue.Queue(maxsize=8)
        errors = []

        def reader():
            try:
                while True:
                    buf = bytearray(frame_size)
                    mv, got = memoryview(buf), 0
                    while got < frame_size:
                        n = dec.stdout.readinto(mv[got:])
                        if not n:
                            break
                        got += n
                    if got < frame_size:
                        break
                    read_q.put(buf)
            except Exception as e:  # noqa: BLE001
                errors.append(e)
            finally:
                read_q.put(None)

        def writer():
            try:
                while True:
                    item = write_q.get()
                    if item is None:
                        break
                    enc.stdin.write(item)
            except Exception as e:  # noqa: BLE001  (ví dụ FFmpeg tắt đột ngột)
                errors.append(e)
                while write_q.get() is not None:   # xả hàng đợi để luồng chính không bị kẹt
                    pass

        t_read = threading.Thread(target=reader, daemon=True)
        t_write = threading.Thread(target=writer, daemon=True)
        t_read.start()
        t_write.start()

        def to_bgr(y, u, v):
            """ROI I420 -> BGR (BT.601 limited, đúng với video nguồn thông dụng)."""
            return cv2.cvtColor(np.vstack([y, u.reshape(rh // 4, rw), v.reshape(rh // 4, rw)]), cv2.COLOR_YUV2BGR_I420)

        def from_bgr(bgr):
            i420 = cv2.cvtColor(bgr, cv2.COLOR_BGR2YUV_I420).astype(np.int16)
            return i420[:rh], i420[rh:rh + rh // 4].reshape(rh // 2, rw // 2), i420[rh + rh // 4:].reshape(rh // 2, rw // 2)

        start_time = time.time()
        processed_count = 0
        self._prev_roi = None
        self._donor_pick = None

        try:
            while True:
                buf = read_q.get()
                if buf is None:
                    break
                arr = np.frombuffer(buf, dtype=np.uint8)
                Y = arr[:y_size].reshape(H, W)
                U = arr[y_size:y_size + c_size].reshape(H // 2, W // 2)
                V = arr[y_size + c_size:].reshape(H // 2, W // 2)

                y_roi = np.ascontiguousarray(Y[ry1:ry2, rx1:rx2])
                u_roi = np.ascontiguousarray(U[ry1 // 2:ry2 // 2, rx1 // 2:rx2 // 2])
                v_roi = np.ascontiguousarray(V[ry1 // 2:ry2 // 2, rx1 // 2:rx2 // 2])
                bgr = to_bgr(y_roi, u_roi, v_roi)

                if use_exact_mask:
                    intro = (start_frame + processed_count) <= self.intro_last_frame
                    new_bgr = self.clean_roi(bgr, intro, temporal=True, frame=Y)   # luma toàn khung làm nguồn texture
                else:
                    cleaned = cv2.inpaint(bgr, manual, radius, flag)
                    new_bgr = (cleaned.astype(np.float32) * manual_soft + bgr.astype(np.float32) * (1.0 - manual_soft)).astype(np.uint8)

                # Delta-domain: (sau xử lý) - (trước xử lý, cùng phép chuyển màu) cộng vào YUV gốc.
                yo, uo, vo = from_bgr(bgr)
                yn, un, vn = from_bgr(new_bgr)
                Y[ry1:ry2, rx1:rx2] = np.clip(y_roi.astype(np.int16) + (yn - yo), 0, 255).astype(np.uint8)
                U[ry1 // 2:ry2 // 2, rx1 // 2:rx2 // 2] = np.clip(u_roi.astype(np.int16) + (un - uo), 0, 255).astype(np.uint8)
                V[ry1 // 2:ry2 // 2, rx1 // 2:rx2 // 2] = np.clip(v_roi.astype(np.int16) + (vn - vo), 0, 255).astype(np.uint8)

                write_q.put(buf)
                processed_count += 1

                if progress_callback and (processed_count % 15 == 0 or processed_count == frames_to_process):
                    elapsed = max(0.001, time.time() - start_time)
                    progress_callback(processed_count, frames_to_process, processed_count / elapsed)
        finally:
            write_q.put(None)
            t_write.join()
            for pipe in (dec.stdout,):
                try:
                    pipe.close()
                except Exception:  # noqa: BLE001
                    pass
            dec.terminate()
            dec.wait()
            try:
                enc.stdin.close()
            except Exception:  # noqa: BLE001
                pass
            enc.wait()

        if enc.returncode != 0 or errors:
            err = ""
            try:
                enc.stderr_file.seek(0)
                err = enc.stderr_file.read().decode("utf-8", errors="replace")[-500:]
            except Exception:  # noqa: BLE001
                pass
            raise RuntimeError(f"FFmpeg lỗi khi xuất video: {err or errors}")
        enc.stderr_file.close()
        dec.stderr_file.close()
        return self.output_path

    def _source_color_info(self) -> dict:
        """Đọc thông số màu của video gốc (ma trận, dải, hàm truyền, hệ màu) để đầu ra giữ đúng nhãn."""
        try:
            out = subprocess.run(
                ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
                 "stream=color_space,color_range,color_transfer,color_primaries", "-of", "default=nw=1",
                 self.input_path],
                capture_output=True, text=True, timeout=20,
            ).stdout
        except Exception:  # noqa: BLE001
            return {}
        info = {}
        for line in out.splitlines():
            k, _, v = line.partition("=")
            if v and v != "unknown":
                info[k.strip()] = v.strip()
        return info

    def _open_decoder(self, start_time_sec: float, n_frames: int) -> subprocess.Popen:
        """Mở FFmpeg giải mã video gốc ra YUV420 thô (không đổi không gian màu nếu nguồn đã là yuv420p)."""
        cmd = ["ffmpeg", "-v", "error", "-ss", str(start_time_sec), "-i", self.input_path,
               "-map", "0:v:0", "-frames:v", str(n_frames), "-f", "rawvideo", "-pix_fmt", "yuv420p", "-"]
        err_file = tempfile.TemporaryFile()
        try:
            proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=err_file, bufsize=0)
        except FileNotFoundError:
            raise RuntimeError("Không tìm thấy FFmpeg. Hãy cài FFmpeg và thêm vào PATH.")
        proc.stderr_file = err_file
        return proc

    def _open_encoder(self, start_time_sec: float, duration_sec: float) -> subprocess.Popen:
        """Mở FFmpeg: nhận YUV420 thô qua stdin, ghép âm thanh gốc, mã hóa H.264 (CRF 18), giữ nhãn màu nguồn."""
        col = self._source_color_info()
        color_flags = []
        for key, flag in (("color_space", "-colorspace"), ("color_primaries", "-color_primaries"),
                          ("color_transfer", "-color_trc"), ("color_range", "-color_range")):
            if key in col:
                color_flags += [flag, col[key]]
        cmd = [
            "ffmpeg", "-y", "-loglevel", "error",
            "-f", "rawvideo", "-pix_fmt", "yuv420p",
            "-s", f"{self.width}x{self.height}", "-framerate", f"{self.fps}",
            "-i", "-",
            "-ss", str(start_time_sec), "-i", self.input_path,
            "-t", f"{duration_sec:.6f}",
            "-map", "0:v:0", "-map", "1:a:0?",
            "-c:v", "libx264", "-threads", str(self.ENCODE_THREADS), "-crf", "18", "-preset", self.ENCODE_PRESET,
            "-pix_fmt", "yuv420p", *color_flags,
            "-c:a", "copy", "-shortest",
            "-movflags", "+faststart",
            self.output_path,
        ]
        err_file = tempfile.TemporaryFile()
        try:
            proc = subprocess.Popen(cmd, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=err_file)
        except FileNotFoundError:
            raise RuntimeError("Không tìm thấy FFmpeg. Hãy cài FFmpeg và thêm vào PATH.")
        proc.stderr_file = err_file
        return proc


def main():
    parser = argparse.ArgumentParser(
        description="Tool tự động xóa Watermark / Logo cho video Google Flow bằng Reverse Alpha Blending, OpenCV Inpainting & FFmpeg",
    )
    parser.add_argument("--input", "-i", type=str, required=True, help="Đường dẫn file video đầu vào")
    parser.add_argument("--output", "-o", type=str, default=None, help="Đường dẫn file video xuất ra")
    parser.add_argument("--ratio", "-r", type=str, choices=["16:9", "9:16", "auto"], default="auto", help="Tỉ lệ video")
    parser.add_argument("--method", "-m", type=str, choices=["telea", "ns"], default="telea", help="Thuật toán inpaint (telea/ns)")
    parser.add_argument("--start", "-s", type=float, default=0.0, help="Thời điểm bắt đầu (giây)")
    parser.add_argument("--end", "-e", type=float, default=None, help="Thời điểm kết thúc (giây)")
    parser.add_argument("--bbox", type=str, default=None, help="Tọa độ tùy chỉnh dạng x,y,w,h (ví dụ 1700,860,80,80)")

    args = parser.parse_args()

    remover = VideoWatermarkRemover(
        input_path=args.input,
        output_path=args.output,
        inpaint_method=args.method,
    )

    print("==================================================")
    print("🎬 VIDEO WATERMARK REMOVER (GOOGLE FLOW / VEO)")
    print("==================================================")
    print(f"📁 Video vào     : {remover.input_path}")
    print(f"📐 Kích thước    : {remover.width}x{remover.height}")
    print(f"⏱️  Thời lượng    : {remover.duration:.2f}s ({remover.total_frames} frames @ {remover.fps:.1f} fps)")
    print(f"🎯 Tỉ lệ nhận dạng: {remover.aspect_ratio_str}")

    use_exact = (args.bbox is None)
    bbox = None
    if args.bbox:
        parts = [int(p.strip()) for p in args.bbox.split(",")]
        bbox = (parts[0], parts[1], parts[2], parts[3])
        print(f"📦 Vùng xóa logo : Tùy chỉnh (x={bbox[0]}, y={bbox[1]}, w={bbox[2]}, h={bbox[3]})")
    else:
        if remover.alpha is not None:
            extra = (f", sao phụ ở intro đến frame {remover.intro_last_frame}"
                     if remover.intro_last_frame >= 0 else "")
            print(f"📦 Vùng xóa logo : Reverse Alpha Blending (alpha map Google Flow){extra}")
        else:
            bbox = remover.get_preset_bbox(None if args.ratio == "auto" else args.ratio)
            print(f"📦 Vùng xóa logo : Preset {remover.aspect_ratio_str} (x={bbox[0]}, y={bbox[1]}, w={bbox[2]}, h={bbox[3]})")
            use_exact = False

    print(f"⚙️  Thuật toán    : {args.method.upper()} (inpaint) {'+ Reverse Alpha' if use_exact and remover.alpha is not None else ''}")
    print("🚀 Đang xử lý...")

    def on_progress(cur, total, fps):
        pct = (cur / total) * 100
        print(f"\r   Tiến độ: {cur}/{total} frames ({pct:.1f}%) - Tốc độ: {fps:.1f} FPS", end="", flush=True)

    out_file = remover.process(
        bbox=bbox,
        use_exact_mask=use_exact,
        start_time_sec=args.start,
        end_time_sec=args.end,
        progress_callback=on_progress,
    )
    print(f"\n✅ Hoàn tất! Video xuất tại: {out_file}")


if __name__ == "__main__":
    main()
