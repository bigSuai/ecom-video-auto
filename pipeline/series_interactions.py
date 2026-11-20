"""Film operations performed against the demo backend or assets shipped by the viewer skill."""
import html
import json
import subprocess
import sys

from claim_release import digest
from series_recipe import read


def record_listing(page, skill, sample, mark):
    products = read(sample)["products"]
    server = subprocess.Popen([sys.executable, "-B", str(skill/"scripts/demo_backend.py"), "--port", "0"],
                              stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True, encoding="utf-8")
    observed = []
    try:
        url = json.loads(server.stdout.readline())["url"]
        page.goto(url)
        page.locator("#product-select option").first.wait_for(state="attached")
        page.add_style_tag(content="""main{max-width:100%;padding:12px 25px}h1,details,nav,main > p:last-of-type,
            #images,label[for=images],#image-state,#save-draft,footer{display:none}
            .demo{padding:5px 9px;font-size:16px;margin:4px 0}
            label[for=product-select]{display:none}
            #product-select{font-size:20px;width:100%}#current-identity{font-size:18px;margin:10px 0}
            .field{display:grid;grid-template-columns:130px 290px 1fr;gap:14px;align-items:center;
            margin:7px 0;padding:5px 10px;border:1px solid #d7e1de;border-radius:8px;background:#f5f8f6}
            .field label,.field .readback{grid-column:auto;margin:0;font-size:20px}
            .field button{display:none}.field input{font-size:22px;padding:5px 10px}
            .field:focus-within{background:#dcefe7;border-color:#167052}
            .actions{margin:12px 0}form{margin:0}#overall-state{font-size:21px;font-weight:750;margin:8px 0}""")
        mark(page, "#20eaea")
        for index, product in enumerate(products):
            identity = " / ".join(str(product[k]) for k in ("platform","shop_id","sku","title"))
            page.select_option("#product-select", label=identity)
            for field in ("title","category","spec","price","stock"):
                widget = page.locator("#"+field)
                widget.fill(str(product[field]))
                page.wait_for_timeout(180)
            page.locator("#verify-all").click()
            page.wait_for_function("document.querySelector('#overall-state').textContent.includes('awaiting_confirmation')")
            row = {"shop_id":product["shop_id"],"sku":product["sku"]}
            for field in ("title","category","spec","price","stock"):
                value = page.locator("#"+field).input_value()
                status = page.locator("#state-"+field).inner_text()
                if value != str(product[field]) or "已核验一致" not in status:
                    raise ValueError("网页字段读回失败："+field)
                row[field] = value
            observed.append(row)
            if index + 1 == len(products):
                mark(page, "#e820e8")
                page.wait_for_timeout(1800)
            else:
                page.wait_for_timeout(1000)
    finally:
        server.terminate()
        server.wait(timeout=10)
    return {"action":"本地演示表单填报与读回", "products":observed, "status":"awaiting_confirmation"}


def record_media(page, skill, folder, dest, mark):
    manifest = folder/"manifest.json"
    item = next(i for i in read(manifest)["items"] if i["type"]=="main_image")
    output = dest/"selected"
    cli = [sys.executable, "-B", str(skill/"scripts/ecommerce.py")]
    def select_export():
        for args in (["media-select","--item",item["id"],"--action","keep"],
                     ["media-export","--destination",str(output)]):
            subprocess.run([*cli,*args,"--manifest",str(manifest)],capture_output=True,check=True,timeout=60)
        sources = read(output/"sources.json")
        files = [p for p in output.rglob("*") if p.is_file() and p.name != "sources.json"]
        if sources["exported_count"] != 1 or len(files) != 1 or digest(files[0]) != item["sha256"]:
            raise ValueError("选定的素材与导出文件不一致")
        return "已导出 1 份选中主图 · "+files[0].name
    page.expose_function("selectAndExport",select_export)
    page.goto((folder/"report.html").as_uri())
    image_uri = html.escape((folder/item["path"]).as_uri(), quote=True)
    page.set_content("""<meta charset="utf-8"><style>
        *{box-sizing:border-box}body{margin:0;padding:26px;display:grid;grid-template-columns:43% 1fr;gap:32px;
        background:#f8f6e9;color:#153c30;font:24px 'Microsoft YaHei',sans-serif;align-items:center;height:100vh}
        img{width:100%;max-height:90vh;object-fit:contain}button{background:#17563f;border:0;border-radius:8px;
        padding:10px 20px;color:white;font:inherit}#exported{font-size:22px;overflow-wrap:anywhere}</style>
        <img src="IMAGE_URI"><section><h2>本次生成的商品主图</h2>
        <p>模板初稿 · 等待挑选</p><button>保留并导出主图</button><p id="exported"></p></section>
        <script>document.querySelector('button').onclick=async e=>{e.target.disabled=true;
        document.querySelector('#exported').textContent=await selectAndExport()}</script>""".replace('IMAGE_URI',image_uri))
    page.wait_for_function("document.querySelector('img').naturalWidth>0")
    mark(page, "#20eaea")
    page.wait_for_timeout(850)
    page.get_by_role("button").click()
    page.wait_for_function("document.querySelector('#exported').textContent.length>0")
    mark(page, "#e820e8")
    page.wait_for_timeout(3600)
    return {"action":"选择并导出本次主图","item":item["id"],"sha256":item["sha256"],
            "export":"selected/sources.json"}

