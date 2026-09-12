#!/usr/bin/env python3
"""图片（封面/海报/照片）→ 主色调 → 对比度达标的浅色 + 深色页面主题。

用法:
  python3 palette_to_theme.py cover.jpg                   # 打印色簇与主题报告
  python3 palette_to_theme.py cover.jpg --json theme.json  # 导出主题给渲染脚本用
  python3 palette_to_theme.py cover.jpg --proof proof.png  # 另存色卡证明图（给用户看）

三个不能改回去的设计决定（都是实测翻车后改的）:
 1. 不要直接取「面积最大的色簇」当主色。近黑/近白底往往占比最大
    （实测一张暗调人像封面：近黑占 43.2%，赢了面积投票，近黑处的"色相 156.8°"
    纯属数值噪声）。必须先按明度筛掉不可信的像素，再在有颜色的部分做
    饱和度加权的色相投票，找出主色「族」。
 2. 不要把主色本身当背景或正文字色。生成同色相浅底 + 压深的强调色，
    并卡 WCAG 对比度，不达标就自动往深里调。
 3. 底色不要靠 HLS 调「明度+饱和度」来染。高明度区 HLS 饱和度没有发挥空间
    （L=0.945 时饱和度拉满，色域只有 5% 的幅度 → 实测染出来 #f3f0ef 基本是灰的）。
    用线性 mix(白, 品牌色, α)。

实测基准（Eric Clapton《Clapton》2010，1200x1200 封面）:
  色相投票峰值 20°，同族色 #B08369 #CCADA4 #7B5C4A #463930，覆盖"有颜色部分"的 99%
  浅色 bg=#f4ece9 surface=#fbf8f6 text=#36261f accent=#825540
  深色 bg=#1f1714 surface=#2a1e19 text=#f7f1ee accent=#dabfb1
  对比度 正文/浅底 12.4:1  强调/浅底 5.42:1  正文/深底 15.76:1
"""
from __future__ import annotations

import argparse
import colorsys
import json
import pathlib
import sys

import numpy as np
from PIL import Image

WHITE = [255, 255, 255]
INK = [20, 17, 16]
DARK = [13, 12, 12]


# ---------- 颜色工具 ----------
def rgb_to_hls(c):
    r, g, b = [v / 255 for v in c]
    return colorsys.rgb_to_hls(r, g, b)          # -> (h, l, s)


def hls_rgb(h, l, s):
    r, g, b = colorsys.hls_to_rgb(h, min(max(l, 0), 1), min(max(s, 0), 1))
    return [round(x * 255) for x in (r, g, b)]


def hx(c):
    return "#%02x%02x%02x" % tuple(int(v) for v in c)


def _lum(c):
    def f(v):
        v /= 255
        return v / 12.92 if v <= 0.04045 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = [f(v) for v in c]
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def contrast(a, b):
    """WCAG 对比度。正文要 >=7（AAA），小字/强调色要 >=4.5（AA）。"""
    la, lb = _lum(a), _lum(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def mix(c1, c2, t):
    """线性混色：t=0 得 c1，t=1 得 c2。"""
    return [round(a * (1 - t) + b * t) for a, b in zip(c1, c2)]


# ---------- 取色 ----------
def kmeans(px, k=6, iters=30, seed=0):
    rng = np.random.default_rng(seed)
    C = [px[rng.integers(len(px))]]
    for _ in range(k - 1):                      # k-means++ 初始化
        d = np.min(((px[:, None, :] - np.array(C)[None, :, :]) ** 2).sum(-1), axis=1)
        p = d / d.sum() if d.sum() else None
        C.append(px[rng.choice(len(px), p=p)])
    C = np.array(C, dtype=float)
    lab = np.zeros(len(px), dtype=int)
    for _ in range(iters):
        d = ((px[:, None, :] - C[None, :, :]) ** 2).sum(-1)
        lab = d.argmin(1)
        for j in range(k):
            m = lab == j
            if m.any():
                C[j] = px[m].mean(0)
    share = np.bincount(lab, minlength=k) / len(px)
    return C, share


def extract_palette(img, k=6):
    im = img.convert("RGB")
    im.thumbnail((220, 220))
    a = np.asarray(im, dtype=np.float64).reshape(-1, 3)
    keep = ~((a.max(1) < 32) | (a.min(1) > 240))   # 先剔掉近黑/近白
    if keep.sum() < 50:
        keep = np.ones(len(a), bool)
    C, share = kmeans(a[keep], k=k)
    out = []
    for c, s in zip(C, share):
        h, l, sat = rgb_to_hls(c)
        reliable = 0.12 <= l <= 0.90               # 只有这区间里的色相才可信
        out.append(dict(rgb=[int(v) for v in c], hex=hx(c), h=h, l=l, s=sat,
                        share=float(s), reliable=reliable,
                        chroma=float(s * sat) if reliable else 0.0))
    out.sort(key=lambda d: (-d["chroma"], -d["share"]))
    return out


def pick_primary(pal, sigma_deg=26.0):
    """在色相上做环形投票，找主色「族」，再取族内份量最大的色做代表。"""
    cands = [c for c in pal if c["chroma"] > 0]
    if not cands:
        return pal[0], None
    grid = np.arange(0, 360, 1.0)
    curve = sum(c["chroma"] * np.exp(-(((grid - c["h"] * 360 + 180) % 360 - 180) ** 2)
                                     / (2 * sigma_deg ** 2))
                for c in cands)
    peak_h = float(curve.argmax())
    total = sum(c["share"] for c in cands) or 1.0
    band = [c for c in cands
            if abs((c["h"] * 360 - peak_h + 180) % 360 - 180) <= 2 * sigma_deg]
    info = {"peak_hue": peak_h,
            "band_share": sum(c["share"] for c in band) / total,
            "band_hexes": [c["hex"] for c in sorted(band, key=lambda c: -c["chroma"])],
            "colored_mass": sum(c["share"] for c in cands)}
    return max(band, key=lambda c: c["chroma"]), info


# ---------- 造主题 ----------
def build_theme(primary, hue_deg=None):
    h = (hue_deg / 360.0) if hue_deg is not None else primary["h"]
    accent_s = min(max(primary["s"] * 1.15, 0.32), 0.70)
    brand = hls_rgb(h, min(max(primary["l"], 0.34), 0.50), accent_s)

    bg = mix(WHITE, brand, 0.13)                 # 白底混 13% 品牌色 = 纸感
    surface = mix(WHITE, brand, 0.05)
    text = mix(INK, brand, 0.22)
    muted = mix(WHITE, mix(INK, brand, 0.5), 0.42)
    accent, lvl = mix(INK, brand, 0.72), 0.72
    while contrast(accent, bg) < 4.5 and lvl > 0.05:
        lvl -= 0.05
        accent = mix(INK, brand, lvl)

    d_bg = mix(DARK, brand, 0.11)
    d_surface = mix(DARK, brand, 0.18)
    d_text = mix(WHITE, brand, 0.10)
    d_muted = mix(d_bg, WHITE, 0.52)
    d_accent, lvl = mix(WHITE, brand, 0.45), 0.45
    while contrast(d_accent, d_bg) < 4.5 and lvl < 1.0:
        lvl += 0.05
        d_accent = mix(WHITE, brand, lvl)

    def chip_text(accent_c):
        """色块上的字：白字够清楚就用白字，不够就用近黑。"""
        return WHITE if contrast(WHITE, accent_c) >= 4.5 else mix(INK, brand, 0.55)

    def pack(d, acc):
        d = dict(d)
        d["accent"] = acc
        d["chip_text"] = chip_text(acc)
        d["line"] = mix(d["surface"], acc, 0.30)
        return {k: hx(v) if isinstance(v, list) else v for k, v in d.items()}

    return {"brand": hx(brand), "peak_hue": round(hue_deg, 1) if hue_deg is not None else None,
            "light": pack({"bg": bg, "surface": surface, "text": text, "muted": muted}, accent),
            "dark": pack({"bg": d_bg, "surface": d_surface, "text": d_text, "muted": d_muted},
                         d_accent)}


# ---------- 输出 ----------
def report(pal, primary, info, theme):
    out = []
    out.append("色簇（按「颜色份量 = 面积×饱和度」排序；✗ = 明度太低/太高，色相不可信）:")
    for c in pal:
        flag = " " if c["reliable"] else "✗"
        out.append(f'  {flag} {c["hex"].upper()}  占{c["share"] * 100:5.1f}%  '
                   f'色相{c["h"] * 360:6.1f}°  L={c["l"]:.2f}  S={c["s"]:.2f}  '
                   f'份量={c["chroma"]:.3f}')
    if info:
        out.append(f'色相投票峰值 {info["peak_hue"]:.1f}°   同族色 {" ".join(info["band_hexes"]).upper()}')
        out.append(f'  该族覆盖「有颜色部分」的 {info["band_share"] * 100:.0f}%'
                   f'（有颜色部分占全图 {info["colored_mass"] * 100:.0f}%）')
    out.append(f'主色 {hx(primary["rgb"]).upper()}')
    for name in ("light", "dark"):
        t = theme[name]
        out.append(f'{name:5s} bg={t["bg"]} surface={t["surface"]} '
                   f'text={t["text"]} muted={t["muted"]} accent={t["accent"]} chip={t["chip_text"]}')
    c1 = contrast(_hex2rgb(theme["light"]["text"]), _hex2rgb(theme["light"]["bg"]))
    c2 = contrast(_hex2rgb(theme["light"]["accent"]), _hex2rgb(theme["light"]["bg"]))
    c3 = contrast(_hex2rgb(theme["dark"]["text"]), _hex2rgb(theme["dark"]["bg"]))
    out.append(f"对比度 正文/浅底 {c1:.2f}:1（AAA 需 7）  强调/浅底 {c2:.2f}:1（AA 需 4.5）  "
               f"正文/深底 {c3:.2f}:1")
    if c1 < 7 or c2 < 4.5:
        out.append("⚠️ 对比度未达标 —— 不要直接交付，先调 brand 的明度区间")
    return "\n".join(out)


def _hex2rgb(s):
    s = s.lstrip("#")
    return [int(s[i:i + 2], 16) for i in (0, 2, 4)]


def proof_png(cover, pal, theme, out, info=None, title=""):
    """色卡证明图。没有 CJK 字体就走 DejaVu，中文会变方框但不影响色块判断。"""
    from PIL import ImageDraw, ImageFont

    def font(sz):
        for p in ("/usr/share/fonts/truetype/wqy/wqy-zenhei.ttc",
                  "/usr/share/fonts/opentype/noto/NotoSansCJK-Regular.ttc",
                  "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"):
            if pathlib.Path(p).exists():
                try:
                    return ImageFont.truetype(p, sz)
                except OSError:
                    pass
        return ImageFont.load_default()

    W, H = 1180, 640
    im = Image.new("RGB", (W, H), (250, 249, 246))
    d = ImageDraw.Draw(im)
    f_t, f_n, f_s, f_m = font(30), font(20), font(17), font(18)
    cv = Image.open(cover).convert("RGB").resize((380, 380), Image.LANCZOS)
    im.paste(cv, (52, 48))
    d.text((452, 40), "图片 → 主色调 → 主题色", font=f_t, fill=(36, 32, 28))
    d.text((452, 78), title, font=f_s, fill=(110, 105, 96))
    y = 118
    for c in pal:
        d.rectangle([452, y, 500, y + 28], fill=tuple(c["rgb"]), outline=(200, 198, 192))
        d.text((512, y + 5), c["hex"].upper(), font=f_m, fill=(50, 47, 42))
        note = f'占 {c["share"] * 100:4.1f}%   色相 {c["h"] * 360:5.1f}°   明度 {c["l"]:.2f}'
        note += "   ◀ 色相不可信" if not c["reliable"] else "   ◀ 主色族"
        d.text((600, y + 5), note, font=f_s,
               fill=(170, 60, 40) if not c["reliable"] else (90, 86, 80))
        y += 34
    if info:
        d.text((452, y + 4), f'色相投票峰值 {info["peak_hue"]:.0f}° —— '
                             f'{" ".join(info["band_hexes"]).upper()}', font=f_s,
               fill=(46, 92, 56))
        y += 34
    for name, label, sub in (("light", "浅色", "底色 / 强调色 / 文字 —— 卡片就长这样"),
                             ("dark", "深色", "同一色相，亮度反过来")):
        t = theme[name]
        d.rectangle([452, y + 10, 1140, y + 102], fill=tuple(_hex2rgb(t["bg"])),
                    outline=tuple(_hex2rgb(t["line"])))
        d.text((470, y + 22), "Aa 示例标题", font=f_n, fill=tuple(_hex2rgb(t["accent"])))
        d.text((470, y + 56), sub, font=f_s, fill=tuple(_hex2rgb(t["text"])))
        d.text((1030, y + 22), label, font=f_s, fill=tuple(_hex2rgb(t["accent"])))
        y += 118
    c1 = contrast(_hex2rgb(theme["light"]["text"]), _hex2rgb(theme["light"]["bg"]))
    c2 = contrast(_hex2rgb(theme["light"]["accent"]), _hex2rgb(theme["light"]["bg"]))
    c3 = contrast(_hex2rgb(theme["dark"]["text"]), _hex2rgb(theme["dark"]["bg"]))
    d.text((452, y + 6), f"对比度实测：正文/浅底 {c1:.2f}:1（AAA 需 7）   "
                         f"强调/浅底 {c2:.2f}:1（AA 需 4.5）   正文/深底 {c3:.2f}:1",
           font=f_s, fill=(46, 92, 56) if c1 >= 7 else (160, 70, 40))
    im.save(out)


def main(argv=None):
    ap = argparse.ArgumentParser(description="图片主色调 → 对比度达标的页面主题")
    ap.add_argument("image")
    ap.add_argument("--colors", type=int, default=6)
    ap.add_argument("--json", dest="json_out")
    ap.add_argument("--proof", dest="proof_out")
    ap.add_argument("--title", default="")
    a = ap.parse_args(argv)

    src = pathlib.Path(a.image)
    if not src.exists():
        sys.exit(f"找不到图片: {src}")
    img = Image.open(src)
    pal = extract_palette(img, k=a.colors)
    primary, info = pick_primary(pal)
    theme = build_theme(primary, hue_deg=info["peak_hue"] if info else None)

    print(f"图片: {src.name}  {img.size[0]}x{img.size[1]}  {src.stat().st_size:,} B")
    print(report(pal, primary, info, theme))

    if a.proof_out:
        proof_png(src, pal, theme, a.proof_out, info, a.title or src.stem)
        print(f"证明图: {a.proof_out}")
    if a.json_out:
        pathlib.Path(a.json_out).write_text(
            json.dumps(theme, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"主题 JSON: {a.json_out}  （渲染脚本读这个塞进 CSS 变量）")


if __name__ == "__main__":
    main()
