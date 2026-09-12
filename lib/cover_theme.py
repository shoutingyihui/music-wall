#!/usr/bin/env python3
"""封面 → 卡片配色。

核心原则：氛围色和强调色都必须是封面里真实存在的色团，不许用色相平均合成。
平均会算出封面上根本没有的颜色（绿草地 100° 与灰蓝天空 210° 平均出 48° 卡其，
而卡其在这张封面里一个像素都没有）。

三种角色的模型：
  氛围色 = 面积最大的色团的真色；该团若近黑/近白（色相是噪声）则退化为中性。
  强调色 = 色度（饱和×明度）最强的色团的真色；没有合格的则退化为中性。
  深浅   = 跟随封面整体明暗（暗封面配深卡，亮封面配浅卡）。

踩过的坑（别再踩）：
  · 近黑像素/近黑色团的 HSV 饱和度会说谎（[6,18,10] 报 S=0.50、色相 140°），
    所以筛选要用色度而不是饱和度。
  · k-means 若在聚类前剔除近黑/近白，"封面的黑色背景"就永远进不了候选。
  · 圆平均色相 R 高不代表有颜色：faye 那张 R=0.91 但全图均饱和只有 0.13。
"""
import pathlib
import sys

import numpy as np

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent))
from palette_to_theme import _hex2rgb, contrast, hx, kmeans, mix  # noqa: E402

K = 6
MIN_SHARE = 0.04      # 一个色团要占到 4% 才算"封面的一部分"
MIN_SAT = 0.15        # 强调色团的饱和下限
CHROMA_MIN = 0.10     # 强调色团的色度（饱和×明度）下限
DARK_TONE = 0.28      # 整图亮度低于此 → 深色卡


def _lin(x):
    c = np.asarray(x, dtype=np.float64) / 255.0
    return np.where(c <= 0.04045, c / 12.92, ((c + 0.055) / 1.055) ** 2.4)


def _tone_of(a):
    """整图平均感知亮度，0=全黑 1=全白"""
    return float((_lin(a) @ [0.2126, 0.7152, 0.0722]).mean())


def _sv(rgb):
    mx, mn = float(max(rgb)), float(min(rgb))
    s = 0.0 if mx <= 0 else (mx - mn) / mx
    return s, mx / 255.0


def _grey(l):
    v = round(255 * max(0.0, min(1.0, l)))
    return [v, v, v]


def _hls(h, l, s):
    import colorsys
    r, g, b = colorsys.hls_to_rgb((h % 360) / 360.0, max(0.0, min(1.0, l)), max(0.0, min(1.0, s)))
    return [r * 255, g * 255, b * 255]


def _fit(rgb, bg, target=4.5):
    """在保持色相/饱和的前提下调明度，直到与底色对比度达标"""
    f = _hex2rgb(hx(rgb))
    if contrast(f, _hex2rgb(hx(bg))) >= target:
        return f
    h, l, s = _rgb2hls(f)
    for i in range(1, 101):
        for cand in (l + i * 0.008, l - i * 0.008):
            if 0.0 <= cand <= 1.0:
                t = _hls(h, cand, s)
                if contrast(t, _hex2rgb(hx(bg))) >= target:
                    return t
    return f


def _rgb2hls(rgb):
    import colorsys
    r, g, b = [max(0.0, min(1.0, c / 255.0)) for c in rgb]
    h, l, s = colorsys.rgb_to_hls(r, g, b)
    return h * 360.0, l, s


def analyse(img) -> dict:
    im = img.convert("RGB")
    im.thumbnail((200, 200))
    a = np.asarray(im, dtype=np.float64).reshape(-1, 3)
    tone = _tone_of(a)

    C, share = kmeans(a, k=K)
    cl = []
    for i in range(len(C)):
        rgb = [float(x) for x in C[i]]
        s, v = _sv(rgb)                                   # v = HSV 明度（max/255）
        lum = float(_lin(rgb) @ [0.2126, 0.7152, 0.0722])  # 感知光度，判断深浅用
        cl.append(dict(rgb=rgb, hex=hx(rgb), hue=_rgb2hls(rgb)[0], s=s, v=v, lum=lum,
                       share=float(share[i]), chroma=s * v,
                       tonal=(v < 0.16 or v > 0.88)))

    dom = max(cl, key=lambda c: c["share"])
    base = _grey(dom["lum"]) if dom["tonal"] else dom["rgb"]

    ok = [c for c in cl if c["share"] >= MIN_SHARE and not c["tonal"]
          and c["s"] >= MIN_SAT and c["chroma"] >= CHROMA_MIN]
    acc = max(ok, key=lambda c: c["chroma"]) if ok else None
    accent = acc["rgb"] if acc else mix(base, [128, 128, 128], 0.5)

    return dict(tone=tone, dark=(tone < DARK_TONE), clusters=cl, dom=dom, acc=acc,
                base=base, accent=accent,
                note=("强调色取自封面真实色团 %s，该团占 %.1f%%、色度 %.3f（色相 %.0f°）"
                      % (hx(acc["rgb"]), acc["share"] * 100, acc["chroma"], acc["hue"]))
                if acc else
                ("封面上没有够格的高色度色团（最大色度 %.3f）→ 强调色退化为中性，不编色相"
                 % max(c["chroma"] for c in cl)))


def theme_for(img, mode: str = "follow") -> dict:
    an = analyse(img)
    if mode == "follow":
        dark = an["dark"]
    elif mode == "dark":
        dark = True
    else:
        dark = False

    base, accent = an["base"], an["accent"]
    if dark:
        bg = mix([17, 17, 19], base, 0.55)
        bg = mix(bg, accent, 0.10)
        v = dict(
            bg=hx(bg),
            surface=hx(mix(bg, [255, 255, 255], 0.07)),
            text=hx(mix([255, 255, 255], base, 0.06)),
            muted=hx(mix(bg, [255, 255, 255], 0.52)),
            accent=hx(_fit(accent, bg, 4.5)),
            line=hx(mix(bg, [255, 255, 255], 0.14)),
        )
    else:
        # 浅色模式下，若封面的最大色团是近黑（暗调封面必然如此），拿它当染色源
        # 只会得到灰 —— 所以改用强调色染色，浅底才带得上封面的颜色。
        src = accent if an["acc"] else base
        bg = mix([255, 255, 255], src, 0.16)
        v = dict(
            bg=hx(bg),
            surface=hx(mix(bg, [255, 255, 255], 0.55)),
            text=hx(mix([26, 22, 21], base, 0.30)),
            muted=hx(mix(bg, [26, 22, 21], 0.55)),
            accent=hx(_fit(accent, bg, 4.5)),
            line=hx(mix(bg, [26, 22, 21], 0.16)),
        )
    v["stripe"] = v["accent"]
    return dict(v=v, an=an, dark=dark)


if __name__ == "__main__":
    from PIL import Image
    root = pathlib.Path(__file__).resolve().parent.parent
    for p in sorted((root / "covers").glob("*.jpg")):
        r = theme_for(Image.open(p))
        print(f'{p.stem:16s} 亮度={r["an"]["tone"]:.3f} '
              f'{"深" if r["dark"] else "浅"}卡 bg={r["v"]["bg"]} accent={r["v"]["accent"]}')
        print(f'{"":16s} {r["an"]["note"]}')
