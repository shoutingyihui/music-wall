#!/usr/bin/env python3
"""页面几何自检：横向溢出、文字裁切、裂图、卡片配色。输出纯文本便于逐行核对。"""
import json
import pathlib
import sys

from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
PROBE = (HERE / "spike" / "probe.js").read_text()


def check(page, label: str) -> None:
    # 先把整页滚一遍再判定：封面是 loading="lazy"，不滚就 evaluate，
    # 没进过视口的图会被误报成"裂图"（naturalWidth=0）。
    page.evaluate("async () => {"
                  "for (let y = 0; y < document.body.scrollHeight; y += 400) {"
                  "window.scrollTo(0, y); await new Promise(r => setTimeout(r, 60)); }"
                  "window.scrollTo(0, 0); }")
    page.wait_for_timeout(800)
    r = page.evaluate(PROBE)
    print(f"\n=== {label} ===")
    print(f"文档宽 {r['docScrollW']} / 视口 {r['innerW']}  横向溢出={'有!!' if r['hOverflow'] else '无'}")
    print(f"溢出元素 {len(r['overflowers'])}：{r['overflowers'][:5]}")
    print(f"裂图 {len(r['brokenImgs'])}：{r['brokenImgs']}")
    print(f"文字被裁 {len(r['clipped'])}：{r['clipped'][:5]}")
    print(f"图片总数 {r['imgCount']}  正文 {r['bodyText']} 字")
    for c in r["cards"]:
        print(f"  {c['cls'][-26:]:<28} 底={c['bg']:<22} 强调={c['accent']:<9} 尺寸={c['w']}×{c['h']}")


def main() -> int:
    bad = 0
    with sync_playwright() as p:
        b = p.chromium.launch()
        for f, label, w in (("index.html", "跟随封面", 1100),
                            ("index-light.html", "一律浅色", 1100)):
            f = sys.argv[1] if len(sys.argv) > 1 else f
            page = b.new_page(viewport={"width": w, "height": 900})
            page.goto((HERE / f).as_uri(), wait_until="load")
            check(page, f"{f} · {label} · {w}px")
            page.close()
            if len(sys.argv) > 1:
                break
        b.close()
    return bad


if __name__ == "__main__":
    sys.exit(main())
