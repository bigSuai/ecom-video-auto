"""Loopback-only browser acceptance fixture. All products and operations are fake.

Start: python scripts/demo_backend.py --port 0
The first stdout line is JSON containing the actual URL. Keep the process alive
while using the host browser. No merchant account, credentials or network service
is used. Mutation events can be inspected at /mock/events.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import csv
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import io
import json
from pathlib import Path
import threading
from urllib.parse import urlsplit


FIELDS = ("title", "category", "spec", "price", "stock")
PRODUCTS = [
    {"id": "demo-shop-a-cup", "platform": "demo", "shop_id": "demo-shop-a", "sku": "DEMO-CUP-01",
     "title": "演示陶瓷水杯", "category": "家居/水杯", "spec": "蓝色 350ml", "price": "19.90", "stock": 8,
     "images": []},
    {"id": "demo-shop-a-bag", "platform": "demo", "shop_id": "demo-shop-a", "sku": "DEMO-BAG-02",
     "title": "演示棉布袋", "category": "箱包/购物袋", "spec": "米白色 30cm", "price": "12.50", "stock": 12,
     "images": []},
    {"id": "demo-shop-b-cup", "platform": "demo", "shop_id": "demo-shop-b", "sku": "DEMO-CUP-01",
     "title": "演示陶瓷水杯B店", "category": "家居/水杯", "spec": "绿色 350ml", "price": "21.00", "stock": 5,
     "images": []},
]
ACTIVITIES = [
    {"activity_id": "MOCK-ACT-001", "platform": "demo", "shop_id": "demo-shop-a", "name": "演示冬季会场",
     "status": "报名中", "start_date": "2026-11-20", "end_date": "2026-11-27", "category": "家居",
     "threshold": "活动价不高于日常价90%", "fee_rate": "0.02", "source": "本地虚构演示"},
    {"activity_id": "MOCK-ACT-002", "platform": "demo", "shop_id": "demo-shop-b", "name": "演示包袋专场",
     "status": "待开始", "start_date": "2026-12-01", "end_date": "2026-12-03", "category": "箱包",
     "threshold": "可售库存至少20件", "fee_rate": "0.03", "source": "本地虚构演示"},
]
for _index, _activity in enumerate(ACTIVITIES):
    _activity.update(deadline=('2026-11-19T18:00:00+08:00' if _index == 0 else '2026-11-30T18:00:00+08:00'),
                     eligibility=_activity['threshold'], source_url='local-fixture:activities')

# Separate synthetic event ledger, not inferred orders from the aggregate report.
LEDGER = {'orders': [], 'refunds': [], 'ads': []}
for _platform, _shop, _paid, _cost, _ad in (
    ('demo-a', 'store-1', '100', '40', '5'),
    ('demo-a', 'store-2', '80', '30', '4'),
    ('demo-b', 'store-3', '50', '20', '3')):
    LEDGER['orders'].append(dict(platform=_platform, shop_id=_shop, order_id='SAME-ORDER-1', line_id='1',
        date='2026-11-16', sku='SAME-SKU', currency='CNY', quantity='1', paid_amount=_paid,
        status='paid', unit_cost=_cost, shipping_cost='2', packing_cost='1', platform_fee='1'))
    LEDGER['ads'].append(dict(platform=_platform, shop_id=_shop, ad_id='DAILY', date='2026-11-16', currency='CNY', spend=_ad))
LEDGER['refunds'].append(dict(platform='demo-a', shop_id='store-1', refund_id='REF-1',
    order_id='SAME-ORDER-1', line_id='1', date='2026-11-16', currency='CNY', amount='20', recovered_cost='4'))
REPORTS = [
    {"date": "2026-11-15", "platform": "demo", "shop_id": "demo-shop-a", "sku": "DEMO-CUP-01",
     "orders": 3, "units": 4, "revenue": "79.60", "cost": "32.00", "refunds": "0.00", "ad_spend": "6.00"},
    {"date": "2026-11-16", "platform": "demo", "shop_id": "demo-shop-a", "sku": "DEMO-BAG-02",
     "orders": 2, "units": 2, "revenue": "25.00", "cost": "10.00", "refunds": "0.00", "ad_spend": "2.00"},
    {"date": "2026-11-16", "platform": "demo", "shop_id": "demo-shop-b", "sku": "DEMO-CUP-01",
     "orders": 1, "units": 1, "revenue": "21.00", "cost": "9.00", "refunds": "0.00", "ad_spend": "1.00"},
]


STYLE = """
body{font:16px system-ui,sans-serif;color:#172e35;background:#f2f5f3;margin:0}
main{max-width:1020px;margin:28px auto;padding:26px;background:white;border-radius:14px}
nav{display:flex;gap:20px;margin:18px 0}a{color:#176b61}.demo{background:#fff0ca;padding:12px;border-radius:8px}
label{font-weight:600;display:block;margin:14px 0 6px}input,select{box-sizing:border-box;font:inherit;padding:10px;border:1px solid #9fb0b1;border-radius:6px;max-width:100%}
input:not([type=file]):not([type=checkbox]){width:100%}select{min-width:360px}
.field{display:grid;grid-template-columns:1fr 132px;gap:8px;align-items:end}.field label{grid-column:1/-1;margin-bottom:0}
.readback{grid-column:1/-1;color:#465e65;font-size:14px;margin:0 0 7px;white-space:pre-wrap}
button,.download{font:inherit;padding:10px 15px;border:0;border-radius:6px;background:#176b61;color:white;cursor:pointer;display:inline-block;text-decoration:none}
button:disabled{background:#9aa9aa;cursor:default}.actions{display:flex;gap:10px;flex-wrap:wrap;margin:20px 0}
.status{padding:12px;background:#e9f4ef;border-radius:6px;white-space:pre-wrap}.expected{background:#f5f7f8;padding:12px;white-space:pre-wrap}
table{border-collapse:collapse;width:100%;margin:14px 0}th,td{border:1px solid #c8d3d5;padding:9px;text-align:left}
.preview{display:flex;gap:10px}.preview img{height:90px;max-width:150px;object-fit:contain}
dialog{max-width:650px;border:1px solid #9fb0b1;border-radius:10px}pre{white-space:pre-wrap;overflow-wrap:anywhere}
small{color:#536f74}h1{margin:0 0 12px;font-size:28px}
"""


def _page(title, body, script=""):
    return (f'<!doctype html><html lang="zh-CN"><head><meta charset="utf-8"><title>{title} · 本地演示</title>'
            f'<meta name="viewport" content="width=device-width,initial-scale=1"><style>{STYLE}</style></head>'
            f'<body><main><h1>{title}</h1><p class="demo" role="note">本地浏览器验收 · 全部为虚构数据 · 不连接真实平台，不会真实上架或报名。</p>'
            '<nav aria-label="演示导航"><a href="/mock/listing">批量商品填报</a><a href="/mock/activities">活动查询</a>'
            '<a href="/mock/reports">经营报表</a></nav>' + body + '</main>'
            + (f'<script>{script}</script>' if script else '') + '</body></html>')


def listing_page():
    labels = {"title": "商品标题", "category": "商品类目", "spec": "规格", "price": "价格（元）", "stock": "库存（件）"}
    fields = "".join(f'<div class="field"><label for="{field}">{labels[field]}</label>'
                     f'<input id="{field}" name="{field}" type="text" autocomplete="off"'
                     + (' inputmode="decimal"' if field in ("price", "stock") else '')
                     + f'><button type="button" data-verify-field="{field}" id="verify-{field}">核验{labels[field]}</button>'
                     f'<p class="readback" id="state-{field}" aria-live="polite">未填写 · 未核验</p></div>'
                     for field in FIELDS)
    body = ('<label for="product-select">选择演示商品（平台 / 店铺 / SKU）</label>'
            '<select id="product-select" aria-label="选择演示商品"></select>'
            '<p id="current-identity" role="status"></p><details><summary>当前商品的虚构期望资料</summary>'
            '<pre class="expected" id="expected-data"></pre></details>'
            '<form id="listing-form" onsubmit="return false">' + fields
            + '<label for="images">本地演示图片（可选）</label><input id="images" name="images" type="file" accept="image/*" multiple>'
            '<p id="image-state" class="readback">尚未上传图片</p><div id="image-previews" class="preview"></div>'
            '<div class="actions"><button type="button" id="verify-all">读取并核验全部字段</button>'
            '<button type="button" id="save-draft">保存本地演示草稿</button>'
            '<button type="button" id="review-submit" disabled>核对并确认提交（仅演示）</button></div></form>'
            '<p id="overall-state" class="status" role="status" aria-live="polite">prepared：等待填写</p>'
            '<p><small>浏览器 smoke 验收应停在“核对并确认提交”按钮前。每个字段的读回值与核验结果均可直接观察。</small></p>'
            '<dialog id="confirm-dialog"><h2>本地演示提交核对</h2><pre id="confirmation-values"></pre>'
            '<p>这只会向本机夹具写入演示事件。</p><label><input type="checkbox" id="confirm-checkbox">我确认本地演示提交</label>'
            '<div class="actions"><button id="confirm-submit" type="button" disabled>确认本地演示提交</button>'
            '<button id="cancel-submit" type="button">返回核对</button></div></dialog>')
    script = r"""
const fields=['title','category','spec','price','stock'];
let data, current, states, uploadUrls=[];
const $=id=>document.getElementById(id);
async function post(path,body){const response=await fetch(path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body)});const value=await response.json();if(!response.ok)throw Error(value.error);return value;}
function values(){return Object.fromEntries(fields.map(field=>[field,$(field).value]));}
function state(){return states[current.id];}
function showStatus(){
 const checks=state().checks||{};
 for(const field of fields){const check=checks[field];$('state-'+field).textContent=check?`读回：${check.observed} · ${check.matched?'已核验一致':'不一致，需要修正'}`:($ (field).value?'已填写 · 待读回核验':'未填写 · 未核验');}
 const all=fields.every(field=>checks[field]&&checks[field].matched);
 $('review-submit').disabled=!all;
 $('overall-state').textContent=state().external_id?`${state().status} · ${state().external_id}`:(all?'awaiting_confirmation：五个字段已核验，尚未提交':'prepared：填写后逐字段读回核验，尚未提交');
}
function render(){
 current=data.products.find(product=>product.id===$('product-select').value);
 $('current-identity').textContent=`当前平台：${current.platform} ｜ 店铺：${current.shop_id} ｜ SKU：${current.sku}`;
 $('expected-data').textContent=JSON.stringify(current,null,2);
 for(const field of fields)$(field).value=state().values[field]??'';
 $('images').value='';$('image-previews').replaceChildren();for(const url of uploadUrls)URL.revokeObjectURL(url);uploadUrls=[];
 $('image-state').textContent=state().images.length?`已上传演示图片：${state().images.join('、')}`:'尚未上传图片';
 showStatus();
}
async function verify(selected=fields){
 const result=await post('/mock/verify',{id:current.id,values:values(),fields:selected});
 states[current.id]=result.state;showStatus();
}
for(const field of fields){
 $(field).addEventListener('input',()=>{state().values[field]=$(field).value;delete state().checks[field];state().external_id='';state().status='prepared';showStatus();});
 $(field).addEventListener('change',async()=>{try{await post('/mock/edit',{id:current.id,values:values(),field});}catch(error){$('overall-state').textContent=error.message;}});
 document.querySelector(`[data-verify-field="${field}"]`).onclick=()=>verify([field]).catch(error=>$('overall-state').textContent=error.message);
}
$('product-select').onchange=render;
$('verify-all').onclick=()=>verify().catch(error=>$('overall-state').textContent=error.message);
$('save-draft').onclick=async()=>{try{const result=await post('/mock/draft',{id:current.id,values:values()});states[current.id]=result.state;showStatus();}catch(error){$('overall-state').textContent=error.message;}};
$('images').onchange=async()=>{
 const files=Array.from($('images').files);$('image-previews').replaceChildren();
 for(const file of files){const image=document.createElement('img');image.alt='演示上传预览：'+file.name;image.src=URL.createObjectURL(file);uploadUrls.push(image.src);$('image-previews').append(image);}
 try{const result=await post('/mock/upload',{id:current.id,filenames:files.map(file=>file.name)});state().images=result.filenames;$('image-state').textContent=`上传成功（仅本地演示）：${result.filenames.join('、')}；${result.filenames.length}张`;}catch(error){$('image-state').textContent=error.message;}
};
$('review-submit').onclick=()=>{$('confirmation-values').textContent=JSON.stringify({platform:current.platform,shop_id:current.shop_id,sku:current.sku,...values()},null,2);$('confirm-checkbox').checked=false;$('confirm-submit').disabled=true;$('confirm-dialog').showModal();};
$('confirm-checkbox').onchange=()=>{$('confirm-submit').disabled=!$('confirm-checkbox').checked;};
$('cancel-submit').onclick=()=>$('confirm-dialog').close();
$('confirm-submit').onclick=async()=>{try{const result=await post('/mock/submit',{id:current.id,values:values(),confirmed:$('confirm-checkbox').checked});states[current.id]=result.state;$('confirm-dialog').close();showStatus();}catch(error){$('overall-state').textContent=error.message;}};
fetch('/mock/data').then(response=>response.json()).then(value=>{data=value;states=value.states;for(const product of data.products){const option=document.createElement('option');option.value=product.id;option.textContent=`${product.platform} / ${product.shop_id} / ${product.sku} / ${product.title}`;$('product-select').append(option);}render();}).catch(error=>$('overall-state').textContent=error.message);
"""
    return _page("批量商品填报验收", body, script)


def activities_page():
    rows = "".join(f'<tr data-activity-id="{activity["activity_id"]}"><td>{activity["activity_id"]}</td>'
                   f'<td>{activity["shop_id"]}</td><td>{activity["name"]}</td><td>{activity["status"]}</td>'
                   f'<td>{activity["start_date"]} 至 {activity["end_date"]}<br>截止：{activity["deadline"]}</td>'
                   f'<td><details><summary>查看报名规则</summary>{activity["threshold"]}；费用率{activity["fee_rate"]}</details></td></tr>'
                   for activity in ACTIVITIES)
    body = ('<p id="activity-source">数据来源：本地虚构活动列表；观察时间由浏览器当前读取记录。</p>'
            '<table aria-label="演示活动列表"><thead><tr><th>活动ID</th><th>店铺</th><th>活动名称</th><th>状态</th><th>日期</th><th>规则</th></tr></thead>'
            f'<tbody>{rows}</tbody></table><a class="download" id="download-activities" href="/mock/activities.csv" download>下载活动表 CSV（虚构）</a>'
            '<p id="activity-action-state" role="status">只读查询；未报名任何活动。</p>')
    return _page("活动查询验收", body)


def reports_page():
    columns = tuple(REPORTS[0])
    head = "".join(f"<th>{column}</th>" for column in columns)
    rows = "".join('<tr>' + ''.join(f'<td>{report[column]}</td>' for column in columns) + '</tr>' for report in REPORTS)
    return _page("经营报表下载验收", '<p id="report-source">数据来源：本地虚构经营报表；日期2026-11-15至2026-11-16。</p>'
                 f'<table aria-label="演示经营报表"><thead><tr>{head}</tr></thead><tbody>{rows}</tbody></table>'
                 '<a id="download-reports" class="download" href="/mock/reports.csv" download="demo-operating-report.csv">下载经营报表 CSV（虚构）</a>'
                 '<p>以下为独立虚构事件账本：2平台3店、2026-11-16，同号订单用于跨店隔离验收。</p>'
                 + ''.join(f'<a id="download-{kind}" class="download" href="/mock/{kind}.csv" download="demo-{kind}.csv">下载{kind}原始事件</a> ' for kind in LEDGER)
                 + '<p id="download-hint">下载后核对文件名、表头、行数、日期及店铺范围；点击按钮本身不证明文件已落盘。</p>')


def _matches(field, expected, observed):
    if field in ("price", "stock"):
        try:
            left, right = Decimal(str(expected)), Decimal(str(observed))
            return left.is_finite() and right.is_finite() and left == right
        except InvalidOperation:
            return False
    return str(expected).strip() == str(observed).strip()


def _csv(rows):
    output = io.StringIO(newline="")
    writer = csv.DictWriter(output, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return output.getvalue().encode("utf-8-sig")


class FixtureState:
    def __init__(self):
        self.lock = threading.RLock()
        self.events = []
        self.states = {product["id"]: {"values": {}, "checks": {}, "images": [],
                                        "status": "prepared", "external_id": ""} for product in PRODUCTS}

    def event(self, event, product=None, **details):
        self.events.append({"sequence": len(self.events) + 1, "event": event,
                            "timestamp": datetime.now(timezone.utc).isoformat(timespec="seconds"),
                            "id": product["id"] if product else "",
                            "scope": {field: product[field] for field in ("platform", "shop_id", "sku")} if product else {},
                            **details})

    def mutate(self, action, body):
        product = next((product for product in PRODUCTS if product["id"] == body.get("id")), None)
        if product is None:
            return 404, {"error": "unknown demo product"}
        state = self.states[product["id"]]
        values = body.get("values", {})
        if not isinstance(values, dict):
            return 400, {"error": "values must be an object"}
        if action in ("edit", "verify", "draft", "submit"):
            for field in FIELDS:
                value = values.get(field, "")
                if state["values"].get(field, "") != value:
                    state["checks"].pop(field, None)
                state["values"][field] = value
        checks = {field: {"observed": state["values"].get(field, ""),
                          "matched": _matches(field, product[field], state["values"].get(field, ""))}
                  for field in FIELDS}
        if action == "verify":
            requested = body.get("fields", FIELDS)
            if not isinstance(requested, (list, tuple)) or any(field not in FIELDS for field in requested):
                return 400, {"error": "unknown verification field"}
            for field in requested:
                state["checks"][field] = checks[field]
            all_verified = all(state["checks"].get(field, {}).get("matched") for field in FIELDS)
            state["status"] = "awaiting_confirmation" if all_verified else "prepared"
            self.event("verify", product, fields=list(requested), values=deepcopy(state["values"]), all_verified=all_verified)
            return 200, {"all_verified": all_verified, "checks": deepcopy(state["checks"]), "state": deepcopy(state)}
        if action == "upload":
            filenames = body.get("filenames", [])
            if not isinstance(filenames, list) or any(not isinstance(name, str) for name in filenames):
                return 400, {"error": "filenames must be strings"}
            state["images"] = filenames
            self.event("upload", product, filenames=filenames)
            return 200, {"filenames": filenames, "state": deepcopy(state)}
        if action == "submit":
            if body.get("confirmed") is not True or not all(check["matched"] for check in checks.values()):
                return 409, {"error": "explicit local confirmation and all current expected values are required"}
            state["external_id"] = "MOCK-PRODUCT-" + product["id"]
            state["status"] = "submitted_review"
        elif action == "draft":
            state["external_id"] = "MOCK-DRAFT-" + product["id"]
            state["status"] = "draft"
        elif action == "edit":
            state["status"] = "prepared"
            state["external_id"] = ""
        else:
            return 404, {"error": "unknown mock action"}
        self.event(action, product, values=deepcopy(state["values"]), external_id=state["external_id"])
        return 200, {"status": state["status"], "external_id": state["external_id"], "state": deepcopy(state)}


def create_server(port=0):
    """Create a server bound strictly to 127.0.0.1; caller owns its lifetime."""
    fixture = FixtureState()

    class Handler(BaseHTTPRequestHandler):
        def log_message(self, format, *args):
            pass

        def send(self, status, data, content_type="application/json; charset=utf-8", filename=None):
            if isinstance(data, (dict, list)):
                data = json.dumps(data, ensure_ascii=False).encode("utf-8")
            elif isinstance(data, str):
                data = data.encode("utf-8")
            self.send_response(status)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(data)))
            self.send_header("Cache-Control", "no-store")
            if filename:
                self.send_header("Content-Disposition", f'attachment; filename="{filename}"')
            self.end_headers()
            self.wfile.write(data)

        def do_GET(self):
            path = urlsplit(self.path).path
            if path in ("/", "/mock/listing"):
                return self.send(200, listing_page(), "text/html; charset=utf-8")
            if path == "/mock/activities":
                return self.send(200, activities_page(), "text/html; charset=utf-8")
            if path == "/mock/reports":
                return self.send(200, reports_page(), "text/html; charset=utf-8")
            with fixture.lock:
                if path == "/mock/data":
                    return self.send(200, {"demo": True, "products": PRODUCTS, "activities": ACTIVITIES,
                                           "reports": REPORTS, "ledger": LEDGER, "states": deepcopy(fixture.states)})
                if path == "/mock/events":
                    return self.send(200, {"demo": True, "events": deepcopy(fixture.events)})
                if path in ("/mock/activities.csv", "/mock/reports.csv"):
                    activity = path.endswith("activities.csv")
                    fixture.event("download_activities" if activity else "download_reports")
                    return self.send(200, _csv(ACTIVITIES if activity else REPORTS), "text/csv; charset=utf-8",
                                     "demo-activities.csv" if activity else "demo-operating-report.csv")
                if path in {f'/mock/{kind}.csv' for kind in LEDGER}:
                    kind = path.rsplit('/', 1)[-1].removesuffix('.csv')
                    fixture.event('download_' + kind)
                    return self.send(200, _csv(LEDGER[kind]), 'text/csv; charset=utf-8', 'demo-' + kind + '.csv')
                if path == "/healthz":
                    return self.send(200, {"ok": True, "demo": True})
            return self.send(404, {"error": "unknown fixture path"})

        def do_POST(self):
            path = urlsplit(self.path).path
            if path not in {f"/mock/{action}" for action in ("edit", "verify", "upload", "draft", "submit")}:
                return self.send(404, {"error": "unknown fixture action"})
            try:
                length = int(self.headers.get("Content-Length", "0"))
                if length > 1024 * 1024:
                    return self.send(413, {"error": "fixture request too large"})
                body = json.loads(self.rfile.read(length).decode("utf-8"))
                if not isinstance(body, dict):
                    raise ValueError("object required")
            except (ValueError, UnicodeDecodeError):
                return self.send(400, {"error": "valid JSON object required"})
            with fixture.lock:
                status, response = fixture.mutate(path.rsplit("/", 1)[-1], body)
            return self.send(status, response)

    server = ThreadingHTTPServer(("127.0.0.1", int(port)), Handler)
    server.daemon_threads = True
    server.fixture = fixture
    return server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=0, help="0 allocates an ephemeral loopback port")
    parser.add_argument("--ready-file", type=Path, help="optional local JSON file containing the actual URL")
    args = parser.parse_args()
    server = create_server(args.port)
    base = f"http://127.0.0.1:{server.server_address[1]}"
    ready = {"demo": True, "host": "127.0.0.1", "port": server.server_address[1],
             "url": base + "/mock/listing", "activities_url": base + "/mock/activities",
             "reports_url": base + "/mock/reports", "events_url": base + "/mock/events"}
    if args.ready_file:
        args.ready_file.parent.mkdir(parents=True, exist_ok=True)
        args.ready_file.write_text(json.dumps(ready, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(ready, ensure_ascii=False), flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()
