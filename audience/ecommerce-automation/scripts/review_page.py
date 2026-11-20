"""Portable report inspector embedded in each HTML report. Works offline."""
import json


def inspector(result):
    payload = json.dumps({"id": result.get("run_id"), "tables": {name: rows[:1000] for name, rows in result.get("tables", {}).items()}},
                         ensure_ascii=False).replace("<", "\\u003c")
    return UI.replace("__DATA__", payload)


UI = r'''
<style>
:root{color-scheme:dark}body{margin:0!important;max-width:none!important;padding:0!important;background:#14262d!important;color:#f6f2df!important;font:18px "Microsoft YaHei",sans-serif!important}body>h1,body>p,body>pre,body>section,body>h2{display:none}
#desk *{box-sizing:border-box}#desk{min-height:100vh;background:radial-gradient(ellipse at 65% 0%,#24443f,transparent 72%),#14262d}
#desk header{display:flex;justify-content:space-between;align-items:center;padding:13px 24px;background:#102128;border-bottom:1px solid #48625e;color:#ffdc8b;font-weight:800}#desk header small{color:#bccec9}
#desk main{padding:12px 25px;max-width:1320px;margin:auto}#desk nav{display:flex;gap:6px;align-items:center;overflow:auto;padding-bottom:7px}
#desk button,#desk input,#desk select{font:inherit;border:1px solid #689187;color:#f0f4ed;background:#233e40;border-radius:6px;padding:7px 12px;cursor:pointer}
#desk button[aria-pressed=true],#desk button:hover,#desk button:focus{background:#d0efb3;color:#19382c}
#desk .tools{display:flex;align-items:center;gap:12px;margin:6px 0 10px}#desk input{background:#10282d;width:37%}#desk .count{color:#c1dbba;font-size:17px}
#desk .record{display:grid;grid-template-columns:52px 1fr 98px;align-items:center;gap:12px;width:100%;margin:4px 0;text-align:left;padding:10px 13px;min-height:46px}
#desk .record b{color:#ecba72}#desk .record span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#desk aside{border-left:6px solid #ffc572;border-radius:8px;padding:12px 18px;background:#f5ecd7;color:#172d30;margin-top:9px;animation:slide .22s ease-out}
#desk aside h3{margin:0 0 8px}#desk dl{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px 15px;margin:7px 0}#desk dt{font-size:14px;color:#4c655d}#desk dd{margin:3px 0;overflow-wrap:anywhere;font-weight:bold;font-size:21px}
#desk footer{display:flex;align-items:center;gap:15px}#desk output{color:#274b45}#desk .rows{max-height:250px;overflow:auto}#desk:has(aside:not([hidden])) .rows{max-height:102px}
@keyframes slide{from{transform:translateY(12px);opacity:.3}to{transform:none;opacity:1}}
</style>
<div id="desk"><header>电商助手　/　运行结果 <small>本地复核台</small></header><main><nav><label>结果表 <select id="tables"></select></label><button id="original">完整报告</button></nav>
<div class="tools"><input id="query" type="search" placeholder="输入货号、店铺或状态" aria-label="筛选记录"><span class="count"></span></div>
<div class="rows"></div><aside hidden><h3>记录详情</h3><dl></dl><footer><button id="exportrow">导出这条记录</button><output></output></footer></aside></main></div>
<script type="application/json" id="run-data">__DATA__</script><script>
(()=>{
const data=JSON.parse(document.querySelector('#run-data').textContent);
const $=s=>document.querySelector('#desk '+s), el=t=>document.createElement(t);
const names={normalized:'标准化商品',issues:'问题清单',stores:'分店账本',overview:'合计',after_sales:'售后工单',keywords:'关键词',ad_totals:'投放汇总',products:'本店商品',comparisons:'竞品对照',queue:'准备队列',media_items:'素材清单'};
const fields={sku:'货号',source_row:'原表行',message:'检查结果',name:'商品',price:'价格',shop_id:'店铺',paid_amount:'实付',refund_amount:'退款',net_sales:'净销售额',ad_spend:'广告费',case_id:'工单号',subject:'咨询主题',reply_status:'回复状态',elapsed_hours:'经过小时',sla_overdue:'超时',local_status:'店内状态',platform:'平台',keyword:'关键词',attribution_window:'归因窗口',spend:'花费',roas:'广告回报',own_price:'本店价格',own_price_gap:'本店价差',comparable:'可比',spec:'规格',type:'类型',version:'版本',status:'状态'};
const priorities={issues:['source_row','sku','message','category'],normalized:['sku','price','source_row','name'],stores:['shop_id','paid_amount','refund_amount','net_sales'],overview:['paid_amount','refund_amount','net_sales','ad_spend'],after_sales:['case_id','subject','local_status','reply_status','elapsed_hours','sla_overdue'],keywords:['keyword','platform','attribution_window','roas'],ad_totals:['platform','attribution_window','spend','roas'],products:['sku','spec','price'],comparisons:['sku','own_price','price','comparable','own_price_gap'],queue:['sku','shop_id','status'],media_items:['type','version','status']};
const display=v=>typeof v==='object'&&v!==null?JSON.stringify(v):String(v??'');
let selection=null;
for(const name of Object.keys(data.tables)){$('#tables').add(new Option(names[name]||name,name))}
function draw(){
 const table=$('#tables').value, q=$('#query').value.trim().toLowerCase();
 const rows=data.tables[table]||[];const area=$('.rows');area.replaceChildren();$('aside').hidden=true;selection=null;
 let count=0;
 rows.forEach((row,i)=>{
  if(q&&!Object.values(row).some(v=>display(v).toLowerCase().includes(q)))return;
  count++;const keys=[...new Set([...(priorities[table]||[]),...Object.keys(row)])].filter(k=>k in row);
  const btn=el('button');btn.className='record';btn.dataset.index=i;
  const num=el('b');num.textContent=String(i+1).padStart(2,'0');const info=el('span');
  info.textContent=keys.slice(0,4).map(k=>(fields[k]||k)+' '+display(row[k])).join('　');
  const open=el('small');open.textContent='查看详情 ↗';btn.append(num,info,open);area.append(btn);
  btn.onclick=()=>{selection={run_id:data.id,table,index:i,row};$('aside').hidden=false;$('aside h3').textContent=(names[table]||table)+'　/　第 '+(i+1)+' 条';$('output').textContent='';
   $('dl').replaceChildren(...keys.slice(0,6).map(k=>{const a=el('div'),b=el('dt'),v=el('dd');b.textContent=fields[k]||k;v.textContent=display(row[k]);a.append(b,v);return a}));
   const prev=$('aside img');if(prev)prev.remove();
   if(table==='media_items'&&/^assets\/[\w-]+\/[\w.-]+\.(png|jpe?g|webp)$/i.test(row.path)){
     const img=el('img');img.alt='本次生成的素材';img.src=row.path;img.style.cssText='width:96px;height:96px;float:right;object-fit:contain;background:white';$('aside').prepend(img);}
  };
 });$('.count').textContent=count+' / '+rows.length+' 条预览记录';
}
$('#original').onclick=()=>{const w=window.open('','_blank');if(!w)return;w.document.title='完整运行报告';for(const e of document.querySelectorAll('body>h1,body>p,body>pre,body>section,body>h2'))w.document.body.appendChild(w.document.importNode(e,true));};
$('#tables').onchange=()=>{$('#query').value='';draw()};$('#query').oninput=draw;
$('#exportrow').onclick=()=>{if(!selection)return;const url=URL.createObjectURL(new Blob([JSON.stringify(selection,null,2)],{type:'application/json'}));const a=el('a');a.href=url;a.download=selection.table+'-'+(selection.index+1)+'.json';a.click();setTimeout(()=>URL.revokeObjectURL(url),1000);$('output').textContent='已导出所选原始记录';};draw();
})();</script>'''

