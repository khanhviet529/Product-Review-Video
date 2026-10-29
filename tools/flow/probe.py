"""Kết nối vào Chrome đang mở (cổng 9222), liệt kê tab, chụp màn hình tab Flow."""
import sys, json
from playwright.sync_api import sync_playwright

OUT = sys.argv[1] if len(sys.argv) > 1 else "shot.png"
with sync_playwright() as p:
    b = p.chromium.connect_over_cdp("http://127.0.0.1:9222")
    pages = [pg for c in b.contexts for pg in c.pages]
    for i, pg in enumerate(pages):
        print(i, pg.url[:100])
    flow = next((pg for pg in pages if "flow.google" in pg.url or "labs.google" in pg.url), pages[0])
    flow.bring_to_front()
    print("FLOW:", flow.url[:120], "| title:", flow.title())
    flow.screenshot(path=OUT)
