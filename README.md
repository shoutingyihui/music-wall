# music-wall

我最近在听什么。一张卡片一首歌 / 一张专辑：封面 + 基本信息 + 我写的那段话。

页面是**单个自包含的 HTML**：封面以 base64 内嵌，打开不需要联网，也没有外部依赖。

## 文件

| 路径 | 是什么 |
| --- | --- |
| `index.html` | 页面本体（GitHub Pages 服务的就是它） |
| `index-light.html` | 同一份内容、不跟随封面变深色的浅色版 |
| `data/entries.json` | **内容的唯一来源**，所有歌曲和专辑都在这里 |
| `covers/` | 封面原图 |
| `build.py` | 读 `entries.json` + `covers/` → 生成上面两个 html |
| `lib/palette_to_theme.py` | 从封面里取色，决定每张卡的配色 |
| `verify.py` | 渲染自检：横向溢出 / 裂图 / 文字裁切 |

## 加一首

1. 封面丢进 `covers/`
2. 在 `data/entries.json` 里加一条：
   - `note_raw` — 我原话，一个字不动（存档用，也写进 html 注释）
   - `note` — 页面上显示的字，只动标点和承接
   - `note_edits` — 逐条改动清单，每一条都能驳
3. `python3 build.py && python3 build.py light`
4. `python3 verify.py`

配色规则：强调色只能取自封面上真实存在的色团；封面上没有够格的色团就退化成中性灰，**不靠编色相**。
