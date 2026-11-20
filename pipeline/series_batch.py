"""Batch selection, real skill recordings, custom animation and deterministic audience releases."""
import argparse
from contextlib import contextmanager
import hashlib
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import sys
import tempfile
import uuid
import zipfile

from claim_release import build_release, digest
from series_recipe import ROOT, SERIES, prepare, read, write
from operation_capture import run_capture as run_and_record


@contextmanager
def exclusive(output):
    # Kernel-held lock is released if the process exits during a render.
    with (output / ".series.lock").open("a+b") as lock:
        if lock.tell() == 0:
            lock.write(b"0"); lock.flush()
        lock.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(lock.fileno(), msvcrt.LK_NBLCK, 1)
        else:
            import fcntl
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        yield


def load_catalog():
    rows = read(SERIES / "catalog.json")
    ids = [r["id"] for r in rows]
    if len(set(ids)) != len(ids) or any(not re.fullmatch(r"[a-z0-9-]+", k) for k in ids):
        raise ValueError("选题编号须唯一且可用作目录名")
    for r in rows:
        if not r.get("expect") or len(r["views"]) != 2:
            raise ValueError("每个选题均需可复核的结果及实录视图")
    return rows


def key_for(r, release, voice_cache=None):
    h = hashlib.sha256(json.dumps([r,release["sha256"]],sort_keys=True,ensure_ascii=False).encode())
    paths = [Path(__file__), ROOT/"pipeline/series_evidence.py", ROOT/"pipeline/series_recipe.py",
             ROOT/"pipeline/operation_capture.py", ROOT/"pipeline/proof_camera.py",
             SERIES/"story.js", SERIES/"cinema.js", SERIES/"stories"/(r["id"]+".js")]
    if r.get("template"): paths.extend(sorted((SERIES / r["template"]).glob("*")))
    if r["id"] == "listing-queue": paths.append(SERIES/"hook.js")
    if r["id"] == "media-drafts": paths.append(SERIES/"ceramic/cup-turntable.webp")
    paths.extend(sorted((ROOT / "engine").glob("*.js")))
    paths.extend(ROOT / "pipeline" / filename for filename in (
        "compile_script.py", "make.py", "render.js", "compose.py", "mix.py", "audio.py", "motion_check.py", "footage.py"))
    if r.get("interaction"): paths.append(ROOT / "pipeline/series_interactions.py")
    if r.get("image"): paths.append(ROOT / "assets/images" / r["image"])
    elif r["id"]=="ceramic-price": paths.append(ROOT/"assets/images/s2-sheet-errors.jpg")
    paths += [ROOT / "engine/index.html", ROOT / "assets/voice/ref.wav", ROOT / "assets/voice/ref.txt",
              ROOT / "assets/soundfont/GeneralUser-GS.sf2"]
    paths.extend(sorted((ROOT / "assets/mascot").glob("*.png")))
    cache = (voice_cache or SERIES/"voices") / r["id"] / "voice"
    if cache.is_dir(): paths.extend(sorted(cache.iterdir()))
    for p in paths:
        if p.is_file(): h.update(digest(p).encode())
    return h.hexdigest()


def verified_evidence(folder, release):
    p = read(folder/"pack.json")
    e = p["evidence"]
    report = folder/e["report"]
    record = read(report.with_name("run.json"))
    if e.get("interaction_sha256"):
        if digest(folder/"interaction.json") != e["interaction_sha256"]:
            raise ValueError("浏览器操作记录与本次实录不匹配")
        action = read(folder/"interaction.json")
        if "file" in action and digest(folder/action["file"]) != action["sha256"]:
            raise ValueError("本次导出的复核记录已改变")
        if "export" in action:
            files = [f for f in (folder/action["export"]).parent.rglob("*") if f.is_file() and f.name != "sources.json"]
            if len(files)!=1 or digest(files[0]) != action["sha256"]:
                raise ValueError("实录中的选稿导出物已改变")
    sample = "ecommerce-automation/assets/demo/"+e["module"]+".json"
    with zipfile.ZipFile(release["archive"]) as z:
        sample_sha = hashlib.sha256(z.read(sample)).hexdigest()
    if (p["review"] != "ok" or record["status"] != "completed" or e["run_id"] != record["run_id"]
            or p["measured"] != {"items":record["summary"]["processed_rows"], "seconds":record["processing_seconds"]}
            or sample_sha != e["input_sha256"] or sample_sha != record["input_sha256"]
            or release["sha256"] != e["release_sha256"] or digest(folder/p["clip"]) != e["clip_sha256"]
            or digest(folder/"execution.webm") != e["raw_sha256"]
            or digest(report) != e["report_sha256"] or digest(report.with_name("result.json")) != e["result_sha256"]):
        raise ValueError("实录来源或文件已改变："+str(folder))
    return p


def can_reuse(item, key, release, mode, output):
    if not item or item.get("key") != key: return False
    try:
        pack=verified_evidence(output/item["evidence"], release)
        if mode == "capture": return True
        if pack.get("recorder")=="continuous-workflow" and item.get("status")=="ready":
            scenes=read((output/item["video"]).parent/"script.json")["scenes"]
            if any(not s.get("pointer_focus") for s in scenes if s.get("slot") in ("hook","mid")): return False
        return item.get("status")=="ready" and all(digest(output/p)==sha for p,sha in item["files"].items()) and bool(item["files"])
    except (OSError,KeyError,ValueError):
        return False


def stage_voice(args, recipe, script, movie):
    import tts
    cached = (args.voice_cache or SERIES/"voices") / recipe["id"] / "voice"
    if cached.is_dir():
        try:
            tts.reuse_voice(script,cached.parent)
        except tts.TTSFailed:
            if args.voice_cache: raise
        else:
            shutil.copytree(cached,movie/"voice")
            return
    voice_python = args.voice_python or os.environ.get("ECOM_VOICE_PYTHON") or sys.executable
    env = os.environ.copy()
    if Path(voice_python).resolve() != Path(sys.executable).resolve():
        env.pop("PYTHONPATH", None)
    subprocess.run([str(voice_python),str(ROOT/"pipeline/tts.py"),str(movie/"script.json")],check=True,env=env)


def relative(out,p): return Path(p).relative_to(out).as_posix()

def footage_edits(pack):
    highlights = pack["highlights"]
    if set(highlights) != {"hook", "mid"}:
        raise ValueError("正式批量成片需有开头和中段两个实录槽")
    hook, mid = highlights["hook"], highlights["mid"]
    if hook["dur"] < 2.5 or mid["dur"] < 4 or hook["start"]+hook["dur"] > mid["start"]+.001:
        raise ValueError("两个实录槽的时长或剪辑范围不符")
    if any(not any(s.get("slot")==slot for s in pack["steps"]) for slot in highlights):
        raise ValueError("实录槽缺少原片定位")
    return highlights


def hook_summary(recipe, pack, folder):
    if recipe.get("interaction") == "listing":
        action = read(folder/"interaction.json")
        return f'本次共 {len(action["products"])} 件  ·  逐字段读回'
    if recipe.get("interaction") == "media":
        return "本机实录  ·  打开当次素材清单"
    if recipe["id"] == "ceramic-price":
        return "已找到两条价格记录  ·  原表第 2、3 行"
    return f'本地实测  ·  处理 {pack["measured"]["items"]} 行'


def build_item(args, recipe, item, key, release, skill, browser, save):
    import make
    output=args.output
    if not can_reuse(item,key,release,"capture",output):
        work=output/"episodes"/recipe["id"]/uuid.uuid4().hex[:12]
        evidence=work/"evidence"
        run_and_record(skill,recipe,evidence,release,browser)
        item={"id":recipe["id"],"module":recipe["module"],"step":recipe["step"],"title":recipe["title"],
              "keyword":recipe["keyword"],"key":key,"claim":relative(output,release["archive"]),
              "skill_sha256":release["sha256"],"evidence":relative(output,evidence),"status":"captured"}
        save(item)
    if args.mode=="capture": return item
    evidence=output/item["evidence"]
    pack=verified_evidence(evidence,release)
    highlights=footage_edits(pack)
    movie=evidence.parent/("film-"+uuid.uuid4().hex[:8])
    script=prepare(recipe,movie)
    from proof_camera import follow
    focus=follow(evidence/pack["clip"],highlights)
    for sc in script["scenes"]:
        if sc.get("slot") in focus: sc["pointer_focus"]=focus[sc["slot"]]
    script["scenes"][0].update(hook_status=hook_summary(recipe,pack,evidence),
                               hook_result_at=next(s["end"] for s in pack["steps"] if s["slot"]=="hook"))
    write(movie/"script.json",script)
    stage_voice(args,recipe,script,movie)
    # Each catalog entry is an authored, replayable edition. Project history belongs to ad-hoc topics.
    clip=evidence/pack["clip"]
    footage=[f'{name}={clip}:{slot["start"]}:{slot["dur"]}:{slot["speed"]}' for name,slot in highlights.items()]
    final=make.run(movie/"script.json",footage,
                   "voxcpm",reuse_voice=True,evidence_pack=pack,history_file=movie/"render-history.json")
    pub=read(movie/"publish.json")
    if (pub["pending_footage"] or pub["visual_tier"]!="自写画面" or not pub["motion"]["ok"]
            or not all(s.get("visual") for s in script["scenes"])):
        raise ValueError("画面或实录验收失败")
    subprocess.run(["ffmpeg","-nostdin","-v","error","-xerror","-i",str(final),"-map","0:v","-map","0:a","-f","null","-"],check=True)
    pub["audience_skill"]={"module":recipe["module"],"version":release["version"],"sha256":release["sha256"],
                           "keyword":recipe["keyword"],"archive":os.path.relpath(release["archive"],movie).replace(os.sep,"/")}
    timeline=read(movie/"timeline.json")
    positions={scene.get("slot"):i for i,scene in enumerate(script["scenes"])}
    spans=[0,*timeline["cuts"],timeline["dur"]]
    positions_match = positions.get("hook")==0 and .25 <= spans[positions["mid"]]/timeline["dur"] <= .65
    if not positions_match:
        raise ValueError("实录应出现在首镜和中段")
    pub["recording"]={**pack["evidence"],"pack":os.path.relpath(evidence/"pack.json",movie).replace(os.sep,"/"),
                      "slots":{name:{**slot,"film_start":spans[positions[name]],"film_end":spans[positions[name]+1]}
                               for name,slot in highlights.items()}}
    if recipe.get("template")=="ceramic":pub["visual_assets"]=[{"file":"cup-turntable.webp","source":"原创 Blender 白瓷杯，30 视角"}]
    write(movie/"publish.json",pub)
    item.update(status="ready",video=relative(output,final),publish=relative(output,movie/"publish.json"),
                files={relative(output,movie/f):digest(movie/f) for f in [*pub["files"].values(),"publish.json"]})
    save(item)
    return item


def run(args):
    out=args.output.expanduser().resolve();args.output=out
    if out==ROOT or ROOT in out.parents and not out.is_relative_to(ROOT/"out"):
        raise ValueError("批量运行目录请放到仓库外或 out/ 内")
    out.mkdir(parents=True,exist_ok=True)
    with exclusive(out):
        release=build_release(args.skill,out/"claims")
        modules=read(args.skill/"modules.json")["modules"]
        catalog=load_catalog()
        ready=[r for r in catalog if r["module"] in modules and (args.skill/"assets/demo"/(r["module"]+".json")).is_file()]
        index=out/"series.json"
        state=read(index) if index.is_file() else {"episodes":{}}
        wanted=[x.strip() for x in args.topics.split(",") if x.strip()] if args.topics else []
        if wanted:
            recipes=[]
            for token in wanted:
                hits=[r for r in ready if r["id"]==token or r["module"]==token.upper()]
                if not hits: raise ValueError("没有已完成且已配置实录的选题："+token)
                recipes.extend(r for r in hits if r not in recipes)
        else:
            recipes=[r for r in ready if not can_reuse(state["episodes"].get(r["id"]),key_for(r,release,args.voice_cache),release,args.mode,out)][:args.count]
        if args.mode=="plan":
            for r in ready:print(r["module"],r["id"],r["title"],"→",r["keyword"])
            print("本批候选：",", ".join(r["id"] for r in recipes));return 0
        from playwright.sync_api import sync_playwright
        errors={}
        def save(item):
            state["episodes"][item["id"]]=item
            state["claims"]=[{"topic":e["id"],"keyword":e["keyword"],"archive":e["claim"],"sha256":e["skill_sha256"],"video":e["video"]}
                             for e in state["episodes"].values() if e.get("status")=="ready"]
            write(index,state)
        with tempfile.TemporaryDirectory(prefix="viewer-skill-") as tmp, sync_playwright() as pw:
            with zipfile.ZipFile(release["archive"]) as archive:archive.extractall(tmp)
            skill=Path(tmp)/"ecommerce-automation"
            browser=pw.chromium.launch()
            try:
                for r in recipes:
                    k=r["id"]; key=key_for(r,release,args.voice_cache); item=state["episodes"].get(k)
                    if can_reuse(item,key,release,args.mode,out):
                        print("复用已核验产物",k,flush=True);continue
                    try:
                        print("开始",k,flush=True)
                        build_item(args,r,item,key,release,skill,browser,save)
                    except Exception as err:
                        errors[k]=str(err);print("失败",k,err,flush=True)
            finally:browser.close()
        write(out/"last-run.json",{"mode":args.mode,"selected":[r["id"] for r in recipes],"errors":errors})
        return int(bool(errors))


def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument("mode",choices=["plan","capture","run"])
    ap.add_argument("--output",type=Path,required=True)
    ap.add_argument("--skill",type=Path,default=ROOT/"audience/ecommerce-automation")
    ap.add_argument("--count",type=int,default=1)
    ap.add_argument("--topics",help="显式选模块或选题 ID，逗号分隔")
    ap.add_argument("--voice-python",type=Path)
    ap.add_argument("--voice-cache",type=Path,help="受信的同音色配音，每个选题 ID 下有 voice/，逐段核对文本")
    args=ap.parse_args()
    if args.count<1:ap.error("--count 应大于零")
    return run(args)


if __name__=="__main__":
    sys.exit(main())

