#!/usr/bin/env python3
"""生成分享图，一次渲染出两个尺寸：

  assets/share.jpg       1200×630    预览卡缩略图（og:image 指向它，勿改尺寸）
  assets/promo-2400.png  2400×1260   高清版，手动发说说/朋友圈/当宣传图用

这张图必须是**独立的一张图文件**，不能是页面里 base64 内嵌的封面——抓取程序
是另外发一个 HTTP 请求去拿这张图，它看不到页面里 base64 的东西。

高清版直接取 2 倍设备像素比的原始渲染（不是把 1200 拉伸上去），文字是真的按
2400 宽排出来的，放大看依然锐。

用法：python3.10 make_share.py
"""
from __future__ import annotations

import json
import pathlib
import sys

from PIL import Image
from playwright.sync_api import sync_playwright

HERE = pathlib.Path(__file__).resolve().parent
OUT = HERE / "assets" / "share.jpg"
PROMO = HERE / "assets" / "promo-2400.png"
W, H = 1200, 630
SCALE = 2                      # 按 2 倍渲染：缩到 1200 更锐，原样存就是高清版
MSYH = "file:///mnt/c/Windows/Fonts/msyh.ttc"
MSYHBD = "file:///mnt/c/Windows/Fonts/msyhbd.ttc"


def entries() -> list[dict]:
    d = json.loads((HERE / "data" / "entries.json").read_text(encoding="utf-8"))
    return ([{**e, "kind": "song"} for e in d["songs"]] +
            [{**e, "kind": "album"} for e in d["albums"]])


def html_for(es: list[dict], updated: str) -> str:
    n_song = sum(1 for e in es if e["kind"] == "song")
    n_album = len(es) - n_song
    cover_n = len(es)
    # 封面条：总宽 = 6*side + 5*gap，跟着张数缩放，保证左右留白一样
    side = min(158, int((1200 - 132 - 22 * (cover_n - 1)) / cover_n))
    imgs = "".join(
        f'<img src="file://{HERE}/covers/{e["cover_key"]}.jpg" alt="">' for e in es)
    return f"""<!DOCTYPE html><html><head><meta charset="utf-8">
<style>
@font-face{{font-family:MSYH;src:url("{MSYH}") format("truetype");font-weight:400}}
@font-face{{font-family:MSYH;src:url("{MSYHBD}") format("truetype");font-weight:700}}
*{{margin:0;padding:0;box-sizing:border-box}}
body{{width:{W}px;height:{H}px;background:#f2efec;color:#26221f;
  font-family:MSYH,WenQuanYi Zen Hei,sans-serif;overflow:hidden;
  display:flex;flex-direction:column;justify-content:space-between;
  padding:64px 66px 56px;position:relative}}
/* 左上角一块极淡的暖色，避免大面积纯色发闷 */
body::before{{content:"";position:absolute;inset:0;
  background:radial-gradient(900px 420px at 12% -10%, #fff6ec 0%, rgba(255,246,236,0) 70%);}}
h1{{font-size:86px;font-weight:700;letter-spacing:.04em;line-height:1.1;position:relative}}
.strip{{display:flex;gap:22px;align-items:flex-end;position:relative}}
.strip img{{width:{side}px;height:{side}px;object-fit:cover;border-radius:8px;
  box-shadow:0 12px 26px rgba(0,0,0,.30)}}
.foot{{display:flex;justify-content:space-between;align-items:baseline;
  font-size:21px;color:#8a8079;letter-spacing:.04em;position:relative}}
.foot b{{font-weight:700;color:#26221f}}
</style></head><body>
<div>
  <h1>最近在听</h1>
</div>
<div class="strip">{imgs}</div>
<div class="foot">
  <span><b>{n_song}</b> 首单曲 · <b>{n_album}</b> 张专辑</span>
  <span>更新于 {updated}</span>
</div>
</body></html>"""


def main() -> int:
    es = entries()
    src = HERE / "data" / "entries.json"
    updated = json.loads(src.read_text(encoding="utf-8")).get("updated", "")
    OUT.parent.mkdir(exist_ok=True)
    tmp = HERE / "assets" / "_share_raw.png"
    # 必须真的落一个 .html 文件再用 file:// 打开（不能用 set_content）：
    # set_content 的页面是 about:blank 这种不透明源，file:// 的封面和字体
    # 都会被当成跨源请求拦掉 —— 表现是图 blank、字体悄悄退回系统默认。
    tmp_html = HERE / "assets" / "_share.html"
    tmp_html.write_text(html_for(es, updated), encoding="utf-8")
    with sync_playwright() as p:
        b = p.chromium.launch(args=["--allow-file-access-from-files"])
        pg = b.new_page(viewport={"width": W, "height": H},
                        device_scale_factor=SCALE)
        pg.goto(tmp_html.as_uri(), wait_until="load")
        pg.wait_for_timeout(700)
        bad = pg.evaluate(
            "() => [...document.images].filter(i => !i.naturalWidth).length")
        if bad:
            raise SystemExit(f"有 {bad} 张封面没加载成功，先修再截图")
        pg.screenshot(path=str(tmp), clip={"x": 0, "y": 0, "width": W, "height": H})
        b.close()
    tmp_html.unlink()
    raw = Image.open(tmp).convert("RGB")          # 2 倍原始渲染，2400×1260
    raw.resize((W, H), Image.LANCZOS).save(
        OUT, "JPEG", quality=88, optimize=True, progressive=True)
    raw.save(PROMO, "PNG", optimize=True)         # 高清版：原样存，别缩
    tmp.unlink()
    for p, size in ((OUT, f"{W}×{H}"),
                    (PROMO, f"{raw.width}×{raw.height}")):
        print(f"→ {p.relative_to(HERE)}  {p.stat().st_size:,} B  {size}")
    print(f"  封面 {len(es)} 张")
    return 0


if __name__ == "__main__":
    sys.exit(main())
