# 给 agent 的说明

本工程是一个制作电商推广短视频的 skill。做视频时，读取并按根目录的 `SKILL.md` 执行。
所有工作通过 `pipeline/`、`research/` 和 `tools/` 里的脚本完成，命令由你在用户电脑上直接运行，不要让用户去点文件。
从包含本文件的工程根目录运行命令。

## 分工（改代码时必须遵守）

本工程由两类模型协作开发，各管一块，只通过固定格式的文件对接。

| 部分 | 负责的模型 | 目录 / 文件 |
|---|---|---|
| **视频画面**：动效场景、渲染、字幕、企鹅动作、转场、封面、合成 | Codex / Claude 等具有画面制作能力的 agent | `engine/`、`pipeline/render.js` `shots.js` `compile_script.py` `make.py` 的渲染与合成部分、`pipeline/compose.py` `mix.py` `audio.py`、`assets/` |
| **后端数据**：爆款采集、信息整理与分类、标签、选题、结构库、查重、数据反馈 | GPT（Codex） | `research/`、`data/`、`pipeline/pick_topic.py` `dedupe.py` `script_check.py`、`tools/report.py` |
| 共用：录屏与素材包、配音、安全闸 | 改动前在 PR 里说明 | `pipeline/pack.py` `guard.py` `record_*.py` `frames_pack.py` `highlights.py` `mask.py` `tts.py`、`tools/kimi_*.py` |

规则：
- **不要改另一方负责的目录**。确实需要时，在 PR 描述里写明原因，由用户决定。
- **接口文件的格式是合同**：`script.json`（剧本，样例 `tests/fixtures/script_ok.json`）、`pack.json`（素材包，`pipeline/pack.py`）、`data/*.json`、`publish.json`。改格式前先在 `docs/接口约定.md` 写明新格式，并同时更新样例和测试。
- **每次改动都要跑全部测试**：`python -m pytest` 和 `node --test tests/*.test.mjs`，全部通过才能提交。只修改自己负责部分的测试；需要改对方的测试时同样先说明。
- **在自己的分支上工作**（`frontend/...` 或 `backend/...`），由用户确认后合并到 `main`。
- 视频画面的标准见 `docs/2026-11-17-视频画面重做需求.md`：动效要多、要华丽，不能像 PPT。Codex 默认执行陶瓷杯 v2 的专属动效标准，正式批量出片通过 `pipeline/series_batch.py` 绑定观众领取包与实录，具体见 `docs/批量出片与领取包.md`。

## 不能提交的东西

`.secrets/`（浏览器登录状态）、任何 `.env` 或 API Key、`out/` 下的成片和截图、`node_modules/`。`.gitignore` 已经排除，提交前再用 `git status` 看一眼。
