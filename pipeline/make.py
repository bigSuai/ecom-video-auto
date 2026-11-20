"""一键出片：剧本检查与查重 → 实录抽帧/占位 → 配音 → 编译 → 抽帧检查 → 渲染 → 时长复查 → 选曲混音 → 合成 → 发布信息 → 记入历史。
用法：python pipeline/make.py out/<id>/script.json [--footage hook=<视频>:<起点秒>:<时长秒>[:<倍速>]] [--footage mid=…] [--footage auto] [--tts-backend voxcpm|fake]
--footage auto：用 assets/footage/s<步骤>/pack.json 素材包的高光片段；没有可用素材包时用示意占位。
任何一步失败都不记入历史。"""
import argparse, datetime, json, os, subprocess, sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
sys.path.insert(0, str(HERE))
from compile_script import compile_script, segments
from footage import extract, placeholder
from mix import mix
from pack import load_pack
from music_pick import pick as pick_track
from pick_topic import load_history
from script_check import MAX_S, MIN_S, CPS, check
import tts

class Stop(Exception):
    pass

def _parse_footage(args):
    if args == ["auto"]: return "auto"
    out = {}
    for a in args or []:
        slot, _, rest = a.partition("=")
        parts = rest.rsplit(":", 3)
        try:
            if len(parts) == 4: clip, start, dur, speed = parts[0], float(parts[1]), float(parts[2]), float(parts[3])
            else:
                parts = rest.rsplit(":", 2); clip, start, dur, speed = parts[0], float(parts[1]), float(parts[2]), 4.0
        except (ValueError, IndexError):
            raise Stop(f"--footage 写法不对：{a}（应为 槽位=视频路径:起点秒:时长秒[:倍速]）")
        if a == "auto": raise Stop("--footage auto 不能和具体槽位写法混用")
        if slot not in ("hook", "mid"): raise Stop(f"实录槽位只能是 hook 或 mid：{slot}")
        out[slot] = (Path(clip), start, dur, speed)
    return out

def step_id(script: dict) -> str:
    return f"s{script.get('step')}"

def footage_slots(script: dict, wanted, out: Path, evidence_pack=None) -> dict:
    """wanted 是 _parse_footage 的结果：'auto' 时用这一步的素材包（没有或待确认就占位）。"""
    if wanted == "auto":
        p = evidence_pack if evidence_pack is not None else (load_pack(step_id(script)) if script.get("step") is not None else None)
        wanted = {}
        if p:
            for slot, h in (p.get("highlights") or {}).items():
                wanted[slot] = (Path(p["dir"]) / p["clip"], float(h["start"]), float(h["dur"]), float(h.get("speed", 1)))
    foot = {}
    for slot in {sc.get("slot") for sc in script["scenes"] if sc["type"] == "footage" or sc.get("slot") == "hook"}:
        if slot in (wanted or {}):
            clip, start, dur, speed = wanted[slot]
            try: foot[slot] = extract(clip, Path(out) / "frames" / slot, start, dur, speed)
            except (FileNotFoundError, ValueError, RuntimeError) as e: raise Stop(str(e))
        else:
            foot[slot] = placeholder()
    return foot

def _node(script_name: str, content: Path, out: Path, what: str):
    r = subprocess.run(["node", str(HERE / script_name)], env={**os.environ, "CONTENT": str(content), "OUT_DIR": str(out)},
                       capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise Stop(f"{what}失败：{(r.stderr or r.stdout).strip()[-400:]}")

def _ffmpeg(args, cwd, what):
    r = subprocess.run(["ffmpeg", "-v", "error", "-y", *args], cwd=str(cwd), capture_output=True, text=True, encoding="utf-8", errors="replace")
    if r.returncode != 0:
        raise Stop(f"{what}失败：{r.stderr.strip()[-300:]}")

def run(script_path: Path, footage_args, backend_name: str, reuse_voice: bool = False, music_mode: str = "compose", check_history=None,
        allow_still: bool = False, fallback_preview: bool = False, evidence_pack=None, history_file=None) -> Path:
    """check_history：剧本检查时拿来比对“近 N 条不重复”的历史；重出旧片时传它原来位置之前的历史。"""
    script = json.loads(script_path.read_text(encoding="utf-8"))
    vid = script["id"]; out = script_path.parent
    history_path = Path(history_file) if history_file is not None else ROOT / "data" / "history.json"; history = load_history(history_path)
    final = out / f"{vid}.mp4"
    if not fallback_preview and not all(sc.get("visual") for sc in script["scenes"]):
        raise Stop("正式成片需要每个内容镜头使用专属 visual.js。模板预览请显式传 --fallback-preview。")

    print("1/9 剧本检查")
    p = evidence_pack if evidence_pack is not None else (load_pack(step_id(script)) if script.get("step") is not None else None)
    probs = check(script, history if check_history is None else check_history, measured=(p or {}).get("measured"))
    import dedupe
    hist_for_dup = history if check_history is None else check_history
    probs += dedupe.check(script, dedupe.load_history_scripts(hist_for_dup, ROOT / "out", exclude=vid))
    if probs:
        raise Stop("剧本检查没通过：\n" + "\n".join("  ✗ " + p for p in probs))
    for i, sc in enumerate(script["scenes"]):
        img = sc.get("image") or next((im.get("file") for im in script.get("images") or [] if im.get("scene") == i and sc["type"] == "photo"), None)
        if sc["type"] == "photo" and (not img or not (ROOT / "assets" / "images" / img).is_file()):
            raise Stop(f"第 {i+1} 个场景的配图不存在：{img}（先用 tools/gen_image.py 生成）")

    print("2/9 实录槽位")
    foot = footage_slots(script, _parse_footage(footage_args), out, evidence_pack)
    pending = any(not f.get("n") for f in foot.values())

    print("3/9 配音")
    try:
        voice = tts.reuse_voice(script, out) if reuse_voice else tts.voice_for_script(script, out, backend_name)
    except tts.TTSFailed as e:
        raise Stop(f"配音失败：{e}")

    print("4/9 编译内容")
    content = out / "content.js"
    try:
        content.write_text(compile_script(script, voice, foot, out / "visual.js"), encoding="utf-8")
    except FileNotFoundError as e:
        raise Stop(str(e))

    print("5/9 抽帧检查 → contact.jpg")
    _node("shots.js", content, out, "抽帧")
    print("6/9 渲染")
    for f in out.glob("scene*.mp4"): f.unlink()
    _node("render.js", content, out, "渲染")
    timeline = json.loads((out / "timeline.json").read_text(encoding="utf-8"))
    secs = float(timeline["dur"])
    import motion_check
    n0 = len(timeline["cuts"]) + 1
    (out / "list.txt").write_text("".join(f"file 'scene{i}.mp4'\n" for i in range(n0)), encoding="utf-8")
    _ffmpeg(["-f", "concat", "-safe", "0", "-i", "list.txt", "-c", "copy", "video.mp4"], out, "拼接")
    mc = motion_check.check(out / "video.mp4")
    (out / "motion.json").write_text(json.dumps(mc, ensure_ascii=False, indent=1), encoding="utf-8")
    print(f"   画面运动：静止 {mc['still_ratio']:.1%}，冻结 {len(mc['still_runs'])} 段，缺新动作 {len(mc['event_gaps'])} 段")
    tier = "自写画面" if all(sc.get("visual") for sc in script["scenes"]) else "兜底版"
    if tier == "兜底版" and not mc["ok"]:
        print("   ! 兜底场景库做不到全程运动，这条标为\"画面为兜底版\"（交付时要告诉用户）")
    elif not mc["ok"] and not allow_still:
        raise Stop("画面运动检查没通过（详见 motion.json）：\n" + "\n".join("  ✗ " + p for p in mc["problems"]) +
                   "\n  → 给这些时间段加入场、镜头推移、数字跳动或持续微动；兜底场景库做不到时改写 visual.js")
    if not MIN_S <= secs <= MAX_S:
        diff = (MIN_S - secs) if secs < MIN_S else (secs - MAX_S)
        raise Stop(f"成片时长 {secs:.1f} 秒，不在 {MIN_S}–{MAX_S} 秒内：配音文本大约要{'加' if secs < MIN_S else '删'} {int(diff * CPS) + 1} 个字")

    print("7/9 选曲与混音")
    try:
        if music_mode == "compose":
            from audio import write_wav
            from compose import compose, plan_music, sections_from_script, seed_for
            seed = seed_for(vid); mood = script.get("mood")
            write_wav(out / "music.wav", compose(timeline, sections_from_script(script, timeline), mood, seed))
            plan = plan_music(timeline, mood if mood else "upbeat", seed)
            track = {"id": f"composed-{seed}", "file": str(out / "music.wav"), "aligned": True, "title": "原创配乐",
                     "source": f"代码编曲（{plan['bpm']} BPM，{plan['palette']} 乐器组），音色库 GeneralUser GS",
                     "license": "自有；音色库允许商用", "license_url": "", "attribution": ""}
        else:
            lib_path = ROOT / "assets" / "music" / "library.json"
            library = json.loads(lib_path.read_text(encoding="utf-8")) if lib_path.is_file() else []
            track = pick_track(library, script.get("mood"), history)
        mix(timeline, out / "voice", track, out / "audio.wav", out / f"{vid}.srt")
    except (ValueError, FileNotFoundError, RuntimeError, ImportError) as e:
        raise Stop(f"配乐失败：{e}")

    print("8/9 合成")
    _ffmpeg(["-i", "video.mp4", "-i", "audio.wav", "-map", "0:v", "-map", "1:a", "-c:v", "copy", "-c:a", "aac", "-b:a", "192k",
             "-shortest", "-movflags", "+faststart", "final.tmp.mp4"], out, "合成")
    (out / "final.tmp.mp4").replace(final)
    try:
        from review import review
        review(final, out / "review.jpg")
        print("   审片联系表：review.jpg（每秒一格，逐格对照 SKILL.md 的审片清单）")
    except (RuntimeError, OSError, subprocess.CalledProcessError) as e:
        print("   ! 审片联系表没生成：", e)
    for f in [out / "video.mp4", out / "list.txt", *out.glob("scene*.mp4")]: f.unlink()

    print("9/9 发布信息与历史")
    idx_path = ROOT / "assets" / "images" / "index.json"
    idx = {e["file"]: e for e in (json.loads(idx_path.read_text(encoding="utf-8")) if idx_path.is_file() else [])}
    used = {sc.get("image") for sc in json.loads(content.read_text(encoding="utf-8").split("window.CONTENT=")[1].split(";\nwindow.VO=")[0])["scenes"] if sc.get("image")}
    publish = {"id": vid, "title": script.get("title"), "tags": script.get("tags"), "platform": (script.get("cta") or {}).get("platform"),
               "comment_keyword": (script.get("cta") or {}).get("keyword"), "seconds": round(secs, 1),
               "reminder": "发布前请人工看一遍成片，并在平台上打 AI 生成内容标识。" + ("配乐要求署名，请把 music.attribution 这一行贴进视频简介。" if track.get("attribution") else ""),
               "pending_footage": pending if script.get("type") != "hot" else False,
               **({"source": {k: (script.get("hot") or {}).get(k) for k in ("topic", "source_url", "source_date")}} if script.get("type") == "hot" else {}), "pending_note": "实录槽位目前是示意画面，对应 skill 录屏后可替换重出。" if pending else "",
               "images": [idx.get(f, {"file": f, "license": "未登记"}) for f in sorted(used)],
               "music": {k: track.get(k) for k in ("id", "title", "source", "license", "license_url", "attribution")},
               "files": {"video": final.name, "subtitles": f"{vid}.srt", "contact_sheet": "contact.jpg", "review_sheet": "review.jpg", "motion_report": "motion.json"},
               "visual_tier": tier, "motion": {k: mc.get(k) for k in ("still_ratio", "ok", "problems")}}
    (out / "publish.json").write_text(json.dumps(publish, ensure_ascii=False, indent=1), encoding="utf-8")
    history.append({"id": vid, "date": datetime.date.today().isoformat(), "type": script.get("type"), "step": script.get("step"),
                    "angle_index": script.get("angle_index", 0), "structure": script.get("structure"), "mid_hook": script.get("mid_hook"),
                    "theme": script.get("theme"), "track": track["id"], "has_footage": not pending})
    history_path.parent.mkdir(parents=True, exist_ok=True)
    history_path.write_text(json.dumps(history, ensure_ascii=False, indent=1), encoding="utf-8")
    if history_file is None and script.get("type") == "hot": mark_hot_used((script.get("hot") or {}).get("source_url"))
    return final

def mark_hot_used(url, path: Path = ROOT / "data" / "hot.json") -> None:
    try: items = json.loads(Path(path).read_text(encoding="utf-8"))
    except (OSError, ValueError): return
    for h in items:
        if h.get("source_url") == url: h["used"] = True
    Path(path).write_text(json.dumps(items, ensure_ascii=False, indent=1), encoding="utf-8")

def main(argv=None) -> int:
    for s in (sys.stdout, sys.stderr):
        try: s.reconfigure(encoding="utf-8")
        except Exception: pass
    ap = argparse.ArgumentParser()
    ap.add_argument("script"); ap.add_argument("--footage", action="append"); ap.add_argument("--tts-backend", default="voxcpm", choices=["voxcpm", "fake"])
    ap.add_argument("--music", default="compose", choices=["compose", "library"], help="compose：按剧本段落原创编曲；library：从曲库选曲")
    ap.add_argument("--reuse-voice", action="store_true", help="复用 out/<id>/voice/ 里已合成的配音")
    ap.add_argument("--allow-still", action="store_true", help="画面运动检查不过也出片（只用于调试，交付的片子不能用）")
    ap.add_argument("--fallback-preview", action="store_true", help="显式使用内置场景作预览")
    a = ap.parse_args(argv)
    try:
        final = run(Path(a.script).resolve(), a.footage, a.tts_backend, a.reuse_voice, a.music, allow_still=a.allow_still, fallback_preview=a.fallback_preview)
    except Stop as e:
        print("✗", e); return 1
    print("✓ 成片：", final); return 0

if __name__ == "__main__":
    sys.exit(main())
