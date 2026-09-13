# music-wall

我最近在听什么。一张卡片一首歌 / 一张专辑：封面 + 基本信息 + 我写的那段话。

页面是**单个自包含的 HTML**：封面以 base64 内嵌，打开不需要联网，也没有外部依赖。

站点：https://shoutingyihui.github.io/music-wall/

## 两个版本

| 路径 | 是什么 |
| --- | --- |
| `index.html` | **首页 = 深色版（v2）**：近黑底 + 暗锈红块 + 直角 + 静态斜排底纹；单曲卡正文平铺、专辑卡点开升成"浮层印张"读全文 |
| `index-light.html` | 旧浅色版：每张卡从封面取强调色，跟着封面变深变浅 |
| `design-v2/index.html` | 深色版的发布副本（跟 `index.html` 是同一份文件） |

## 文件

| 路径 | 是什么 |
| --- | --- |
| `data/entries.json` | **内容的唯一来源**，两个版本都读它 |
| `covers/` | 封面原图（深色版按 `cover_key` 取，560px/q84 内嵌） |
| `assets/share.jpg` | 分享预览图（1200×630，聊天里贴链接时抓的就是它） |
| `build.py` + `lib/palette_to_theme.py` | 浅色版生成器（从封面取色决定每卡配色） |
| `spike/design-v2/build_preview.py` | **深色版生成器**（`spike/` 不入库，见下） |
| `spike/design-v2/DESIGN-v2.md` | **深色版的视觉规格**：字号/间距/颜色/浮层/底纹/验收实测数字 |
| `spike/design-v2/shot_preview.py` | 深色版渲染自检 + 出图（横向溢出/裂图/底纹密度/浮层开合/渐隐/滚动条） |
| `make_share.py` | 生成 `assets/share.jpg`（加歌后重跑一次） |
| `verify.py` | 浅色版渲染自检 |

## 深色版（v2）怎么重出

```bash
cd spike/design-v2
python3.10 build_preview.py        # → preview.html（单文件 630KB，6 条）
python3.10 shot_preview.py         # 自检 + 出 shots/*.png
cd ../..
cp spike/design-v2/preview.html index.html
cp spike/design-v2/preview.html design-v2/index.html
git add index.html design-v2/index.html && git commit && git push
```

推完等 Pages 变 `built <sha>`，再 `curl` 一次线上首页比对 sha256 ——"推上去了"和"线上是它"是两件事。

⚠️ **`spike/` 被 .gitignore 挡住**：仓库里没有生成器和这份规格，只有产物。克隆下来的人能看页面、
能改 `data/entries.json`，但要重新生成首页得在本机的 `spike/design-v2/` 里跑。

## 加一首

1. 封面丢进 `covers/`
2. 在 `data/entries.json` 里加一条：
   - `note_raw` — 我原话，一个字不动（存档用，也写进 html 注释）
   - `note` — 页面上显示的字，只动标点和承接
   - `note_edits` — 逐条改动清单，每一条都能驳
   - `cover_key` — 对应 `covers/<cover_key>.jpg`
3. 深色版：在 `build_preview.py` 的 `QUOTES` 里给这条补一句摘句。**必须是 `note` 里逐字出现过的话**，
   否则构建直接停下报"摘句不在 note 里（会露馅）"——手选摘句最容易出的错就是顺手改一两个字，
   页面上就成了"引文不引"。改完按上面第 2 节重出 + 推。
4. 浅色版：`python3 build.py && python3 build.py light && python3.10 verify.py`
5. `python3.10 make_share.py`（预览图要重做，否则上面还是旧的歌）

配色规则（浅色版）：强调色只能取自封面上真实存在的色团；封面上没有够格的色团就退化成中性灰，
**不靠编色相**。深色版反过来：全页一套色（近黑 `#221F20` + 暗锈红 `#793528` + 亮红 `#E73B33` 只小面积），
不从封面取色 —— 这是两个版本最根本的区别。

## 分享预览

两个版本的 `<head>` 里都写了 `og:` 标签，聊天软件/社交平台抓链接时读的就是它们
（深色版那套是从旧首页原样搬过来的，抓到的卡片不变；只有 `theme-color` 跟着底色换成近黑）。
卡片上刻意**不写** `og:description`：标题 + 图就够了，不堆文案。
`og:image` 必须是**绝对 URL 指向一个真实图片文件**，不能是页面里 base64 内嵌的封面 ——
抓取程序是另外发一次 HTTP 请求去拿图，看不到内嵌数据。
