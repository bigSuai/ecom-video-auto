# D 多平台、多店复盘

先在授权的每家店后台观察当前报表页面，选定同一业务期间，逐店导出订单、退款、广告，保存实际来源与导出时刻。不要套作者店铺ID或假定所有平台有同一导出按钮。宿主没有下载能力时，可用用户已导出文件，准确说明取数范围。

job必填start_date/end_date（YYYY-MM-DD，含首尾，最多366天）。三表可用列表或file/mapping/defaults/scales；所有记录必须有platform/shop_id/currency，编码文本。平台不同时间字段先转统一业务日，确认后才写date。

| 表 | 字段 |
|---|---|
| orders | order_id,line_id,date,sku,quantity,paid_amount,status=paid/cancelled；unit_cost/shipping_cost/packing_cost/platform_fee可缺但不可当0 |
| refunds | refund_id,order_id,line_id,date,amount,recovered_cost可缺；关联原订单，跨期原单也需输入 |
| ads | ad_id,date,spend；每店/业务日/币种须明确记录，未投放用spend=0 |

paid_amount为商家优惠后且未再扣输入费用的支付额；unit_cost为单件成本，其余为该订单行已经分摊的费用总额。若源为结算实收或未分摊跨SKU费用，先核对口径，不能直接填入造成重复扣费。退款按退款发生日，recovered_cost只填明确收回采购成本；退款不自动等于退货。

复合键含平台店铺：重复同值去重，同键冲突整键隔离并列问题，不让文件顺序决定财务数。退单须关联有效已支付订单，累计不得超过原支付；异常原始事实保留facts。总览按币种、stores按店，daily按日期，skus不分摊店铺广告，贡献口径before_shop_ads。

缺成本/费用/回收成本或广告日期覆盖时，相关贡献为null；已知小计仍可核对。报告中的贡献不称净利润。先看summary/issues/facts是否完整，再核对overview与分店表，形成conclusions和具体待办。前后期比较时分别对等长期间运行，再由智能体按同币种同店口径比较；不要平均各店变化率，不把变化原因编成事实。
