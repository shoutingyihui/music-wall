#!/usr/bin/env python3
"""音乐页构建器：data/entries.json + covers/ → index.html

用法：
    python3 build.py            # 卡片深浅跟随封面明暗（推荐）
    python3 build.py light      # 一律亮卡片（对照组，方便对比）

设计取舍：
- 封面压缩到 600×600 后 base64 内嵌 → 单文件、零外部依赖，发给谁都能直接打开，
  GitHub Pages 上也不会裂图。代价是体积随条目线性增长（5 条约 400KB），
  超过 ~25 首就该改成 covers/ 相对路径，改一处即可。
- 每张卡片的主色调取自它自己那张封面，见 lib/cover_theme.py（氛围色 + 记忆点两个角色）。
- 页面底色保持中性：卡片自己带色，页面就不能也跟着带色，否则颜色会互相打架。
"""
from __future__ import annotations

import base64
import html
import io
import json
import pathlib
import sys

from PIL import Image

HERE = pathlib.Path(__file__).resolve().parent
sys.path.insert(0, str(HERE / "lib"))

from cover_theme import theme_for                      # noqa: E402
from palette_to_theme import _hex2rgb, contrast        # noqa: E402

COVER_MAX = 600
COVER_Q = 86
UPDATED = "2026-09-12"                  # 兜底值；实际用 data/entries.json 的 updated

# 分享预览（og:）。抓取程序是**另外发一个 HTTP 请求**来读这些标签和那张预览图的：
# 它不执行 JS，也看不到页面里 base64 内嵌的封面 —— 所以 og:image 必须是
# 一个真实的绝对 URL（这里指向仓库里的 assets/share.jpg，见 make_share.py）。
SITE = "https://shoutingyihui.github.io/music-wall/"
TITLE = "最近在听"
# 故意不写 og:description / description —— 卡片上只留标题 + 图，不堆文案
META = f"""<meta property="og:type" content="website">
<meta property="og:site_name" content="{TITLE}">
<meta property="og:title" content="{TITLE}">
<meta property="og:url" content="{SITE}">
<meta property="og:image" content="{SITE}assets/share.jpg">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="630">
<meta property="og:locale" content="zh_CN">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:image" content="{SITE}assets/share.jpg">
<meta name="theme-color" content="#f2efec">"""

MODE = sys.argv[1] if len(sys.argv) > 1 else "follow"
DEST = "index.html" if MODE == "follow" else "index-light.html"


def cx(a: str, b: str) -> float:
    return contrast(_hex2rgb(a), _hex2rgb(b))


def thumb_datauri(src: pathlib.Path) -> tuple[str, int]:
    img = Image.open(src).convert("RGB")
    img = img.resize((COVER_MAX, COVER_MAX), Image.LANCZOS)
    buf = io.BytesIO()
    img.save(buf, "JPEG", quality=COVER_Q, optimize=True, progressive=True)
    raw = buf.getvalue()
    return "data:image/jpeg;base64," + base64.b64encode(raw).decode(), len(raw)


def var_block(cls: str, v: dict, indent: str = "    ") -> str:
    keys = ["bg", "surface", "text", "muted", "accent", "line"]
    decl = "".join(f"--{k}:{v[k]};" for k in keys)
    return f"{indent}.{cls}{{{decl}--stripe:{v['accent']};}}"


def picks_html(picks: list) -> str:
    out = []
    for grp in picks:
        items = "".join(
            f'<li><span class="no">{it["no"]}</span>'
            f'<span class="tt">{html.escape(it["title"])}</span></li>'
            for it in grp["items"])
        out.append(f'<div class="picks"><div class="picks-label">'
                   f'{html.escape(grp["label"])}</div><ul class="tracks">{items}</ul></div>')
    return "".join(out)


def card_html(e: dict, datauri: str) -> str:
    if e.get("kind") == "album":
        meta = f'{e["released"]} 发行 · 共 {e["tracks_total"]} 首'
        heading, sub = e["album"], e["artist"]
    else:
        meta = f'收录于《{e["album"]}》{e["album_year"]} · 第 {e["track_no"]} 首'
        heading, sub = e["title"], e["artist"]
    picks = picks_html(e["picks"]) if e.get("picks") else ""
    return f"""  <article class="card c-{e['id']}">
    <div class="cover"><img src="{datauri}" alt="{html.escape(heading)} 封面"
      width="600" height="600" loading="lazy"></div>
    <div class="body">
      <div class="meta">{html.escape(meta)}</div>
      <h3>{html.escape(heading)}</h3>
      <div class="artist">{html.escape(sub)}</div>
      <p class="note">{html.escape(e["note"])}</p>
      {picks}
    </div>
    <!-- 原话存档（语音输入，未润色）；改动清单见 data/entries.json
         {html.escape(e["note_raw"])} -->
  </article>"""


CSS = """
*,*::before,*::after{box-sizing:border-box}
html{-webkit-text-size-adjust:100%}
body{margin:0;background:#f2efec;color:#26221f;
  font-family:"PingFang SC","Microsoft YaHei","Noto Sans CJK SC","Source Han Sans SC",system-ui,sans-serif;
  line-height:1.75;font-size:17px}
.wrap{max-width:1080px;margin:0 auto;padding:56px 22px 96px}
header.page{margin-bottom:52px}
h1{font-size:clamp(30px,5vw,46px);margin:0 0 10px;letter-spacing:.02em}
.sub{color:#6d655f;font-size:15px}
h2.sec{font-size:14px;letter-spacing:.24em;color:#8a8079;
  margin:64px 0 20px;padding-bottom:12px;border-bottom:1px solid #ddd8d3;font-weight:600}
h2.sec:first-of-type{margin-top:0}
.card{display:grid;grid-template-columns:232px 1fr;gap:32px;align-items:start;
  background:var(--bg);color:var(--text);
  border:1px solid var(--line);border-left:7px solid var(--stripe);
  border-radius:16px;padding:28px 28px 28px 25px;margin-bottom:26px}
.cover img{display:block;width:100%;height:auto;border-radius:6px;
  box-shadow:0 10px 30px rgba(0,0,0,.30)}
.meta{font-size:13px;letter-spacing:.04em;color:var(--muted);margin-bottom:10px}
h3{margin:0;font-size:clamp(22px,3vw,30px);line-height:1.25;letter-spacing:.01em}
.artist{color:var(--accent);font-size:15px;margin:6px 0 16px;font-weight:600}
.note{margin:0;font-size:17.5px;line-height:1.95}
.picks{margin-top:22px;padding-top:18px;border-top:1px solid var(--line)}
.picks-label{font-size:13px;color:var(--muted);margin-bottom:8px}
ul.tracks{list-style:none;margin:0;padding:0}
ul.tracks li{display:flex;gap:12px;align-items:baseline;padding:3px 0}
.no{flex:0 0 2.4em;text-align:right;color:var(--accent);
  font-variant-numeric:tabular-nums;font-size:14px;font-weight:700}
.tt{font-size:16px}
@media (max-width:700px){
  .wrap{padding:34px 16px 72px}
  .card{grid-template-columns:1fr;gap:20px;padding:20px 20px 20px 17px}
  .cover{max-width:250px}
}
"""


def build() -> dict:
    data = json.loads((HERE / "data" / "entries.json").read_text(encoding="utf-8"))
    updated = data.get("updated", UPDATED)
    entries = [{**e, "kind": "song"} for e in data["songs"]] + \
              [{**e, "kind": "album"} for e in data["albums"]]

    css_rules, cards, stats = [], [], []
    for e in entries:
        src = HERE / "covers" / f'{e["cover_key"]}.jpg'
        img = Image.open(src).convert("RGB")
        r = theme_for(img, mode=MODE)
        v, an = r["v"], r["an"]
        uri, n = thumb_datauri(src)
        css_rules.append(var_block(f'c-{e["id"]}', v))
        cards.append(card_html(e, uri))
        stats.append(dict(id=e["id"], tone=an["tone"],
                          mode="深卡" if r["dark"] else "浅卡",
                          chroma=("中性" if an["acc"] is None
                                  else "色团%.0f%%" % (an["acc"]["share"] * 100)),
                          base=v["bg"], accent=v["accent"],
                          note=an["note"], thumb=n,
                          c_text=round(cx(v["text"], v["bg"]), 2),
                          c_acc=round(cx(v["accent"], v["bg"]), 2)))

    songs = [e for e in entries if e["kind"] == "song"]
    albums = [e for e in entries if e["kind"] == "album"]
    out = f"""<!DOCTYPE html>
<html lang="zh-CN">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>{TITLE}</title>
{META}
<style>
{CSS}
/* 每张卡片的主色调取自它自己那张封面：--bg 是氛围色，--stripe/--accent 是记忆点 */
{chr(10).join(css_rules)}
</style>
</head>
<body>
<div class="wrap">
<header class="page">
  <h1>最近在听</h1>
  <div class="sub">{len(songs)} 首单曲 · {len(albums)} 张专辑 · 更新于 {updated}</div>
</header>
<h2 class="sec">单曲</h2>
{chr(10).join(cards[:len(songs)])}
<h2 class="sec">专辑</h2>
{chr(10).join(cards[len(songs):])}
</div>
</body>
</html>
"""
    dest = HERE / DEST
    dest.write_text(out, encoding="utf-8")
    return dict(dest=dest, stats=stats, n=len(entries),
                songs=len(songs), albums=len(albums))


if __name__ == "__main__":
    r = build()
    print(f'→ {r["dest"]}  {r["dest"].stat().st_size:,} B   '
          f'{r["n"]} 条（{r["songs"]} 单曲 / {r["albums"]} 专辑）  模式={MODE}')
    print(f'{"条目":26} {"亮度":>5} {"卡片":>5} {"彩度":>7} {"氛围色":>8} {"记忆点":>8} '
          f'{"正文对比":>7} {"强调对比":>7}  说明')
    for s in r["stats"]:
        print(f'{s["id"]:26} {s["tone"]:5.3f} {s["mode"]:>5} {s["chroma"]:>7} '
              f'{s["base"]:>8} {s["accent"]:>8} {s["c_text"]:7.2f} {s["c_acc"]:7.2f}  {s["note"]}')
