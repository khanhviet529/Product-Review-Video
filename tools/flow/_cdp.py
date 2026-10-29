"""Kết nối vào Chrome đang mở (cổng 9222) và các hàm dò giao diện Flow."""
import sys
from playwright.sync_api import sync_playwright

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

CDP = "http://127.0.0.1:9222"


def flow_page(ctx):
    """Trang Flow; khôi phục cửa sổ nếu bị thu nhỏ và đưa lên trước (chụp ảnh sẽ treo nếu cửa sổ không hiển thị)."""
    pages = [p for p in ctx.pages if "flow.google" in p.url]
    pg = pages[0] if pages else ctx.pages[0]
    try:
        cdp = ctx.new_cdp_session(pg)
        win = cdp.send("Browser.getWindowForTarget")
        if win["bounds"].get("windowState") != "normal":
            cdp.send("Browser.setWindowBounds", {"windowId": win["windowId"], "bounds": {"windowState": "normal"}})
        cdp.detach()
    except Exception:
        pass
    pg.bring_to_front()
    return pg


def dump(page, limit=80):
    """In các nút, ô nhập, tab đang thấy được (role + chữ)."""
    js = """() => [...document.querySelectorAll('button,[role=button],[role=tab],[role=menuitem],[role=option],input,textarea,[contenteditable=true],a[href]')]
      .filter(e => { const r = e.getBoundingClientRect(); return r.width > 4 && r.height > 4 && r.bottom > 0 && r.top < innerHeight; })
      .map(e => { const r = e.getBoundingClientRect();
        return [e.tagName.toLowerCase(), e.getAttribute('role') || '', (e.getAttribute('aria-label') || e.innerText || e.placeholder || '').trim().replace(/\\s+/g,' ').slice(0,60),
                Math.round(r.x), Math.round(r.y), Math.round(r.width), Math.round(r.height)]; })"""
    for row in page.evaluate(js)[:limit]:
        print(row)


def shot(page, path):
    """Chụp ảnh bằng CDP trực tiếp (nhanh và không treo như page.screenshot trên Flow)."""
    import base64
    cdp = page.context.new_cdp_session(page)
    data = cdp.send("Page.captureScreenshot", {"format": "png"})["data"]
    cdp.detach()
    with open(path, "wb") as f:
        f.write(base64.b64decode(data))
