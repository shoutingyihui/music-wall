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
| `assets/share.jpg` | 分享预览图（1200×630，聊天里贴链接时抓的就是它） |
| `build.py` | 读 `entries.json` + `covers/` → 生成上面两个 html |
| `make_share.py` | 生成 `assets/share.jpg`（加歌后重跑一次） |
| `lib/palette_to_theme.py` | 从封面里取色，决定每张卡的配色 |
| `verify.py` | 渲染自检：横向溢出 / 裂图 / 文字裁切 |

## 加一首

1. 封面丢进 `covers/`
2. 在 `data/entries.json` 里加一条：
   - `note_raw` — 我原话，一个字不动（存档用，也写进 html 注释）
   - `note` — 页面上显示的字，只动标点和承接
   - `note_edits` — 逐条改动清单，每一条都能驳
3. `python3 build.py && python3 build.py light`
4. `python3.10 make_share.py`（预览图要重做，否则上面还是旧的歌）
5. `python3.10 verify.py`

配色规则：强调色只能取自封面上真实存在的色团；封面上没有够格的色团就退化成中性灰，**不靠编色相**。

## 分享预览

`index.html` 的 `<head>` 里写了几条 `og:` 标签，聊天软件/社交平台抓链接时读的就是它们。
改站点地址或文案时，改 `build.py` 顶部的 `SITE` / `TITLE` / `DESC` 三个常量，再重新 build。
`og:image` 必须是**绝对 URL 指向一个真实图片文件**，不能是页面里 base64 内嵌的封面——
抓取程序是另外发一次 HTTP 请求去拿图，看不到内嵌数据。
