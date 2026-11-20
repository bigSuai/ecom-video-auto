"""Record selected cells of the HTML report actually emitted by the released skill."""
import datetime
import html
import os
import subprocess
import sys
from pathlib import Path

from claim_release import digest
from series_recipe import read, write


def matches(row, wanted):
    return all(key in row and row[key] == value for key, value in wanted.items())


def check_result(recipe, result):
    if result.get("module") != recipe["module"] or result.get("data_kind") != "synthetic":
        raise ValueError("实际输出与本集模块或演示数据性质不符")
    for assertion in recipe["expect"]:
        if not any(matches(row, assertion["row"]) for row in result["tables"][assertion["table"]]):
            raise ValueError("本次输出无法支持本集文案：" + str(assertion))
    for view in recipe["views"]:
        rows = [r for r in result["tables"][view["table"]] if matches(r, view["where"])]
        if not rows or not all(set(view["columns"]).issubset(row) for row in rows):
            raise ValueError("报告中缺少本集要展示的行列：" + view["table"])


# Select existing cells and translate their headers. The recorded values come from the HTML report.
PROJECT = """arg => {
 const sections=[...document.querySelectorAll('section')];
 const s=sections.find(el=>el.querySelector('h2')?.textContent.split('（')[0]===arg.table);
 if(!s) throw Error('missing actual report section '+arg.table);
 for(const e of document.body.children)e.style.display=e===s?'block':'none';
 const rows=[...s.querySelectorAll('tr')],keys=[...rows[0].cells].map(c=>c.textContent);
 const out=Object.keys(arg.columns); let visible=0;
 rows.forEach((tr,i)=>{const cells=[...tr.cells];const keep=!i||Object.entries(arg.where).every(([k,v])=>cells[keys.indexOf(k)]?.textContent===String(v));
 tr.style.display=keep?'':'none';if(i&&keep)visible++;
 cells.forEach((cell,j)=>{const k=keys[j];cell.style.display=out.includes(k)?'':'none';if(!i&&out.includes(k))cell.textContent=arg.columns[k];});});
 if(!visible)throw Error('report filter selected no rows');window.scrollTo(0,0);
}"""
STYLE = """*{box-sizing:border-box}body{margin:0;padding:25px 32px;background:#fbf7ec;color:#172e28;font:24px "Microsoft YaHei",sans-serif}section{margin:0;overflow:visible}h2{font-size:33px;color:#153c30;margin:0 0 15px}table{width:100%;border-collapse:collapse;background:#fff}td,th{padding:12px;border:1px solid #cbd8c9;font-size:25px;overflow-wrap:anywhere}th{background:#e0eada;font-size:23px}"""


def execute(skill, recipe, dest, sample):
    cmd = [sys.executable, "-B", str(skill / "scripts/ecommerce.py"), "run", "--module", recipe["module"],
           "--input", str(sample), "--output", str(dest / "runs")]
    env = {**os.environ, "PYTHONUTF8": "1", "PYTHONIOENCODING": "utf-8"}
    log = subprocess.run(cmd, capture_output=True, encoding="utf-8", env=env, timeout=300)
    (dest / "execution.jsonl").write_text(log.stdout, encoding="utf-8")
    if log.returncode:
        raise RuntimeError("领取包本次执行失败：" + (log.stderr or log.stdout)[-600:])
    runs = list((dest / "runs").glob("*/run.json"))
    if len(runs) != 1:
        raise RuntimeError("当次执行应产生一个运行记录")
    run = read(runs[0])
    folder = runs[0].parent
    result = read(folder / "result.json")
    report = folder / "report.html"
    if run["status"] != "completed" or run["run_id"] != result["run_id"] or run["input_sha256"] != digest(sample):
        raise ValueError("运行状态或输入校验失败")
    check_result(recipe, result)
    product_image = None
    if recipe["module"] == "E":
        item = next(r for r in result["tables"]["media_items"] if r["type"] == "main_image")
        product_image = (folder / item["path"]).resolve()
        if not product_image.is_relative_to(folder) or digest(product_image) != item["sha256"]:
            raise ValueError("素材产物与运行记录不匹配")
    return run, result, report, product_image


def mark_view(page, color):
    # A small recording indicator anchors trims to encoded frames, including on busy machines.
    page.evaluate("""color => {
        document.querySelector('#capture-cue')?.remove();
        const dot = document.createElement('div');
        dot.id='capture-cue';
        dot.style.cssText='position:fixed;right:4px;top:4px;width:14px;height:14px;z-index:2147483647;border-radius:3px;background:'+color;
        document.documentElement.appendChild(dot);
    }""", color)


def recorded_starts(raw, lengths):
    cmd = ["ffmpeg", "-nostdin", "-v", "error", "-i", str(raw), "-vf",
           "fps=25,crop=4:4:928:8,scale=1:1,format=rgb24", "-f", "rawvideo", "pipe:1"]
    pixels = subprocess.run(cmd, check=True, capture_output=True).stdout
    found = [[] for _ in lengths]
    for i in range(0, len(pixels), 3):
        rgb = pixels[i:i+3]
        channel = max(range(3), key=rgb.__getitem__)
        if len(found) >= 4 and rgb[0] < 90 and min(rgb[1:]) > 160:
            found[3].append(i // 3 / 25)
        elif len(found) >= 5 and rgb[1] < 90 and min(rgb[0], rgb[2]) > 160:
            found[4].append(i // 3 / 25)
        elif rgb[channel] > 170 and all(rgb[j] < 90 for j in range(3) if j != channel):
            found[channel].append(i // 3 / 25)
    starts = []
    for times, duration in zip(found, lengths):
        if not times or times[-1]-times[0] + .04 < duration:
            raise ValueError("原始录像缺少持续可读的启动画面或报告视图")
        starts.append(times[0] + .04)
    return starts


def edit_capture(raw, clip, action):
    """Cut two separate windows from the same continuous, real run."""
    minimums = [1.7, 2.6, 2.8, .7, 1.6] if action else [1.7, 2.6, 2.8]
    starts = recorded_starts(raw, minimums)
    if action:
        # Preserve an uninterrupted section of the real browser interaction for the middle.
        hook_parts = [(3, 1.28, "开始实际操作"), (4, 1.6, "实际核验或导出结果")]
        mid_parts = [(3, 3.52, action["action"]), (4, 1.44, "本次操作结果")]
    else:
        hook_parts = [(0, 1.68, "运行领取包"), (2, 1.56, "直接看问题或结果")]
        mid_parts = [(1, 2.52, "读取本次处理结果"), (2, 2.8, "核对输出证据")]
    filters, steps, highlights = [], [], {}
    cursor = 0
    for slot, parts in (("hook", hook_parts), ("mid", mid_parts)):
        begin = cursor
        for index, duration, label in parts:
            source = starts[index]
            filters.append(f"[0:v]fps=25,trim=start={source:.3f}:duration={duration},setpts=PTS-STARTPTS,fps=30[v{len(filters)}]")
            steps.append({"name": label, "slot": slot, "start": round(cursor, 3), "end": round(cursor + duration, 3),
                          "source_start": round(source, 3), "source_duration": duration})
            cursor += duration
        highlights[slot] = {"start": round(begin, 3), "dur": round(cursor-begin, 3), "speed": 1}
    inputs = "".join(f"[v{i}]" for i in range(len(filters)))
    filters.append(f"{inputs}concat=n={len(filters)}:v=1:a=0[out]")
    subprocess.run(["ffmpeg", "-nostdin", "-v", "error", "-i", str(raw), "-filter_complex", ";".join(filters),
                    "-map", "[out]", "-an", "-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p",
                    "-movflags", "+faststart", "-n", str(clip)], check=True)
    from footage import probe_seconds
    if probe_seconds(clip) + .05 < cursor:
        raise ValueError("录像实际时长不足")
    return highlights, steps, starts


def run_and_record(skill, recipe, dest, release, browser):
    dest.mkdir(parents=True, exist_ok=False)
    module = recipe["module"]
    sample = skill / "assets" / "demo" / (module + ".json")
    if read(sample).get("data_kind") != "synthetic":
        raise ValueError("批量实录使用领取包中的虚构演示输入")
    size = {"width": 940, "height": 530}
    ctx = browser.new_context(viewport=size, record_video_size=size, record_video_dir=str(dest), locale="zh-CN")
    observed = []
    def invoke():
        if observed:
            raise ValueError("本次录像已执行")
        result = execute(skill, recipe, dest, sample)
        observed.append(result)
        run = result[0]
        return f'运行完成 · {run["summary"]["processed_rows"]} 行 · 模块用时 {run["processing_seconds"]:.3f} 秒'
    try:
        page = ctx.new_page()
        video = page.video
        page.expose_function("runViewerSkill", invoke)
        page.set_content('<meta charset=utf-8><style>body{background:#f7f4e8;color:#173c32;margin:46px;font:28px Microsoft YaHei,sans-serif}h1{font-size:45px}button{font:inherit;background:#17563f;color:white;border:0;border-radius:8px;padding:12px 22px}code{font-size:20px}</style>'
            + '<small>领取包实录 · 虚构演示输入</small><h1>' + html.escape(recipe["title"]) + '</h1>'
            + '<code>ecommerce.py run --module ' + html.escape(module) + '</code><p><button>运行领取包</button></p><strong id="status"></strong>'
            + '<script>document.querySelector("button").onclick=async(e)=>{e.target.disabled=true;e.target.textContent="正在运行…";document.querySelector("#status").textContent=await runViewerSkill();e.target.textContent="运行完成 ✓";}</script>')
        mark_view(page, "#f02020")
        page.wait_for_timeout(800)
        page.get_by_role("button").click()
        page.wait_for_function("document.querySelector('#status').textContent.length > 0",timeout=305000)
        if len(observed)!=1: raise RuntimeError("录像没有记录到领取包运行")
        run,result,report,product_image = observed[0]
        folder=report.parent
        page.wait_for_timeout(1700)
        for index,view in enumerate(recipe["views"]):
            page.goto(report.as_uri())
            page.add_style_tag(content=STYLE)
            page.evaluate(PROJECT,view)
            if product_image and index==0:
                page.goto(product_image.as_uri())
            mark_view(page, ("#20ea20", "#2020ee")[index])
            page.wait_for_timeout(550)
            page.evaluate("window.scrollTo({top: document.documentElement.scrollHeight,behavior:'smooth'})")
            page.wait_for_timeout(3600)
        action = None
        if recipe.get("interaction") == "listing":
            from series_interactions import record_listing
            action = record_listing(page, skill, sample, mark_view)
        elif recipe.get("interaction") == "media":
            from series_interactions import record_media
            action = record_media(page, skill, folder, dest, mark_view)
        if action:
            write(dest/"interaction.json", action)
    finally:
        ctx.close()
    raw=dest/"execution.webm"
    Path(video.path()).replace(raw)
    clip = dest / "recording.mp4"
    highlights, steps, starts = edit_capture(raw, clip, action)
    pack = {"step": "s" + str(recipe["step"]), "product": recipe["title"], "recorder": "released-skill-report",
            "clip": clip.name, "recorded_at": datetime.datetime.now(datetime.timezone.utc).isoformat(), "review": "ok", "masked": False,
            "measured": {"items": run["summary"]["processed_rows"], "seconds": run["processing_seconds"]},
            "steps": steps,
            "highlights": highlights,
            "evidence": {"module": module, "raw_sha256": digest(raw), "source_starts": starts, "run_id": run["run_id"], "data_kind": "synthetic", "release_sha256": release["sha256"],
                         "skill_version": release["version"], "input_sha256": digest(sample), "report": report.relative_to(dest).as_posix(),
                         "report_sha256": digest(report), "result_sha256": digest(folder / "result.json"), "clip_sha256": digest(clip),
                         "capture_scope": "本次输出报告或本次生成的素材，测量秒数为模块处理用时"}}
    if action:
        pack["evidence"]["interaction_sha256"] = digest(dest/"interaction.json")
    write(dest / "pack.json", pack)
    return pack

