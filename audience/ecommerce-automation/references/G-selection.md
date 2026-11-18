# G 选品与价格提醒

由智能体读取用户已授权的ERP、竞品页面或导出资料，整理同款证据、价格条件和来源时间，再交脚本计算价差与变价。此模块不访问网络、不登录账号、不自动改价，也不创建工作台或后台计划。可用行业和单品汇总帮助挑选候选，不能用缺失销量编排名。

## 取数与执行

先确认平台、店铺、商品及关注竞品范围，观察真实页面/导出表头，记录币种、规格、常规价/券后价等价格类型、是否可售及观察时间。相似名称只产生候选；核对规格、包装、型号与可用同款证据后才填`match_confirmed=true`。浏览器和ERP读取按宿主实际能力与用户授权执行；遇到登录、验证码或无下载工具，保留当前输入，使用用户导出或等待所需操作，不编造已接入状态。

按[输入与映射](inputs.md)生成job，执行`python <skill目录>/scripts/ecommerce.py run --module G --input <job.json> --output <任务输出目录>`。核对`comparisons`、`alerts`、`industry_summary`、`industry_products`与issues，向用户给出可比较竞品、价格下降、当前价差和来源不足的具体清单；改价决定交回用户或已明确授权的后续流程。

| 表 | 字段与口径 |
|---|---|
| products | platform、shop_id、sku、name、currency、price、spec、price_type；为自店当前价，不能把不同规格塞进同一SKU |
| snapshots | platform、shop_id、sku、competitor_id、currency、price、spec、price_type、available、observed_at、match_confirmed；可附product_name、changed_at、source_url及source_* |
| industry | category、product、currency；可附units、revenue、source_url。明确期间、范围和来源口径后才放在同一job汇总 |

`available`与`match_confirmed`使用布尔值；CSV可用明确的`true/false`文本。`unknown`、空白或其他非法布尔文本列为`invalid_boolean`，该行暂停比较，不能静默当成不可售或未确认。价格、销量与收入用十进制非负有限数，最多12位小数、最大1e18；NaN/Infinity拒绝。币种不得跨币种相加，不做汇率转换。规格和价格类型采用事先核对后的明确文本；脚本只做精确相等检查，不推算500g与1kg折算价。

`now`为检测时间，可省略以使用实际系统UTC。`drop_threshold_percent`默认5，`absolute_threshold`可选，任意一个阈值达到便提醒；绝对阈值使用该行币种单位。`stale_after_hours`默认24，过期观察仍可展示并报问题，暂停对它产生新提醒。下面是虚构输入：

```json
{
  "data_kind": "synthetic",
  "now": "2026-11-17T12:00:00+00:00",
  "drop_threshold_percent": "5",
  "products": [{"platform":"demo","shop_id":"A","sku":"CAT","name":"演示猫粮","currency":"CNY","price":"100","spec":"1kg","price_type":"regular"}],
  "snapshots": [{"platform":"demo","shop_id":"A","sku":"CAT","competitor_id":"R1","product_name":"演示猫粮","currency":"CNY","price":"90","spec":"1kg","price_type":"regular","available":true,"match_confirmed":true,"observed_at":"2026-11-17T11:00:00Z","source_url":"https://example.test/demo-product"}],
  "industry": [{"category":"演示宠物食品","product":"演示猫粮","currency":"CNY","revenue":"300"}]
}
```

## 比较、提醒和时间证据

只有已确认同款、可售且币种/规格/价格类型都与自店一致的竞品进入计算。状态键包含平台、店铺、SKU、竞品ID及这些价格条件，不跨店、不把不同币种当同一基线。自店重复商品事实冲突时暂停该商品比较。冲突签名只比较规范业务字段，保留的原始别名列、`_raw`和来源审计不参与；经显式分转元映射的`10000/10000.0`同为规范价格100。

`own_price_gap=自店价-竞品价`，正值表示竞品更便宜。`price_drop`比较上一轮同竞品同条件基线与本轮价格，下降达到百分比或绝对阈值才告警。首次没有旧基线时，竞品较低只记`initial_price_gap`，不能称为刚刚降价。同一次job对同键只取最新`observed_at`；同时间冲突不选价，乱序旧快照不覆盖更晚观察，同快照和同提醒ID不重复提醒。商品名称不参与自动确认同款。

每条提醒写入`alerts/<alert_id>.json`。表中分别保留来源明确提供的`changed_at`、取数者提供的`observed_at`、本轮逻辑`detected_at`、真实系统检测时刻`actual_detected_at`和实际写提醒时的`written_at`。`detected_to_write_seconds`仅使用本次程序单调时钟计算实际处理间隔，`processing_delay_basis=monotonic_clock`，不会将历史演示时间与真实写入时间相减。

显式传入`now`表示场景时钟，保留该逻辑检测时间并标`timing_basis=scenario_clock`；来源变更到观察、观察到逻辑检测的数值标`source_delay_basis=scenario_supplied_timestamps`，仅为给定场景计算，不能作为实测平台延迟。省略`now`时使用真实系统检测时刻，`timing_basis=system_clock`且`detected_at=actual_detected_at`，来源时间差仍以`supplied_source_timestamps`注明输入证据口径。没有平台真实变更时间，`changed_at`及变更到观察延迟保持空值。若观察早于变更、逻辑检测早于观察或真实墙钟倒退，列出`negative_delay`；实际处理耗时仍以单调时钟为准。真实监测通常省略`now`。

行业汇总按类别与币种，单品汇总再按商品名分组。`known_units/known_revenue`只求已知行小计，任何同行缺失使该组总量`units/revenue=null`，同时显示缺失行数。没有销量时只报告已知收入和数据缺口；不同期间或不同统计范围的数据先由智能体核对，不能混成销量事实。

## 连续检查与恢复

`run(job, out, emit=None)`返回`summary/tables/issues/state`。runner将成功结果状态保存为本轮目录的`state.json`；恢复job可填`"state_file":"<最近成功轮次>/state.json"`，相对路径以job所在目录为根；也可直接放入上一轮完整`state`。`baselines`保存可比较基线；`latest_snapshots`保留包含不可售/未匹配在内的最新有效观察，避免后来读到的旧可售导出触发误报；`seen_snapshot_ids`记录已见观察，`compared_snapshot_ids`记录已完成有效比较，`seen_alert_ids`记录已生成提醒。缺少自店商品等依赖修复后，可对仍是最新的同一快照完成首次有效比较，不会被“已见”永久阻断；已完成比较的重复和乱序旧快照仍不重复提醒。丢弃状态会变成新的首次观察，需向用户说明。恢复前检查输入真实来源时间；不要编辑历史提醒伪造已发送通知。

用户明确要求启动连续检查后，可运行前台`watch --module G --input <job.json> --output <目录> --interval 60`，用Ctrl+C停止。watch只重新读输入文件并在本次进程轮次间传状态；竞品页面/ERP刷新仍需已授权取数连接或由智能体执行，单靠watch不能采集网页。恢复新进程时保留最近状态。不能根据“需要定期关注”自行创建常驻任务或后台计划。

演示数据验证只证明本地计算与提醒文件可运行。真实实接另须记录账号/来源范围、同款证据、实际刷新与检测时刻，以及用户确认结果；提醒文件是本地待审事项，不等于平台通知或实际改价。
