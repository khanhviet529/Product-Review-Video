"""
Điều khiển giao diện Google Flow qua Chrome đang mở (cổng 9222). Mọi thao tác dựa trên chữ/nhãn của nút,
không dùng tọa độ cố định, nên chịu được việc đổi kích thước cửa sổ.

Chrome cần được mở trước bằng:  tools/flow/open_chrome.bat  (profile riêng, đăng nhập Google một lần).

Chốt chặn chi phí: generate() mặc định KHÔNG bấm tạo. Chỉ bấm khi gọi với confirm=True, và luôn kiểm tra
chi phí hiển thị trên giao diện có đúng kỳ vọng (mặc định 15 tín dụng/clip) trước khi bấm.
"""
import re
import sys
import time

from _cdp import CDP, dump, flow_page, shot, sync_playwright  # noqa: F401

PROJECT_URL = "https://flow.google.com/project/{pid}"


class Flow:
    def __init__(self, play, project_id=None):
        self.browser = play.chromium.connect_over_cdp(CDP)
        self.pg = flow_page(self.browser.contexts[0])
        if project_id and project_id not in self.pg.url:
            self.pg.goto(PROJECT_URL.format(pid=project_id))
            self.pg.wait_for_timeout(4000)

    # ---- cơ bản
    def settle(self, ms=900):
        self.pg.wait_for_timeout(ms)

    def snap(self, path):
        shot(self.pg, path)

    def go_project_home(self):
        """Về màn hình chính của dự án (có ô nhập câu lệnh)."""
        self.pg.keyboard.press("Escape")
        if self.pg.get_by_role("button", name="Quay lại").count():
            self.pg.get_by_role("button", name="Quay lại").first.click()
            self.settle(1500)

    def _open_settings(self):
        if not self.pg.get_by_role("radio", name=re.compile("Video")).count():
            self.pg.get_by_role("button", name="Điều kiện kích hoạt cài đặt").click()
            self.settle(900)

    def _radio(self, pattern):
        return self.pg.get_by_role("radio", name=re.compile(pattern))

    def _checked(self, pattern):
        loc = self._radio(pattern)
        return loc.count() > 0 and loc.first.get_attribute("aria-checked") == "true"

    # ---- cài đặt video
    def set_video_settings(self, ratio="9:16", res="720p", seconds=8, count=1):
        """Chọn Video + Thành phần + khổ + độ phân giải + thời lượng + số kết quả."""
        self._open_settings()
        for pat in ("Video", "Thành phần", re.escape(ratio), re.escape(res), f"{seconds} giây", f"x{count}"):
            if not self._checked(pat):
                self._radio(pat).first.click()
                self.settle(500)
        self.pg.keyboard.press("Escape")
        self.settle(500)

    def read_cost(self):
        """Đọc chi phí hiển thị ('Quá trình tạo sẽ tốn N tín dụng') trong bảng cài đặt."""
        self._open_settings()
        txt = self.pg.evaluate("() => document.body.innerText")
        m = re.search(r"(\d+)\s*tín dụng", txt)
        self.pg.keyboard.press("Escape")
        return int(m.group(1)) if m else None

    # ---- nhân vật
    def _close_overlays(self):
        for _ in range(3):
            if not self.pg.locator(".cdk-overlay-backdrop-showing, [role=listbox]").count():
                break
            self.pg.keyboard.press("Escape")
            self.settle(400)

    def _open_picker(self, tab):
        self._close_overlays()
        self.pg.get_by_role("button", name="Thêm thành phần vào ô nhập câu lệnh").first.click()
        self.settle(1200)
        self.pg.get_by_role("tab", name=tab).click()
        self.settle(900)

    def _pick_by_name(self, name):
        """Trong bộ chọn đang mở: lọc theo tên, bấm đúng 1 dòng khớp, bấm 'Thêm vào câu lệnh'. False nếu không thấy."""
        box = self.pg.get_by_placeholder("Tìm kiếm thành phần")
        box.click()
        box.fill(name)
        self.settle(1300)
        pos = self.pg.evaluate(
            """(name) => { const rows = [...document.querySelectorAll('[role=listbox] *')]
                 .filter(e => e.children.length == 0 && (e.innerText || '').trim().replace(/\.[a-z0-9]+$/i, '') === name.replace(/\.[a-z0-9]+$/i, ''));
               if (!rows.length) return null; const r = rows[0].getBoundingClientRect(); return [r.x + r.width / 2, r.y + r.height / 2]; }""", name)
        if not pos:
            return False
        self.pg.mouse.click(*pos)
        self.settle(800)
        try:
            self.pg.get_by_role("button", name="Thêm vào câu lệnh").click(timeout=8000)
        except Exception:
            return False
        self.settle(1000)
        return True

    def add_character(self, name):
        """Gắn nhân vật (tab Nhân vật) theo tên vào câu lệnh."""
        self._open_picker("Nhân vật")
        ok = self._pick_by_name(name)
        self._close_overlays()
        if not ok:
            raise RuntimeError(f"Không gắn được nhân vật '{name}' (đã đặt tên trong dự án chưa?).")

    def add_asset(self, name):
        """Gắn ảnh đã tải lên (tab Tệp tải lên) theo tên file vào câu lệnh."""
        self._open_picker("Tệp tải lên")
        ok = self._pick_by_name(name)
        self._close_overlays()
        if not ok:
            raise RuntimeError(f"Không gắn được ảnh '{name}'. Hãy tải lên trước bằng upload_asset().")

    def upload_asset(self, path):
        """Tải một ảnh từ máy lên Flow (tab Tệp tải lên). Bỏ qua nếu đã có file cùng tên."""
        from pathlib import Path as _P
        name = _P(path).name
        self._open_picker("Tệp tải lên")
        box = self.pg.get_by_placeholder("Tìm kiếm thành phần")
        box.click()
        box.fill(_P(path).stem)
        self.settle(1200)
        exists = self.pg.evaluate(
            """(stem) => [...document.querySelectorAll('[role=listbox] *')].some(e => e.children.length == 0 && (e.innerText || '').includes(stem))""", _P(path).stem)
        if not exists:
            box.fill("")
            with self.pg.expect_file_chooser(timeout=15000) as fc:
                self.pg.get_by_role("button", name=re.compile("Tải nội dung nghe nhìn lên")).click()
            fc.value.set_files(str(path))
            self.settle(6000)
        self._close_overlays()
        return not exists

    def has_chip(self):
        return self.chip_count() > 0

    def clear_prompt(self):
        if self.pg.get_by_role("button", name="Xoá câu lệnh").count():
            self.pg.get_by_role("button", name="Xoá câu lệnh").first.click()
            self.settle(700)

    # ---- câu lệnh
    def fill_prompt(self, text):
        box = self.pg.get_by_role("textbox", name=re.compile("Bạn muốn tạo")).first
        box.click()
        self.pg.keyboard.press("Control+A")
        self.pg.keyboard.press("Delete")
        self.pg.keyboard.insert_text(text)
        self.settle(600)

    def prompt_text(self):
        return self.pg.get_by_role("textbox", name=re.compile("Bạn muốn tạo")).first.inner_text()

    def generate(self, expect_cost=15, confirm=False):
        """Bấm tạo. Từ chối nếu confirm=False hoặc chi phí hiển thị khác kỳ vọng."""
        cost = self.read_cost()
        if cost is not None and expect_cost is not None and cost != expect_cost:
            raise RuntimeError(f"Chi phí hiển thị {cost} tín dụng, khác kỳ vọng {expect_cost}. Không bấm tạo.")
        if not confirm:
            return {"clicked": False, "cost": cost}
        self.pg.get_by_role("button", name="Bắt đầu tạo").click()
        self.settle(2000)
        return {"clicked": True, "cost": cost}


    # ---- tải về theo mã slot
    def _card_download_button(self, code):
        """Nút 'Tải xuống' của đúng thẻ có prompt bắt đầu bằng mã slot: nút nằm ngay phía trên dòng prompt
        (cùng cột, gần nhất). Không dùng 'nút đầu tiên trong vùng chứa' vì nhiều thẻ chung một vùng chứa."""
        handle = self.pg.evaluate_handle(
            """(code) => {
                const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n, node = null;
                while ((n = w.nextNode())) if (n.nodeValue.trim().startsWith(code + '.')) { node = n; break; }
                if (!node) return null;
                const range = document.createRange(); range.selectNodeContents(node);
                const t = range.getBoundingClientRect();
                const btns = [...document.querySelectorAll('button')].filter(b => (b.getAttribute('aria-label') || '').trim() === 'Tải xuống');
                let best = null, bd = 1e9;
                for (const b of btns) {
                    const r = b.getBoundingClientRect();
                    const dy = t.top - (r.top + r.height);               // dương: nút nằm phía trên dòng prompt
                    const dx = Math.abs((r.left + r.width / 2) - (t.left + 40));
                    if (dy >= -4 && dy < 260 && dx < 330 && dy < bd) { bd = dy; best = b; }
                }
                return best;
            }""", code)
        return handle.as_element()

    def _card_button(self, code, label):
        """Nút có aria-label `label` nằm ngay phía trên dòng prompt của thẻ `code` (cùng thuật toán với nút tải)."""
        handle = self.pg.evaluate_handle(
            """([code, label]) => {
                const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n, node = null;
                while ((n = w.nextNode())) if (n.nodeValue.trim().startsWith(code + '.')) { node = n; break; }
                if (!node) return null;
                const range = document.createRange(); range.selectNodeContents(node);
                const t = range.getBoundingClientRect();
                let best = null, bd = 1e9;
                for (const b of document.querySelectorAll('button')) {
                    if ((b.getAttribute('aria-label') || '').trim() !== label) continue;
                    const r = b.getBoundingClientRect();
                    const dy = Math.abs(t.top - (r.top + r.height)), dx = Math.abs((r.left + r.width / 2) - (t.left + 40));
                    if (dx < 400 && dy < 300 && dy < bd) { bd = dy; best = b; }
                }
                return best;
            }""", [code, label])
        return handle.as_element()

    def reuse_from(self, code):
        """'Sử dụng lại câu lệnh' của thẻ `code`: nạp lại prompt + các thành phần (nhân vật, ảnh sản phẩm) vào ô nhập."""
        btn = self._card_button(code, "Sử dụng lại câu lệnh")
        if btn is None:
            return False
        btn.scroll_into_view_if_needed()
        btn.click()
        self.settle(1800)
        return True

    def chip_count(self):
        """Số thành phần đang gắn trong ô nhập (chỉ đếm các nút nằm ngay phía trên ô nhập câu lệnh)."""
        return self.pg.evaluate(
            """() => { const tb = document.querySelector('[role=textbox]'); if (!tb) return 0;
               const t = tb.getBoundingClientRect().top;
               return [...document.querySelectorAll('button')].filter(b => (b.getAttribute('aria-label')||'').trim() === 'Thành phần'
                  && b.getBoundingClientRect().bottom <= t + 4 && b.getBoundingClientRect().top >= t - 160).length; }""")

    def download_clip(self, code, dest):
        """Tải clip của slot `code` về đường dẫn `dest` (lưu nguyên file gốc, tên theo slot)."""
        btn = self._card_download_button(code)
        if btn is None:
            return None
        btn.scroll_into_view_if_needed()
        with self.pg.expect_download(timeout=90000) as dl:
            btn.click()
        d = dl.value
        d.save_as(dest)
        return dest

    def has_card(self, code):
        """Đã có thẻ clip với mã slot này trên trang chưa (để không tạo trùng, tốn tín dụng)."""
        return self.pg.evaluate(
            """(code) => { const w = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT); let n;
               while ((n = w.nextNode())) if (n.nodeValue.trim().startsWith(code + '.')) return true; return false; }""", code)

    def card_state(self, code):
        """'dang_tao' | 'xong' | 'khong_co' theo chữ trong thẻ (phần trăm tiến độ = đang tạo)."""
        if not self.has_card(code):
            return "khong_co"
        btn = self._card_download_button(code)
        return "xong" if btn is not None else "dang_tao"
