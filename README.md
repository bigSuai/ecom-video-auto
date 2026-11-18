# 电商短视频工作流 · Codex 版

从选题、录制观众技能的实际运行，到专属动效成片和版本一致的领取包。基于 [Annie-xunishangzhi/ecom-video-auto](https://github.com/Annie-xunishangzhi/ecom-video-auto) 的渲染与制作流程，新增批量执行、本机实录和领取包校验。

| 环节 | 产物 |
| --- | --- |
| 选题 | 从七个已配置的虚构业务示例选题，也可登记新的选题 ID |
| 本地实录 | 打包并执行观众技能，从当次浏览器操作、运行报告和结果中采录 |
| 制作 | 参考陶瓷杯 v2 逐镜编排专属动效，输出竖屏 MP4、字幕、封面和检查记录 |
| 领取 | 成片、实录、运行结果和观众技能 ZIP 通过同一选题关联，支持关键词查询 |

## 快速运行

在仓库根目录使用 Python 3.10–3.12、Node.js 20+、FFmpeg 和 Chromium。把 FFmpeg 与 ffprobe 加入 PATH。以下命令先验证无需配音的选题与录屏环节。

```sh
python -m pip install -r requirements.txt
npm ci
python -m playwright install chromium
npx playwright install chromium

python pipeline/series_batch.py plan --output out/demo --count 2
python pipeline/series_batch.py capture --output out/demo --topics B
```

录制结束后，`out/demo/series.json` 会列出录像、运行报告和观众领取包。模块 B 的演示用虚构陶瓷杯商品表核对同货号的价格冲突。

制作有旁白的成片时，先配置自己的 VoxCPM 参考音，或以 `--voice-cache` 提供逐段旁白。参考音可用 `python tools/setup_tts.py` 安装本地配音依赖后，通过 `python tools/design_voice.py --auto` 生成。已有合法可用的参考音时，将音频和对应文字放入本机的 `assets/voice/ref.wav` 和 `assets/voice/ref.txt`。配音与渲染可以使用不同的 Python 环境，见工作流说明。

```sh
python pipeline/series_batch.py run --output out/demo --topics B
python pipeline/resolve_claim.py --output out/demo --keyword 查价
```

在 Codex 中打开仓库并调用 `ecom-video`，或把根目录的 `SKILL.md` 路径交给智能体。[批量出片、追加新选题和领取说明](docs/批量出片与领取包.md)

## 发布范围与许可

本 Fork 的发布包含代码、分镜及虚构样例。成片、真实业务数据、当次实录和本地配音保存在运行机器上。观众技能可独立使用，入口位于 `audience/ecommerce-automation/SKILL.md`。

本项目中新写的工作流代码和观众技能按 MIT 许可发布，文件范围见 [LICENSES/README.md](LICENSES/README.md)。继承的渲染工程和素材保留各自原有权利；上游仓库当前未声明统一许可证。
