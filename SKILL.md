---
name: ecom-video
description: 自动制作电商自动化 skills 的推广短视频（选题、剧本、配音、动效画面、配乐、出片、审片）；也用于按新画面标准重做已出过的视频
---

# 电商推广短视频自动生成

**宣传片的场面与实录分别编排。** 让观众先见到工作量和冲突。按本题铺开报表、售后台、归因日历、价格天平、商品队列或选片台，再跟着一件具体的事推进特写。讲解动作参考成员片里的飞入、聚合、局部对照与揭晓。实录参考拼多多发布助手的字段近景和可见反馈。开头与中段各用一段连续操作，保留输入、触发和结果变化。停在同一页的轻微摇镜不能代替操作。实录使用领取包当次产出的文件，并与其运行编号绑定。

**先录后分镜。** 执行观众领取包，保留本次原始录像。先选出开头能看懂的工具动作、结果和中段可复核的另一个步骤，再决定这一集如何拍。上架拍网页连填与读回，素材制作拍选稿与导出。

**每个选题独立安排开场和片内动效。** 写分镜时说明谁遇到了什么问题、镜头里的物体发生什么改变、观众如何认出工具的作用。查价让同一只杯子的两张价签分开，归因让七天和一天的窗口从同一起点展开，退款让账单上多算的一笔退回。万件上架是上架场景的一个示例，有规模演绎时标记「规模场景示意」。中段和结论的动作也要解释本句旁白。将同批首镜和片内关键帧并排审片，构图与运动重复时先改分镜。

为抖音和微信视频号制作 30–55 秒的竖屏推广短视频。每条视频围绕一个电商自动化 skill，只讲一件事：**这一步可以自动化，真实可靠，省下大量时间**。目的是推广，不是教程。

脚本负责配音、配乐、渲染、合成和各项检查；你负责：选题、问用户要 skill、写剧本、**写这条视频的动效画面代码**（第 7 节）、看检查结果和审片。所有命令都由你在用户电脑上、从工程根目录直接运行，结果自己读，不要让用户去点文件。

**正式画面以陶瓷杯 v2 为基准。** Codex、Claude 等制作端都应为题目设计专属动效，给每个内容镜头绑定 `visual`。参考 `series/ceramic/` 的产品多视角、跟随配音的价签、可读的实录窗口、结果揭晓和品牌收尾。按内容安排运动与停留，逐镜审片。

**推广观众领取包时优先走批量入口。** 从工程根目录运行 `python pipeline/series_batch.py run --output out/系列 --count 1`；批量时调整数量或指定 `--topics B,D,F`。选题、执行同版本领取包、录屏、合成及领取索引由程序串起。可录选题、一次准备和扩展方法见 [批量出片与领取包](docs/批量出片与领取包.md)。

**用法**
- 做新视频：第 1–10 节，先看下面的清单。
- 重做已出过的视频（换画面标准或换音色）：第 11 节。
- 定期任务（热点、爆款调研、数据反馈）：第 12–13 节。
- 字段、兜底场景库、声音、远程会话：第 14–19 节，用到时查。

## 一条视频完整跑一遍

`<编号>` 形如 `2026-11-18-s3-a`（日期-s步骤-序号）。

| # | 做什么 | 命令 / 文件 | 节 |
|---|---|---|---|
| 1 | 选题 | `python pipeline/pick_topic.py` | 1 |
| 2 | 问用户要 skill，读功能点 | `python pipeline/read_skill.py <步骤号> [skill 路径]` | 2 |
| 3 | （有 skill 时）录屏生成素材包 | `pipeline/record_web.py` 或 `tools/kimi_call.py` + `pipeline/frames_pack.py` | 3 |
| 4 | 写剧本 | `out/<编号>/script.json` | 4 |
| 5 | 检查剧本，改到没有 ✗ | `python pipeline/script_check.py out/<编号>/script.json` | 5 |
| 6 | 配图 | `python tools/gen_image.py "…" --id <图片编号>` | 6 |
| 7 | 写画面代码 | 先读 `docs/画面档写法.md`，写 `out/<编号>/visual.js` | 7 |
| 8 | 预览，改到满意 | `python pipeline/preview.py out/<编号> 1` → 看 `preview.jpg` | 7 |
| 9 | 配音 | `python tools/web_tts.py out/<编号>` | 8 |
| 10 | 出片 | `python pipeline/make.py out/<编号>/script.json --reuse-voice [--footage auto]` | 9 |
| 11 | 运动检查不过：只重渲出问题的场景 | `python pipeline/scene_check.py out/<编号> <场景序号>` | 9 |
| 12 | 自己审片，改到合格 | 看 `out/<编号>/review.jpg` | 10 |
| 13 | 交付 | `<编号>.mp4` + `publish.json`，说明要打 AI 标识 | 10 |

配完音再预览，时间轴就是真实配音时长；没配音时按字数估算。

## 0. 首次使用

```
python tools/doctor.py
```

按提示补齐带 ✗ 的项（`!` 是可选功能）。全新电脑一般要做：

```
python -m pip install -r requirements.txt     # tinysoundfont 装不上时：python -m pip install --no-deps tinysoundfont
npm install                                   # 渲染用的 Playwright（Node 18 以上）
npx playwright install chromium
python -m playwright install chromium         # 录网页工具、爆款采集用的 Python 版
```

另需 ffmpeg / ffprobe 在 PATH 里（Windows：`winget install Gyan.FFmpeg`）。

配音默认用本机开着的 VoxCPM 网页版（第 8 节），需要 NVIDIA 显卡（约 8 GB 显存）。没装 VoxCPM 时运行 `python tools/setup_tts.py`；退出码 3 表示硬件不够，如实告诉用户，不要换别的声音。在 `assets/voice/` 使用当前发布方自行配置的参考音色（第 16 节）。初次使用请按 README 设置参考音。

# 一、做新视频

## 1. 选题

```
python pipeline/pick_topic.py
```

输出这次要做的大类（`step`、`name`）、小点（`point`）和痛点（`pain`）。选题池是 `data/topics.json`：18 个大类（选品控价、资料维护、素材、上架、推广、客服、私域、复盘、售后退款、评价口碑、库存补货、订单物流、活动大促、直播带货、财务对账、多平台铺货、合规巡检、团队日常），每类 3–7 个小点，按"最久没做的大类、类内下一个小点"轮换。加 `--hot` 时按七比三穿插热点视频（第 12 节）。

**跳出选题池**（用户点名要做某个题、或池里没有合适的）：

```
python pipeline/pick_topic.py --topic "退货地址自动核对" --step 9 --pain "地址填错,退货寄丢"
```

`--step` 可选，挂到最接近的大类（素材包、话题标签、轮换记录都按它走）；不挂时 `step` 为 `null`，第 2 节的 `read_skill.py` 步骤号写 `-`。剧本里照抄输出的 `step` 和 `angle_index`（自定义选题是 `null`），并加 `"custom": true`。池里缺的好题目，做完后可以补进 `data/topics.json`（只往后加，不改已有小点的顺序）。

有账号数据时（第 13 节）输出里会带 `prefer`：表现好、且近期没用过的结构和钩子写法，写剧本时优先选。

## 2. 问用户要 skill（可以跳过）

问用户一句："这一步对应的 skill 放在哪？没有就直接回车跳过。"

```
python pipeline/read_skill.py <步骤号> [skill 路径]      # 不挂大类的自定义选题，步骤号写 -
```

- 有路径：得到 skill 的名称、简介和功能点，剧本里 `skill.provided` 写 `true`。
- 没有路径：`skill.provided` 写 `false`，按通用功能点写，实录位置留空。**这时不能写"实测"，不能写自动化一侧的具体数字，结尾要说"上线后领取"，画面上要有"开发中 / 功能示意"。**

## 3. 录屏，生成素材包（有 skill 时）

录到的片段放进实录槽位，实测数字才能写进剧本。**只在测试店铺、测试商品或虚构演示数据上录；默认停在提交之前；花钱或对外触达的动作（投放、报名、发消息、加好友）不真实执行。**

先看这一步有没有可用的素材包：`assets/footage/s<步骤>/pack.json` 存在且 `review` 为 `ok`。有就跳到第 4 节。

**本地网页工具**（例如商品资料检查）：写演示清单 `data/demos/s<步骤>.json`（照 `data/demos/s2.json`），然后

```
python pipeline/record_web.py data/demos/s<步骤>.json
```

每个点击都先过安全闸（`pipeline/guard.py`），按钮文字含提交、发布、确认、支付等会被拦下。确需点击时用 `--allow "按钮文字"` 明确放行，并先问用户。

**在用户已登录的浏览器里执行的 skill**（例如拼多多上架）：用 Kimi 浏览器扩展操作，自己直接运行命令（本机 Kimi WebBridge 没启动会自动 start）。

```
python tools/kimi_call.py list_browser_tabs                      # 找到目标标签页
python tools/kimi_call.py attach_tab '{"tabId": 123}'
python tools/kimi_call.py snapshot                               # 读页面，拿元素引用
python tools/kimi_call.py fill '{"selector":"@e12","value":"…"}' --mark "填写标题"
python tools/kimi_call.py click '{"selector":"@e30"}' --label "40"   # 点击必须写 --label（按钮上的文字）
python tools/kimi_call.py screenshot                             # 每做一两步截一张，就是录像的画面
```

- 每做完一步用 `--mark 步骤名` 打标记，批量处理那步加 `--hl hook`。**停在提交之前**：按钮文字含提交、发布、确认、保存草稿等会被安全闸拦下。
- 做完后生成素材包（`--mask` 盖住店铺名、账号等区域，按画面比例 0–1）：

```
python pipeline/frames_pack.py --step s4 --product 拼多多上架 --mask '[{"x":0.79,"y":0,"w":0.19,"h":0.065}]'
```

- 画面里不能出现别家品牌：带品牌标识的商品图不要上传，品牌字段不填。

没有打码规则、或是真实后台录的素材包都是"待人工确认"，**不要停下来等**：照常出片（实录槽位先用示意占位），交付时一并请用户看录像。用户确认后运行 `python pipeline/pack.py approve s<步骤>`，再 `python tools/refill.py <编号>` 换成实录版。

## 4. 写剧本 `out/<编号>/script.json`

格式照 `tests/fixtures/script_ok.json`，场景类型和字段见第 14 节。

- 主线只有一条：以前怎么费时 → 现在自动完成 → 省下时间 → 关注领取。不讲原理，不讲操作步骤。
- 开头第一个场景是钩子，优先用前后对比或一张工作场景配图。
- 中段放一个悬念钩子（场景加 `"mid_hook": true`，位置在全片 35%–65%），答案留到最后两个场景揭晓（加 `"payoff": true`）。写法从 `data/hooks.json` 里选，近 3 条用过的不能再用。
- 揭晓的内容要实在：是真正关键的一步，或者直接接转化动作。
- 最后一个场景是 `cta`：强调免费，引导"关注 + 评论区发关键词"。抖音不能出现微信、公众号等站外引导；视频号可以引到公众号或企业微信。
- 结构从 `data/structures.json` 里选，近 5 条用过的不能再用。主题（`paper` `ink` `mint` `dusk`）和情绪（`upbeat` `calm` `tense` `playful` `warm`）也要和最近几条错开。
- 企鹅至少出场两次（场景里加 `mascot`），最后的 `cta` 必须有。
- 配图 1–2 张，只作氛围示意。
- 数字：自动化一侧只用素材包里量出来的数（`pack.json` 的 `measured`），写了实测数字的场景加 `"measured": true`，检查时会和素材包核对；人工一侧可以估算，场景加 `"about": "manual"` 并在画面注明"估算"。
- 禁用：必定、保证、100%、稳赚、暴利，以及任何收益承诺。收益只说"省下的时间拿去选品和运营"。
- 画面档（第 7 节）：每个场景加 `"visual": "场景名"`，画面要用到的文字也写进这个场景的字段（例如 `"rows": [...]`、`"chips": [...]`），剧本检查会扫到它们。

## 5. 检查剧本

```
python pipeline/script_check.py out/<编号>/script.json
```

有 ✗ 就改，直到通过。出片时还会和近 10 条成片查重（结构、钩子、主题、配乐情绪、场景顺序、文案），太像会报出和哪一条像、像在哪里，按提示换结构或重写文案。话题标签在有 `data/tags.json` 时必须从里面这一步的词里选。

## 6. 配图

```
python tools/gen_image.py "深夜的电商办公室，桌上堆满表格和样品" --id <图片编号>
python tools/regen_images.py        # 剧本里登记了、但 assets/images/ 里没有的图，按剧本记下的原提示词补齐
```

需要 `OPENAI_API_KEY`：请用户放进 `tools/.env`（一行 `OPENAI_API_KEY=…`，已被 `.gitignore` 排除），**不要让用户把 Key 贴进对话**。

把生成的文件名写进剧本对应场景的 `image`，以及 `images` 列表的 `file`。也可以用明确可商用的图片：`--register 图.jpg --id … --source 网址 --license 授权`。来源或授权不明的图不要用。

## 7. 画面：每条视频自己写动效代码（画面档）

**每集围绕本次操作设计画面。** Codex 和其他制作端均写或复用与题目匹配的专属 `visual.js`。素材、道具和运动应解释这一步操作的因果。

1. **先读 `docs/画面档写法.md`**（分镜、构图、运动、套件、骨架、迭代方法、踩过的坑），再从里面的范例表挑一条题材最近的 `out/<编号>/visual.js` 读一遍。先给每个场景写一句分镜（画面在演什么变化），再写代码。
2. 剧本里每个场景已经有 `visual` 和上屏文字字段（第 4 节）。**画面代码里不要硬写上屏文字。**
3. 写 `out/<编号>/visual.js`，注册 `window.VISUALS = {场景名: {bg, build, init?, anim, sfx?}, …, outro}`。背景、进出场、图标、浏览器外框、结尾关注块、落版都用套件 `window.KIT`（`engine/kit.js`），每条视频只写自己的故事和配色。
   - `build(sc, id, H)` 返回 HTML；元素 id 一律以 `id` 开头。`init` 在搭好后跑一次（例如 `H.MO.split` 拆字）。
   - `anim(sc, id, t, H)`：`t` 是场景内秒数，`H.dur` 场景时长，`H.T` 全片时间。**画面必须是 t 的纯函数**：渲染是逐帧 `seek(t)` 截图，CSS `animation`/`transition`、`requestAnimationFrame`、`Math.random` 都不能用。
   - 动效库 `H.MO`（`engine/motion.js`）：缓动与弹簧 `E` `spring`、关键帧 `kf`、`tw`；确定性随机与噪声 `rng` `hash` `noise` `wob`；`set` 一次设好位移/缩放/3D 旋转/透明度/模糊；逐字动画 `split` `textIn` `textOut` `textWave`；`stagger` `count` `typed` `sheen`；Canvas 的 `dust`（漂浮粒子）`burst`（彩片爆开）`ring`（冲击环）`stream`（数据流）`glow`；镜头 `camera`。
   - 其他：`H.at(sc,'词')` 配音说到这个词的时刻（用来卡点），`H.frame(sc,t)` / `H.drawFrame(...)` 实录帧（footage 场景有素材包时），`H.fmt` 行内标记，`H.img(文件名)` 配图路径，`H.SAFE` 安全区，`H.BRAND` `H.BRAND_LOGO` 落版用。
   - 写了 `outro` 就替换默认落版，但必须保留韬行科技标志和名字。
4. 企鹅仍由引擎画（场景的 `mascot` 字段），可以用 `S` `x` `f` 自定位置，`move: [[t, x, f, S], …]` 让它走位。
5. 边写边看：`python pipeline/preview.py out/<编号> 1` 十几秒出一张每秒一格的预览图（`out/<编号>/preview.jpg`），页面报错直接打印；拿不准的时刻用 `--at 3.2 3.4` 只抽那几帧。满意了再配音出片。

**画面标准**（预览和审片时逐条对照）

- 满屏：竖屏 1080×1920 全部用上，主体居中偏上，不要"大字靠左、半屏空白"。背景要有层次（渐变光斑、网格、粒子、配图推拉）。
- 一直在动：每 1–2 秒有一个新动作（入场、变化、数字跳动、镜头推移、转场），其余时间有持续微动（漂浮、呼吸、扫光）。不要整块淡入后停住。
- 讲故事而不是列字：用画面演出"以前怎么乱 → 现在怎么自动"（零散记录被吸进名单、通知越堆越多把回访挤掉、卡片翻开揭晓……）。
- 关键内容在上 150、下 460 像素之外（下面是字幕条和平台界面）；装饰可以满出去。
- 文字不重叠、不溢出、不被企鹅挡住；没录屏的实录位置必须有"示意"字样；skill 未输入时画面上要有"开发中 / 功能示意"。

## 8. 配音

用户一般开着 VoxCPM 网页版（http://127.0.0.1:8808，显卡被它占着，本地再加载一份模型会爆显存），默认走网页版：

```
python tools/web_tts.py out/<编号>                 # 全部配音，固定音色；某段失败只重试那一段
python tools/web_tts.py out/<编号> --only s03      # 只重配某一段（改了这段文案时）
```

网页版没开时 `web_tts.py` 会报连不上：**你自己把它启动**，不要让用户去点：

```
start "" "D:\promgram\.ai_vedio\VoxCPM\Launch-VoxCPM.cmd"
```

（路径以实际安装位置为准，`web_tts.py --voxcpm` 可改。）等大约一分钟、页面能打开后再配音。实在启动不了才改用 `make.py` 不加 `--reuse-voice`（本地模型直接配音，可能爆显存）。

agent 听不了音频：配音和配乐的听感请用户判断。

## 9. 出片

```
python pipeline/make.py out/<编号>/script.json --reuse-voice
python pipeline/make.py out/<编号>/script.json --reuse-voice --footage auto
python pipeline/make.py out/<编号>/script.json --reuse-voice --footage hook=录屏.mp4:0:8:2 --footage mid=录屏.mp4:20:10:2
```

- `--reuse-voice` 复用第 8 节配好的音。`--footage 槽位=视频:起点秒:时长秒:倍速`；有素材包时直接用 `--footage auto` 自动取高光片段，没有就用示意占位。
- 配乐默认由代码原创编曲（第 16 节），不用另外准备。

**画面运动检查**（`pipeline/motion_check.py`，结果写进 `motion.json`）：连续静止 ≥0.8 秒、超过 2 秒没有新动作（帧差 ≥1.5）、整片静止比例 ≥5%，任一条不合格就不出片。不要整片反复重出：用 `timeline.json` 的 `cuts` 找到出问题的场景，改 `visual.js`（加一拍：`K.frame` 的 `beats`、新元素入场、整块换色），再

```
python pipeline/scene_check.py out/<编号> <场景序号>
```

先抽帧复查有问题的场景，通过后再整片渲染。正式片必须通过运动检查；`--allow-still` 只用于调试。

失败时会说明原因（例如时长超出、缺配图、配音失败），按提示处理后重跑。

## 10. 审片并交付

1. 打开 `out/<编号>/review.jpg`（成片每秒一格，左上角是时间），对照第 7 节的画面标准逐格看：满屏、层次、相邻两格有明显变化、文字不重叠不溢出、企鹅不挡字。拿不准的时刻用 `ffmpeg -ss 秒 -i 成片.mp4 -frames:v 1 x.png` 抽原尺寸帧细看。不合格就改 `visual.js` 重跑，**自己看过、改到合格再交付**。
2. 把 `out/<编号>/<编号>.mp4` 和 `publish.json` 交给用户。说明：
   - 这是给人终审的成片，**发布时要在平台上打 AI 生成内容标识**，本 skill 不做自动发布。
   - `publish.json` 里有标题、话题标签、评论关键词，以及配图和配乐的授权记录。配乐要求署名时，把 `music.attribution` 贴进视频简介。
   - `pending_footage` 为 `true` 表示实录位置还是示意画面，等这一步有了素材包，`python tools/refill.py <编号>` 一键换成实录版。
   - `visual_tier` 为"兜底版"时，必须说"画面为兜底版"。
   - 封面暂未实现（第 18 节），请用户在平台上选帧做封面。

# 二、重做已出过的视频

## 11. 重做

用于画面标准升级或换了音色之后，把旧片按新标准重出。**配音文本不变**（已经发过、观众听过），画面和声音换新。

1. 找剧本 `out/<编号>/script.json`。如果剧本没留下来，用 `python tools/srt_scenes.py out/成片/<名>.srt` 按字幕还原：字幕之间相隔约 0.55 秒的地方是场景分界，同一场景的几句字幕按原意加上标点连成这个场景的 `vo`；标题、话题标签、评论关键词、配图从同名 `.publish.json` 取；结构、钩子写法、主题从 `data/history.json` 里这条的记录取。
   配图丢了：先 `python tools/regen_images.py`（需要 OPENAI_API_KEY）；没有 Key 时，从旧成片里配图满屏、还没叠字的那一帧截出来（裁掉旧字幕和旧标题），用 `gen_image.py --register` 登记，来源写明"截自旧成片"。
   剧本有实录槽位但原剧本没写的（未输入 skill 的视频原来也有示意槽位），按原片补回 `footage` 场景，以后录屏能直接替换。
2. 给每个场景加 `visual` 和上屏文字字段，写 `visual.js`（第 7 节）。`script_check.py` 检查时，"近 N 条用过"会把这条自己算进去，这几条可以忽略；`redo.py` 出片时会正确排除。
3. `python tools/web_tts.py out/<编号>` 用当前音色重新配音。
4. `python tools/redo.py <编号>`：同一编号重出（有可用素材包自动用实录），历史记录留在原位置。
5. 按第 10 节审片。旧成片先备份成 `<名>.旧版.mp4`，再把新片和 `publish.json`、`.srt` 复制进 `out/成片/`。

# 三、定期任务

## 12. 热点视频

只做和电商、AI 相关、一周内、有可查来源的热点。用网页搜索找，写进 `data/hot.json`：

```
[{"topic": "…", "angle": "和电商人有什么关系", "source_url": "https://…", "source_date": "2026-11-15", "relevant_to": "ecommerce", "used": false}]
```

`pick_topic.py --hot` 选中热点时，剧本写 `"type": "hot"`、`"step": null`，把这条热点原样放进 `"hot"`，结构从 `data/structures.json` 里 `"for": "hot"` 的几种选。规则：最后要落到"电商自动化"上；钩子、中段悬念、结尾转化照常；只写来源里有的说法，不编数字；引用来源里的数字的场景加 `"about": "manual"`。出片后来源链接写进 `publish.json`，这条热点自动标记为用过。其余步骤和做新视频相同。

## 13. 爆款调研与数据反馈（定期做，不是每条都做）

**调研**（需要用户先登录一次，之后小量采集公开搜索结果的文字信息，不下载视频）：

```
python research/collect.py douyin --login      # 首次：打开浏览器让用户登录
python research/collect.py douyin              # 按选题池关键词采集，每词最多 30 条
python research/digest.py tags data/research/<日期>-douyin.json   # 更新 data/tags.json
python research/digest.py top data/research/<日期>-douyin.json    # 看排名靠前的标题
```

遇到验证码或登录页会立刻停下，请用户处理。采集到 0 条会报错（页面变了），不要当成"没有爆款"。读完排名靠前的标题后，可以把新的结构或钩子写法写进 `data/research/proposals.json`（每条带 `"kind": "structure"|"hook"`），**请用户确认、把 `approved` 改成 `true` 后**再运行 `python research/digest.py merge`。

**数据反馈**：用户把每条视频的播放、完播率、点赞、收藏、涨粉填进 `data/metrics.csv`（第一行是表头），然后 `python tools/report.py` 看各结构、钩子、主题、标签的平均表现。样本不足 3 条的不下结论。

# 四、参考

## 14. 场景类型与字段

字段定义见 `tests/scene_fixtures.mjs`，完整样例 `tests/fixtures/script_ok.json`。

**`type` 决定剧本检查怎么看这个场景**（钩子、揭晓、实录、转化各有规则）；**画面由 `visual` 决定**（第 7 节）。只有不写 `visual` 的兜底版，才按 `type` 用场景库画（第 15 节）。

| 类型 | 剧本里的角色 |
|---|---|
| `hookContrast` | 人工与自动化对比（常用作开头钩子） |
| `photo` | 配图 + 两行大字（`image` 填配图文件名） |
| `counter` / `timer` | 数量 / 时间 |
| `bars` | 2–4 项数据对比 |
| `statement` | 两行大字的转折句 |
| `steps` | 分步，`hide_last` 把最后一步藏成悬念 |
| `reveal` | 揭晓悬念 |
| `footage` | 实录槽位，`slot` 为 `hook` 或 `mid`；没有实录时显示带"示意"字样的占位 |
| `cta` | 结尾转化 |

通用字段：`vo` 是配音文本，也会切成屏幕字幕；`visual` 画面档场景名；`mid_hook` `payoff` `measured` `about` 见第 4 节。

企鹅：`"mascot": {"pos": "bottomRight", "pose": "point", "say": [[0.6, "交给我！"]]}`。`pos` 可选 `topRight` `bottomRight` `big` `cta`；`pose` 可选 `base` `talk` `blink` `phone` `point` `cheer` `shock` `clip` `wave`；画面档里还可以用 `S` `x` `f` 自定位置、`move` 走位。

## 15. 内置场景库预览

不写 `visual.js`、剧本场景不写 `visual` 时，引擎按 `type` 用内置场景库（`engine/scenes.js`）画，并给每个场景加镜头推移防止整段不动。

- 剧本照第 4 节写，按第 14 节的类型填字段（`hookContrast` 的左右两栏、`counter` 的数字、`bars` 的数据条、`steps` 的步骤等，字段见 `tests/scene_fixtures.mjs`）。
- 仅在明确要预览内置场景时给 `make.py` 传 `--fallback-preview`。这种预览在 `publish.json` 标记为“兜底版”。
- 预览文件应注明“画面为兜底版”；正式出片按第 7 节补齐专属画面后重跑。

## 16. 配乐与声音

- 配乐默认由代码原创编曲（`--music compose`）：按剧本段落编排，用 GeneralUser GS 音色库（`assets/soundfont/`）的真实乐器采样渲染，每条视频的调性、和弦、乐器组都不同，不需要署名。`--music library` 改用曲库。
- 声音固定为 `assets/voice/ref.wav` + `ref.txt` 这一对参考（2026-11-18 起是拼多多发布助手 v6b 企鹅片的人声，来源见 `assets/voice/SOURCE.md`），每条视频都用它，不要换别的声音，不要运行 `tools/design_voice.py` 覆盖它。克隆参数 cfg 2.0、步数 10、种子 42。
- `tools/web_tts.py` 会把参考音复制到网页版能读的 `VoxCPM\output\gradio\ecomvoice_ref\ref.wav`（网页版只读得到自己目录里的文件），调用 `/gradio_api/call/generate`，参数 `[文本, '', {path: 参考音路径, meta:{_type:'gradio.FileData'}}, true, ref.txt 的文字, 2, false, false, 10, 42]`。

## 17. 远程会话（命令行不在用户电脑上时）

本机 Claude Code / Codex 用不到这一节。只在 claude.ai 云端会话这类"命令行是一台虚拟机、隔着电脑操控用这台电脑"的情况下：

- 配音：在用户电脑的浏览器里打开 http://127.0.0.1:8808，用页面里的 JavaScript 按第 16 节的参数**在后台循环**调接口（一段约 20–30 秒，几十段要十几分钟，不要一段一段等），把结果路径存在页面变量里轮询；参考音必须放在 `VoxCPM\output\gradio\` 下。全部生成后把各段复制成 `out/<编号>/_v6b_raw/s01.wav…`，运行 `python tools/import_voice.py out/<编号> out/<编号>/_v6b_raw`。
- 启动 VoxCPM 等 Windows 程序：用电脑操控在资源管理器里双击 `.cmd`。`tools/cmd/` 里的 `.cmd` 就是给这种情况备用的。
- 渲染可以在云端做，打包后传回用户电脑解压覆盖。

## 18. 暂未实现

- **封面**：还没有封面生成。交付时请用户在平台上选帧做封面。
- **自动发布**：不做，成片由人终审后手动发布。

## 19. 维护

- 测试：`python -m pytest` 和 `node --test tests/*.test.mjs`，改代码后全部通过才能提交（分工见 `AGENTS.md`）。
- 画面预览：`python pipeline/preview.py out/<编号> [每格秒数] [--at 秒 …]`。
- 曲库：`python tools/add_track.py 曲子.mp3 --mood upbeat --source 来源 --license 授权 [--attribution 署名行]`。没有来源和授权的曲子不会入库。
- 新姿势的企鹅：`tools/mascot_outfit.py` 加装扮，`tools/mascot_finish.py` 抠图并统一画布。

用户只需要在三处出面：提供 skill 路径（可跳过）、首次登录调研用的浏览器（`research/collect.py douyin --login` 会弹出窗口）、最后的成片终审。
