"""Run the actual audience package and locate operations in its source recording."""
import os
import subprocess
import sys

from claim_release import digest
from series_recipe import read


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


def run_and_record(skill, recipe, dest, release, browser):
    from operation_capture import run_capture
    return run_capture(skill,recipe,dest,release,browser)
