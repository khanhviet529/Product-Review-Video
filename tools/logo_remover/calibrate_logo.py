"""
Hiệu chỉnh mô hình logo từng pixel từ chính video.

Mô hình lớp phủ:   I = (1 - a) * B + c        (a: độ đục, c = a * độ sáng logo)

Với mỗi pixel, mỗi quan sát (frame hoặc nhóm frame) cho một cặp (B, I): B là nền thật dưới logo, I là pixel
quan sát được. Nhiều quan sát ở NHIỀU MỨC NỀN khác nhau thì khớp được đường thẳng I = k*B + c bằng bình phương
tối thiểu, với k = 1 - a. Càng có điểm ở nền sáng thì sai số của mô hình càng nhỏ khi xóa logo trên nền sáng.

Hai kiểu quan sát (cách biết nền B):
  flat   : nền phẳng gần như hằng số quanh logo (cảnh đen cuối clip, frame xám phẳng lúc chuyển cảnh):
           B = mức trung bình ở vành đai quanh logo.
  smooth : nền trơn nhưng không hằng số: B = đa thức bậc 2 khớp bền vững (loại ngoại lai) trên vành đai.

Logo neo ở góc dưới phải nên nhiều video (ngang/dọc) dùng chung một mô hình; các video được căn theo góc đó.

Dùng:
  python calibrate_logo.py \\
      --obs flat   input/a.mp4 200 240 \\
      --obs flat   input/a.mp4 171 173 \\
      --obs smooth input/b.mp4 55 57
Kết quả: assets/star_model_1080p.npz (a, c, góc ROI) được watermark_remover.py tự nạp.
"""

import os
import argparse
import cv2
import numpy as np

from watermark_remover import VideoWatermarkRemover


def _read_frames(video: str, lo: int, hi: int):
    cap = cv2.VideoCapture(video)
    cap.set(cv2.CAP_PROP_POS_FRAMES, lo)
    out = []
    for _ in range(hi - lo):
        ok, f = cap.read()
        if not ok:
            break
        out.append(f.astype(np.float32))
    cap.release()
    if not out:
        raise RuntimeError(f"Không đọc được frame {lo}-{hi} của {video}")
    return out


def _robust_poly_background(frames, ring, region_xy, centre):
    """B (theo kênh) = đa thức bậc 2 khớp bền vững trên vành đai, tính tại các pixel của vùng logo."""
    cx, cy = centre
    ys, xs = np.where(ring)

    def feats(x, y):
        x = (x - cx) / 40.0
        y = (y - cy) / 40.0
        return np.stack([np.ones_like(x), x, y, x * x, x * y, y * y], -1)

    A = feats(xs.astype(np.float32), ys.astype(np.float32))
    ry, rx = region_xy
    AL = feats(rx.astype(np.float32), ry.astype(np.float32))
    f_mean = np.mean(frames, 0)
    B = np.zeros(f_mean.shape[:2] + (3,), np.float32)
    mad = 0.0
    for ch in range(3):
        v = f_mean[ys, xs, ch]
        w = np.ones_like(v)
        for _ in range(6):                                  # IRLS kiểu Huber
            coef = np.linalg.lstsq(A * w[:, None], v * w, rcond=None)[0]
            res = v - A @ coef
            mad = np.median(np.abs(res)) / 0.6745 + 1e-3
            w = np.minimum(1.0, 1.5 * mad / (np.abs(res) + 1e-6))
        B[ry, rx, ch] = AL @ coef
    return B, float(mad)


def calibrate(observations, out_path: str) -> str:
    """observations: danh sách (mode, video, frame_bắt_đầu, frame_kết_thúc)."""
    # Ô tham chiếu: ROI của video đầu tiên, đổi sang tọa độ chuẩn 1920x1080 (neo góc dưới phải)
    r0 = VideoWatermarkRemover(observations[0][1])
    sc0 = r0._logo_scale()
    x1, y1, x2, y2 = r0.roi
    ref = (r0.REF_W - (r0.width - x1) / sc0, r0.REF_H - (r0.height - y1) / sc0)
    size = (x2 - x1, y2 - y1)
    ones = lambda k: np.ones((k, k), np.uint8)

    pts_I, pts_B, labels = [], [], []
    for mode, video, lo, hi in observations:
        r = VideoWatermarkRemover(video)
        if r.alpha is None:
            raise RuntimeError("Cần assets/star_alpha_1080p.png để định vị logo.")
        sc = r._logo_scale()
        vx = int(round(r.width - (r.REF_W - ref[0]) * sc))
        vy = int(round(r.height - (r.REF_H - ref[1]) * sc))
        m1 = r.mask_star1
        if mode == "flat":
            ring_full = (cv2.dilate(m1, ones(31)) - cv2.dilate(m1, ones(11))) > 0
        else:
            ring_full = (cv2.dilate(m1, ones(41)) - cv2.dilate(m1, ones(13))) > 0
        frames = _read_frames(video, lo, hi)
        I = np.mean(frames, 0)
        if mode == "flat":
            ring_vals = np.concatenate([f[ring_full] for f in frames])
            B_level, sd = ring_vals.mean(0), ring_vals.std(0)
            if sd.max() > 3.0:
                print(f"CẢNH BÁO: {video} [{lo},{hi}) nền không phẳng (std {sd.max():.1f}).")
            B = np.broadcast_to(B_level, I.shape).astype(np.float32)
            note = f"B={np.round(B_level, 1)}"
        else:
            ly, lx = np.where(m1 > 0)
            B, mad = _robust_poly_background(frames, ring_full, (ly, lx), (lx.mean(), ly.mean()))
            note = f"B~{B[ly, lx].mean():.1f} (MAD vanh dai {mad:.2f})"
            if mad > 2.0:
                print(f"CẢNH BÁO: {video} [{lo},{hi}) nền không đủ trơn (MAD {mad:.1f}); kết quả kém tin cậy.")
        pts_I.append(I[vy:vy + size[1], vx:vx + size[0]])
        pts_B.append(B[vy:vy + size[1], vx:vx + size[0]])
        labels.append(f"{mode} {os.path.basename(video)}[{lo},{hi}) {note}")
    for lab in labels:
        print(" -", lab)

    Is, Bs = np.stack(pts_I), np.stack(pts_B)                 # (n, h, w, 3)
    n = len(Is)
    if n < 2 or np.ptp(Bs.mean((1, 2, 3))) < 25:
        raise RuntimeError("Cần ít nhất hai mức nền cách nhau > 25 để giải a, c.")
    mB, mI = Bs.mean(0), Is.mean(0)
    k = ((Bs - mB) * (Is - mI)).sum(0) / (((Bs - mB) ** 2).sum(0) + 1e-6)     # = 1 - a
    c = mI - k * mB
    a = 1.0 - k
    if n >= 3:
        resid = np.abs(Is - (k * Bs + c)).mean()
        print(f"Sai so khop duong thang (trung binh, muc xam): {resid:.2f}")

    # Giảm nhiễu nén ở LÕI (phẳng); sát viền / mũi sao giữ dữ liệu thô để không làm mờ đỉnh nhọn của rim
    m1 = r0.mask_star1
    dist = cv2.distanceTransform(m1, cv2.DIST_L2, 3)[y1:y2, x1:x2]
    w_in = np.clip((dist - 3.0) / 3.0, 0.0, 1.0)[:, :, None]
    a = a * (1 - w_in) + np.stack([cv2.GaussianBlur(a[:, :, j], (0, 0), 2.0) for j in range(3)], 2) * w_in
    c = c * (1 - w_in) + np.stack([cv2.GaussianBlur(c[:, :, j], (0, 0), 2.0) for j in range(3)], 2) * w_in

    # Logo trung tính (xám/trắng): dùng chung a, c cho 3 kênh. Chênh lệch giữa các kênh chỉ là nhiễu hiệu chỉnh
    # và bị khuếch đại thành đốm màu ở mũi sao khi nền sáng.
    a = np.repeat(a.mean(2, keepdims=True), 3, axis=2)
    c = np.repeat(c.mean(2, keepdims=True), 3, axis=2)

    # Ngoài vùng logo (quá 2px) thì không có lớp phủ
    near = cv2.dilate(m1, ones(5))[y1:y2, x1:x2] > 0
    a = np.where(near[:, :, None], np.clip(a, 0.0, 0.9), 0.0).astype(np.float32)
    c = np.where(near[:, :, None], np.clip(c, 0.0, 255.0), 0.0).astype(np.float32)
    core = r0.core_w[:, :, 0] > 0.9
    print(f"a loi = {a[:, :, 0][core].mean():.3f}   c loi = {c[:, :, 0][core].mean():.1f}")

    np.savez_compressed(out_path, a=a, c=c, origin=np.array([round(ref[0]), round(ref[1])]),
                        size=np.array([r0.width, r0.height]))
    return out_path


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description="Hiệu chỉnh alpha/độ sáng logo từ nhiều mức nền")
    ap.add_argument("--obs", nargs=4, action="append", metavar=("MODE", "VIDEO", "START", "END"), required=True,
                    help="quan sát: MODE = flat|smooth, VIDEO, khoảng frame [START, END)")
    ap.add_argument("--out", default=os.path.join(VideoWatermarkRemover.ASSET_DIR, "star_model_1080p.npz"))
    args = ap.parse_args()
    obs = [(m, v, int(s), int(e)) for m, v, s, e in args.obs]
    print("Đã lưu:", calibrate(obs, args.out))
