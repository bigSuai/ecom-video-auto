# C 营销推广整理

智能体先读取用户授权的商家平台活动/营销页与推广报表。活动只读取可见规则、截止、适用商品及资格；不能凭活动标题推断报名资格。登录由人完成，不报名或投放花钱。

activities字段：platform/shop_id/activity_id/name/deadline/eligibility/source_url。deadline必须ISO时间并带时区；如页面只给日期，先确认平台截止时区和具体时刻，不默认23:59。来源缺截止时留问题。job.now可固定演示时间，真实任务不沿用演示日期。

keywords字段：platform/shop_id/date/keyword/currency/impressions/clicks/spend/conversions/attributed_revenue/attribution_window/metric_basis。对照实际导出列，用显式mapping和scales统一字段与分元单位，再运行C。不同币种、归因窗口、metric_basis分组。表格数据缺失保留为空，不能用店铺支付总额替代广告归因收入。

CTR=clicks/impressions、CPC=spend/clicks、CVR=conversions/clicks、ROAS=attributed_revenue/spend；分母0或所需输入缺失返回null。百分比显示时乘100，脚本返回比率本值。ad_totals按合计分子分母重算。

结合测算、来源和约束整理可用关键词与待验证建议，不把历史比率称为平台预测。activities按真实时区截止排序，过期明确；人工决定活动与投放。提醒保存在任务结果；若用户明确需要持续扫描，可启动前台watch，保持窗口并说明Ctrl+C结束。没有运行watch或用户的日程工具时不声称后台持续提醒。
