# F 客服与售后

先汇总售后清单，再关联同平台、同店铺订单和库存；把来源已发送回复、本地处理标记、待发送草稿分别展示。模块只分析用户授权提供的事实。实际取数由智能体使用当前可用的ERP、平台浏览器会话或导出工具完成，不内置账号、密码、网站选择器或旧工作台依赖。

## 执行路径

1. 观察当前账号与店铺，确认用户已授权的读取范围。读取售后、订单、库存的真实表头和少量样本；核对订单号/行号/SKU、源时间字段、时区及导出时间。遇到登录或验证码，按宿主能力让用户完成，保留已取得数据和恢复位置。
2. 根据[输入与映射](inputs.md)写标准job。保留`source_*`来源；不要把文件修改时间、智能体看到页面的时间当作订单更新时间，也不要把“本地已处理”映射成平台已回复。没有源发送记录时保留待核对状态。
3. 执行`python <skill目录>/scripts/ecommerce.py run --module F --input <job.json> --output <任务输出目录>`。查看输出的售后表、订单、库存、FAQ、时效表和issues，向用户报告优先处理的超时售后、无法关联项、库存冲突和缺失证据。
4. 可以根据有出处的店铺政策拟回复草稿；真实发送需在用户已明确授权的渠道与范围内操作。发送后重新读取平台回执，写入真实`replied_at`及`sent_evidence`再运行。只保存草稿或本地打勾不能关闭未回复问题。

## 标准job

`orders`、`inventory`、`cases`、`questions`接受对象列表，也可使用公共层的`file/mapping/defaults/scales`描述符。各标识均为文本，不能丢失前导零。

| 表 | 必要字段与口径 |
|---|---|
| orders | platform、shop_id、order_id、line_id、sku、status、quantity、updated_at；quantity为正整数，时间为来源订单更新时间 |
| inventory | platform、shop_id、sku、stock、updated_at；stock为来源明确口径的非负整数；可售/账面/锁定库存不要混列 |
| cases | platform、shop_id、case_id、received_at；建议order_id、sku、customer_alias、subject；可附replied_at、sent_evidence、local_status、draft及明确的updated_at |
| questions | platform、shop_id、question；可附answer、source。source须为智能体已经核对的答案/政策出处，而非模型猜测 |

`now`为本次检测时间，ISO格式须带时区；省略时取实际系统UTC时间。`reply_sla_hours`和`stale_after_hours`均默认24，可根据已确认店铺规则调整。下面是虚构演示输入，不表示已经连接店铺：

```json
{
  "data_kind": "synthetic",
  "now": "2026-11-17T12:00:00+00:00",
  "reply_sla_hours": 24,
  "orders": [{"platform":"demo","shop_id":"A","order_id":"0001","line_id":"1","sku":"CAT","status":"paid","quantity":1,"updated_at":"2026-11-17T10:00:00Z","source_file":"演示订单.csv"}],
  "inventory": [{"platform":"demo","shop_id":"A","sku":"CAT","stock":8,"updated_at":"2026-11-17T10:00:00Z","source_file":"演示库存.csv"}],
  "cases": [{"platform":"demo","shop_id":"A","case_id":"C1","order_id":"0001","sku":"CAT","customer_alias":"买家A","subject":"物流查询","received_at":"2026-11-16T10:00:00Z","local_status":"processed","draft":"已为您查询物流，待核对后发送。","source_file":"演示售后.csv"}],
  "questions": [{"platform":"demo","shop_id":"A","question":"多久发货？"}]
}
```

## 结果解释与恢复

`after_sales`为核心清单，优先排列超时未回复项。`reply_status=replied`只表示输入中同时有有效回复时间和非空发送证据，证据真伪仍由取数智能体核对。`sla_overdue`表示当前未完成回复且超时；已回复但回复过晚单列`reply_sla_breached`。`local_status`和`draft`保持独立列。

订单键为平台/店铺/订单号/行号，库存键为平台/店铺/SKU，售后键为平台/店铺/售后号。各键只选最新明确时间，旧行不能覆盖新行；同时间同值去重，同时间异值标`conflict`且不选库存值。冲突比较只采用本模块声明的规范业务字段，排除保留的原始别名列与来源审计；库存`5/5.0`规范后同为整数5。所有收到、回复、更新时间均先统一UTC，等价时区写法视为同一时刻。所有原行及来源留在`source_rows`。没有关联订单/库存时保持空值和问题项。

`staleness`表示已提供的源事件时间距检测时间的年龄，不证明平台已实时同步。订单和库存用`updated_at`；售后有明确`updated_at`时用该字段，否则用收到/回复事件中的较晚时间。导出时间、刷新频率与遗漏来源需智能体另行说明。缺时间的行留在原始行表并报错，不猜测最新顺序。

FAQ按同平台同店的确定性空白/标点规范化结果聚合，不做同义语义猜测。仅显示带已核对出处的答案；缺答案为待补，多个不同已确认答案为冲突，需回原政策核对。输出不能自行证明政策有效。

F每次重新计算本job的快照，不保存跨轮订单库；恢复时输入仍需包含当前要核对的完整相关导出。用户明确要求连续检查后，才可启动前台`watch --module F --input <job.json> --output <目录> --interval 60`；Ctrl+C停止。watch只重新读取输入，真正ERP/页面取数要另有授权和可用连接，不能将反复读旧文件称为实时监控。演示通过与真实账号接入、用户业务验收分别汇报。
