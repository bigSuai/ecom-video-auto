# E：批量商品素材与选择重做

本模块接收明确的商品事实，产出可打开的真实文件，并用运行目录中的 `manifest.json` 保存版本、来源、权利依据及选择状态。商品由 `platform + shop_id + sku` 共同识别；同 SKU 的不同店铺分别生成文件和版本。

## 选择路线

1. 先检查宿主当前可用的图片、视频、设计工具与它们的调用说明，沿用用户在当前任务已给的授权。用户要求 AI 商品图、场景图或商品视频时，由宿主调用这些工具。按商品逐一整理图片、名称、规格、价格、已知卖点及风格，再批量生成并收集工具实际返回的本地文件。服务权限、收费和账号使用按本次用户授权处理。本脚本不调用生成服务、不读取 API Key。
2. 将宿主真实生成的文件交给 `mode: "import_generated"` 注册。保留工具名称、作业 ID、输入来源权利和输出使用依据，检查文件实际能打开；导入 MP4 会用 FFmpeg 解码。工具只给预览链接时先按工具允许的方式获得本地文件，不能把链接、空文件或改过后缀的文件当成果。
3. 用户明确需要本地版式初稿时才用 `mode: "template"`。此路线会生成主图 PNG、图文 PNG、详情 HTML、静音 MP4，并显式标注“模板初稿”。它使用现有商品图和确定事实排版；缺图时显示实拍图占位，不画出虚构商品。MP4 是静态版式配淡入的演示视频，不应描述成 AI 场景视频。

批量初稿完成后，向用户展示对应文件，请其按素材 ID 选择保留项及需要重做项。保留操作只持久化选择；重做必须产生新文件与实际内容变化，并保留已选旧版本。未知权利可以预览，所有选中项权利核实后才能导出。

## 输入

`products` 可为标准对象列表，也可使用总入口的文件映射格式。单个商品的标准字段如下；中文 `name`、`spec` 与卖点均只采用输入内容。

```json
{
  "mode": "template",
  "style": "minimal",
  "duration": 2,
  "products": [
    {
      "platform": "demo",
      "shop_id": "demo-shop",
      "sku": "DEMO-001",
      "name": "演示水杯",
      "spec": "蓝色 350ml",
      "price": "19.90",
      "selling_points": ["手柄设计"],
      "image": "inputs/cup.png",
      "rights": {
        "status": "original",
        "evidence": "卖家对本批商品图与文案的原创声明；附件编号 RIGHTS-001"
      }
    }
  ]
}
```

- `mode` 必须显式填写 `template` 或 `import_generated`。
- `style` 为 `minimal`（简洁蓝白、直线版式）或 `warm`（暖色、圆角版式），默认 `minimal`。
- `duration` 默认 2 秒，供快速演示；可自定义为 3–15 整数秒。模板 MP4 无音轨。
- `image` 可省略。相对路径以输入 job 文件所在目录为基准。输入图会按哈希复制到运行目录的 `sources/`，后续重做使用此副本。
- 模板依赖 Pillow、可用中文字体和含 `libx264` 的 FFmpeg。`font` 可指定 TTF/TTC/OTF 文件，未给时从当前系统字体目录发现中文字体；不打包或擅自复制系统字体。
- `ffmpeg` 可指定当前机器的真实可执行文件路径，否则使用 PATH。发现 `.cmd`、`.bat`、`.ps1` 包装脚本会停止并要求真实可执行文件。脚本始终以参数数组运行 FFmpeg，不拼 shell 命令。
- `rights.status` 支持 `original`、`licensed`、`authorized`、`public_domain`；可导出时还必须有非空 `evidence`。省略、未知状态或无依据只允许预览。此记录保存用户证据，不代替宿主对来源和授权范围的核实。

没有来源依据时不要替用户填写“原创”。补齐原始输入的权利依据后重新运行并重新选择；保留旧运行以便追溯。

## 注册宿主生成结果

使用同样的 `products`、`style`，改用 `import_generated` 并加入 `generated`：

```json
{
  "mode": "import_generated",
  "style": "warm",
  "products": [
    {
      "platform": "demo", "shop_id": "demo-shop", "sku": "DEMO-001",
      "name": "演示水杯", "spec": "蓝色 350ml", "price": "19.90",
      "rights": {"status": "original", "evidence": "本批原始商品资料的原创声明 RIGHTS-001"}
    }
  ],
  "generated": [
    {
      "platform": "demo", "shop_id": "demo-shop", "sku": "DEMO-001",
      "type": "main_image",
      "path": "generated/cup-main.png",
      "provider": "宿主实际使用的生成工具名称",
      "job_id": "实际返回的作业编号",
      "rights": {"status": "licensed", "evidence": "输出商用许可条款及本次生成授权记录"},
      "input_rights": [
        {"status": "original", "evidence": "输入参考图原创声明 RIGHTS-001"}
      ]
    }
  ]
}
```

`type` 支持 `main_image`、`graphic`、`detail`、`video`。图片支持 PNG/JPG/WebP，详情为 HTML，视频为 MP4；详情应由宿主生成可独立打开的自包含页面，避免依赖未登记文件。MP4 导入另需真实 FFmpeg 可执行文件进行解码验证。每项必须匹配 `products` 内唯一商品，并提供真实 `provider`、`job_id`。原始商品的 `rights` 会自动加入输入权利记录，输出许可不能替代输入授权。

宿主处理重做时，先根据用户意见改变构图、配色、商品实拍图的合法处理或已核实文案，然后调用当前可用生成工具，收集新文件及新作业 ID，调用 `append_generated` 追加到原 manifest。相同商品、素材类型与旧版本完全同字节的文件会被拒绝，不能仅改文件名冒充重做。

## 脚本接口与产物

总入口执行 `python scripts/ecommerce.py run --module E --input JOB.json --output USER_OUTPUT`。每次运行应使用自己的输出目录；job 的文件路径相对输入文件解析。运行中生成的绝对路径属于用户当前机器，skill 本身不依赖作者路径、账号或源码全局目录。

`scripts/media.py` 提供：

```python
run(job: dict, out: Path, emit=None) -> dict
select_item(manifest_path, item_id, selected: bool) -> dict
redo_item(manifest_path, item_id, emit=None, *, ffmpeg=None, font=None) -> dict
append_generated(manifest_path, generated: list, job_dir=None, *, ffmpeg=None) -> dict
export_selected(manifest_path, destination) -> dict
```

- `select_item` 保存选择到 manifest；再次设为 `False` 可取消。选中与草稿状态分别为 `selected`、`draft`。
- `redo_item` 适用于本地模板，改变布局、配色等并新增版本；返回新素材对象，新版本默认未选。重做宿主生成素材时会提示使用宿主实际生成后调用 `append_generated`。
- `append_generated` 接收与 job 中相同的 `generated` 列表。相对 `path` 以 `job_dir` 为基准，默认 manifest 目录。预先检查整批输入后复制文件、递增版本并保存，原选择不变。
- `export_selected` 先核对所有选中项的输入和输出权利、证据、真实文件及 SHA-256，再复制选中交付文件及 `sources.json`。有一项未知权利、缺文件或哈希不符时整次导出停止。目标必须为空且与运行目录分开，避免混入未选素材。详情 HTML 使用内嵌商品图，所以单选导出后仍可打开。

manifest 中每项包含 `id`、`product`、`type`、`style`、`version`、相对 `path`、文件 `sha256`、来源 `source`、`rights`、`selected`、`status` 和 `generation`。`source` 保存原始资料哈希、图片来源哈希、权利和证据；`generation` 区分模板与宿主工具并保存工具名、作业 ID。`products` 保存重做输入快照，图片副本与素材都位于本次运行目录。整个运行目录可复制到其他机器后继续挑选与模板重做，再发现该机器的依赖，或明确提供 `ffmpeg` / `font`。

验收时实际打开 PNG 与 HTML，检查文字、规格、价格、缺图占位与风格，播放 MP4 并确认时长及音轨；挑选一项、重做并检查新旧文件内容不同，复制运行目录后再操作一次；最终检查导出目录只有选中交付文件与来源清单。模板技术可播放与文件完整性通过后，商品事实、视觉效果与最终使用仍由用户审核。
