"""Record two continuous actions from a real run and locate their bounds in the encoded WebM."""
import html
import datetime
import subprocess
from pathlib import Path
from series_recipe import read, write
from claim_release import digest

# Durations fit the approved narration. The cut spans the operation, including the result.
DURATIONS = {"B":(4.24,5.65), "A":(5.40,6.45), "C":(5.05,6.77), "D":(5.80,7.38),
             "E":(6.92,7.50), "F":(5.10,6.17), "G":(5.83,6.52)}
QUERIES = {"A":("queue","DEMO-CUP-01"), "B":("issues","conflicting_price"),
           "C":("ad_totals","7d_click"), "D":("overview","CNY"), "E":("media_items","main_image"),
           "F":("after_sales","C1"), "G":("comparisons","000087")}

POINTER = r"""(()=>{if(window.__hasPointer)return;window.__hasPointer=true;
const mount=()=>{const p=document.createElement('div');p.style.cssText='pointer-events:none;position:fixed;left:0;top:0;z-index:99999;width:22px;height:27px;background:#ffac43;clip-path:polygon(0 0,95% 56%,55% 64%,41% 100%);filter:drop-shadow(0 0 3px black);display:none';document.documentElement.append(p);
document.addEventListener('mousemove',e=>Object.assign(p.style,{display:'block',left:e.clientX+'px',top:e.clientY+'px'}));document.addEventListener('mousedown',e=>{const r=document.createElement('i');r.style.cssText='position:fixed;pointer-events:none;z-index:99998;width:20px;height:20px;border-radius:100%;border:4px solid #f89734;left:'+(e.clientX-10)+'px;top:'+(e.clientY-10)+'px';document.documentElement.append(r);r.animate([{transform:'scale(.5)'},{transform:'scale(3)',opacity:0}],420).onfinish=()=>r.remove()});};
if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',mount);else mount()})();"""

def point(page, loc):
    loc.scroll_into_view_if_needed()
    rect = loc.bounding_box()
    x, y = rect["x"] + rect["width"]*.45, rect["y"] + rect["height"]*.52
    page.mouse.move(x,y,steps=14)
    page.wait_for_timeout(110)
    loc.click()

def launcher(page, recipe, sample, invoke):
    # The file selected on camera must be the exact file given to the CLI.
    def dispatch(payload):
        if payload != digest(sample):
            raise ValueError("浏览器输入文件与实际任务不符")
        return invoke()
    page.expose_function("runSelection", dispatch)
    page.goto(sample.parent.as_uri()+"/")
    page.set_content("""<meta charset=utf-8><style>*{box-sizing:border-box}body{margin:0;background:#12282d;color:#f8eed6;font:23px 'Microsoft YaHei',sans-serif}
    header{background:#0f1e21;padding:13px 23px;color:#ffcf78;font-weight:800}main{padding:14px 24px}label,button{background:#ccecb2;color:#18392f;padding:9px 16px;border:0;border-radius:6px;font:inherit;display:inline-block;cursor:pointer}
    input{position:absolute;opacity:0;width:1px}p{margin:10px 0;font-size:19px}pre{color:#cce3d4;font:21px 'Microsoft YaHei',sans-serif;white-space:pre-wrap;margin:12px 0;padding:12px;background:#213c41;border-left:4px solid #efc784;min-height:50px}
    button:disabled{opacity:.4}</style><header>电商助手　/　导入任务</header><main><h2 style="margin:0 0 13px">TITLE</h2>
    <label for="file">选择本地资料</label> <input id=file type=file accept=".json"><b id=name></b><pre id=rows>等待选择输入文件</pre>
    <button id=run disabled>执行技能 →</button> <span id=status></span></main><script>
    let hash;const $=id=>document.getElementById(id);$('file').onchange=async()=>{
    const f=$('file').files[0], data=JSON.parse(await f.text());const arr=Object.values(data).find(Array.isArray)||[];
    $('name').textContent=f.name+'　/　虚构样例';$('rows').textContent=arr.slice(0,3).map((r,i)=>String(i+1).padStart(2,'0')+'　'+Object.values(r).filter(x=>typeof x==='number'||typeof x==='string').slice(0,6).join('　')).join('\\n');
    hash=Array.from(new Uint8Array(await crypto.subtle.digest('SHA-256',await f.arrayBuffer())),n=>n.toString(16).padStart(2,'0')).join('');$('run').disabled=false;};
    $('run').onclick=async()=>{$('run').disabled=true;$('status').textContent='执行中…';$('status').textContent=await runSelection(hash);};</script>""".replace("TITLE",html.escape(recipe["title"])))
    page.evaluate(POINTER)

def select_record(page, table, query):
    selector=page.locator("#tables");selector.select_option(table)
    field=page.locator("#query");point(page,field)
    field.press_sequentially(query,delay=75)
    row=page.locator("button.record").first
    idx=int(row.get_attribute("data-index"))
    point(page,row)
    page.locator("aside:not([hidden])").wait_for()
    return idx

def run_capture(skill, recipe, dest, release, browser):
    from series_evidence import execute, mark_view
    from series_interactions import record_listing, record_media
    dest.mkdir(parents=True,exist_ok=False)
    module=recipe["module"];sample=skill/"assets/demo"/(module+".json")
    if read(sample).get("data_kind")!="synthetic":raise ValueError("演示录制需要虚构输入")
    size=dict(width=940,height=530)
    ctx=browser.new_context(viewport=size,record_video_size=size,record_video_dir=str(dest),locale="zh-CN")
    ctx.add_init_script(POINTER)
    result_bundle=[]
    def invoke():
        if result_bundle: raise ValueError("重复执行输入")
        result_bundle.append(execute(skill,recipe,dest,sample))
        return "完成 · 打开本次报告"
    try:
        page=ctx.new_page();video=page.video
        launcher(page,recipe,sample,invoke)
        if module != "A":mark_view(page,"#f02020")
        page.wait_for_timeout(280)
        with page.expect_file_chooser() as chooser:point(page,page.locator("label"))
        chooser.value.set_files(str(sample));page.wait_for_function("!document.querySelector('#run').disabled")
        page.wait_for_timeout(340);point(page,page.locator("#run"))
        page.wait_for_function("document.querySelector('#status').textContent.includes('完成')",timeout=305000)
        run,result,report,_=result_bundle[0]
        page.wait_for_timeout(220);page.goto(report.as_uri());page.wait_for_timeout(100)
        first=recipe["views"][0];page.locator("#tables").select_option(first["table"])
        key=next(iter(first["where"].values()),"")
        if key:page.locator("#query").press_sequentially(str(key),delay=65)
        point(page,page.locator(".record").first);page.wait_for_timeout(850)
        if module != "A":mark_view(page,"#20ea20")
        page.wait_for_timeout(400)
        if module=="A":
            def start_listing(p,color):
                if color=="#20eaea":mark_view(p,"#f02020");p.wait_for_timeout(250)
            def next_product(p):
                p.wait_for_timeout(550);mark_view(p,"#20ea20");p.wait_for_timeout(350)
                mark_view(p,"#2020ee")
            action=record_listing(page,skill,sample,start_listing,next_product)
        elif module=="E":
            def start_media(p,color):
                if color=="#20eaea":mark_view(p,"#2020ee");p.wait_for_timeout(250)
            action=record_media(page,skill,report.parent,dest,start_media)
        else:
            # Start on the preceding view, then filter/open/export through the actual shipped report.
            page.locator("#query").fill("");page.evaluate("document.querySelector('aside').hidden=true")
            mark_view(page,"#2020ee");page.wait_for_timeout(260)
            table,query=QUERIES[module];idx=select_record(page,table,query)
            page.wait_for_timeout(680)
            with page.expect_download() as download:point(page,page.locator("#exportrow"))
            selected=dest/"selected-row.json";download.value.save_as(str(selected))
            value=read(selected)
            if value!={"run_id":run["run_id"],"table":table,"index":idx,"row":result["tables"][table][idx]}:
                raise ValueError("实际导出记录与领取包计算结果不符")
            page.wait_for_timeout(780)
            action={"action":"检索、展开并导出真实记录","table":table,"query":query,"index":idx,"file":selected.name,"sha256":digest(selected)}
        mark_view(page,"#20eaea");page.wait_for_timeout(450)
        write(dest/"interaction.json",action)
    finally:ctx.close()
    raw=dest/"execution.webm";Path(video.path()).replace(raw)
    clip=dest/"recording.mp4"
    highlights,steps,starts=cut_sequences(raw,clip,module)
    pack={"step":"s"+str(recipe["step"]),"product":recipe["title"],"recorder":"continuous-workflow","clip":clip.name,
          "recorded_at":datetime.datetime.now(datetime.timezone.utc).isoformat(),
          "review":"ok","masked":False,"measured":{"items":run["summary"]["processed_rows"],"seconds":run["processing_seconds"]},
          "steps":steps,"highlights":highlights,"evidence":{"module":module,"run_id":run["run_id"],"source_starts":starts,
          "data_kind":"synthetic","release_sha256":release["sha256"],"skill_version":release["version"],"input_sha256":digest(sample),
          "report":report.relative_to(dest).as_posix(),"report_sha256":digest(report),"result_sha256":digest(report.with_name("result.json")),
          "clip_sha256":digest(clip),"raw_sha256":digest(raw),"interaction_sha256":digest(dest/"interaction.json"),
          "capture_scope":"上架连续填写及读回，其他题从导入执行到打开结果，中段复核或选稿导出。两个剪辑各取一段连续原片。"}}
    write(dest/"pack.json",pack);return pack

def cut_sequences(raw,clip,module):
    from series_evidence import recorded_starts
    starts=recorded_starts(raw,[.18,.18,.18,.18])
    durations=DURATIONS[module]
    cursor=0;steps=[];slots={};filters=[]
    for i,(slot,duration) in enumerate(zip(("hook","mid"),durations)):
        start,end=starts[2*i:2*i+2];length=end-start
        if length<1.5:raise ValueError("操作时段过短")
        frames=round(duration*30);duration=frames/30
        filters.append(f"[0:v]trim=start={start:.3f}:end={end:.3f},setpts=(PTS-STARTPTS)*{duration/length:.7f},fps=30,tpad=stop_mode=clone:stop_duration=0.10,trim=end_frame={frames}[v{i}]")
        phases=("填写本件商品","逐项读回") if module=="A" else ("选择输入并执行","打开实际结果")
        for part,name in enumerate(phases if i==0 else ("操作并核对","读取或导出结果")):
            steps.append({"name":name,"slot":slot,"start":round(cursor+part*duration/2,3),"end":round(cursor+(part+1)*duration/2,3),
                          "source_start":round(start+part*length/2,3),"source_duration":round(length/2,3)})
        slots[slot]={"start":round(cursor,3),"dur":round(duration,3),"speed":1};cursor+=duration
    filters.append("[v0][v1]concat=n=2:v=1:a=0[out]")
    subprocess.run(["ffmpeg","-nostdin","-v","error","-i",str(raw),"-filter_complex",";".join(filters),"-map","[out]","-an",
                    "-c:v","libx264","-preset","veryfast","-pix_fmt","yuv420p","-n",str(clip)],check=True)
    return slots,steps,starts

