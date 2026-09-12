#!/usr/bin/env python3
"""用 python3.10 的 Playwright 把 index.html 真渲染出来截图。

用 python3.10 而不是 python3：playwright 只装在 3.10 那个环境里。
"""
import pathlib
import sys

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "shots"
OUT.mkdir(exist_ok=True)

# (输出的文件名, 要截的 html, 视口宽, 系统配色方案)
JOBS = [
    ("follow-desktop", "index.html", 1100, "light"),
    ("follow-dark", "index.html", 1100, "dark"),
    ("follow-mobile", "index.html", 390, "light"),
    ("light-desktop", "index-light.html", 1100, "light"),
]

with sync_playwright() as p:
    browser = p.chromium.launch()
    for name, html, w, scheme in JOBS:
        URL = (HERE / html).as_uri()
        h = 900
        ctx = browser.new_context(viewport={"width": w, "height": h},
                                  device_scale_factor=1, color_scheme=scheme)
        page = ctx.new_page()
        errs = []
        page.on("console", lambda m: errs.append(f"{m.type}: {m.text}") if m.type == "error" else None)
        page.on("pageerror", lambda e: errs.append(f"pageerror: {e}"))
        page.goto(URL, wait_until="load")
        page.wait_for_timeout(400)
        # 页面里所有图都应该是内嵌的，不该有加载失败
        broken = page.evaluate(
            "() => [...document.images].filter(i => !i.complete || i.naturalWidth === 0).length")
        n_img = page.evaluate("() => document.images.length")
        doc_h = page.evaluate("() => document.documentElement.scrollHeight")
        page.screenshot(path=str(OUT / f"{name}.png"), full_page=True)
        print(f"{name:14} {w}px 图 {n_img} 张 裂图 {broken} 张 页高 {doc_h}px "
              f"JS错误 {len(errs)} 条 {errs if errs else ''}")
        ctx.close()
    browser.close()
print("截图 →", OUT)
