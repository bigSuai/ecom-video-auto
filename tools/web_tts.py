"""用本机开着的 VoxCPM 网页版（默认 http://127.0.0.1:8808）给一条视频配音，音色固定为 assets/voice/ref.wav。

网页版占着显卡时，本地脚本再加载一份模型会爆显存，所以默认走网页版。
网页版只读得到它自己目录里的文件：脚本会先把参考音复制到 <VoxCPM>/output/gradio/ecomvoice_ref/ref.wav。

用法（在用户电脑上运行）：
  python tools/web_tts.py out/<编号>                       # 全部重配
  python tools/web_tts.py out/<编号> --only s03 s05         # 只重配某几段
  python tools/web_tts.py out/<编号> --voxcpm D:\\promgram\\.ai_vedio\\VoxCPM --url http://127.0.0.1:8808
然后：python pipeline/make.py out/<编号>/script.json --reuse-voice

某段失败或时长异常只重试那一段（最多 2 次），仍失败就整体报错，不留半截结果。
"""
import argparse, hashlib, json, os, shutil, sys, urllib.request
from pathlib import Path
from _paths import ROOT
import numpy as np
from audio import SR, read_wav, write_wav
from compile_script import segments
import tts

DEFAULT_URL = "http://127.0.0.1:8808"
DEFAULT_VOXCPM = r"D:\promgram\.ai_vedio\VoxCPM"
SEED, CFG, STEPS = 42, 2, 10


def _md5(p: Path) -> str:
    return hashlib.md5(Path(p).read_bytes()).hexdigest()


def stage_ref(voxcpm_dir: Path, ref_wav: Path) -> Path:
    """把参考音放进网页版能读的目录；内容没变就不重复复制"""
    dst = Path(voxcpm_dir) / "output" / "gradio" / "ecomvoice_ref" / "ref.wav"
    dst.parent.mkdir(parents=True, exist_ok=True)
    if not dst.is_file() or _md5(dst) != _md5(ref_wav):
        shutil.copyfile(ref_wav, dst)
    return dst


class WebBackend:
    """tts.synthesize 用的后端：调网页版的 /gradio_api/call/generate"""
    def __init__(self, url: str, ref_on_server: Path, timeout: float = 300):
        self.url, self.ref, self.timeout = url.rstrip("/"), str(ref_on_server), timeout

    def _post(self, path, body):
        req = urllib.request.Request(self.url + path, data=json.dumps(body).encode("utf-8"), headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=30) as r:
            return json.loads(r.read().decode("utf-8"))

    def _get(self, path):
        with urllib.request.urlopen(self.url + path, timeout=self.timeout) as r:
            return r.read()

    def say(self, text, ref_wav, ref_text, out):
        body = {"data": [text, "", {"path": self.ref, "meta": {"_type": "gradio.FileData"}}, True, ref_text, CFG, False, False, STEPS, SEED]}
        ev = self._post("/gradio_api/call/generate", body).get("event_id")
        if not ev:
            raise RuntimeError("网页版没有返回任务编号")
        sse = self._get("/gradio_api/call/generate/" + ev).decode("utf-8", "replace")
        data = None
        for block in sse.split("\n\n"):
            if block.startswith("event: complete"):
                data = json.loads(block.split("data:", 1)[1])
            elif block.startswith("event: error"):
                raise RuntimeError("网页版报错：" + block[-200:])
        if not data or not isinstance(data[0], dict):
            raise RuntimeError("网页版没有返回音频")
        f = data[0]
        src = Path(f.get("path") or "")
        if src.is_file():
            shutil.copyfile(src, out)
        else:                                   # 不在同一台机器上时按网址下载
            Path(out).write_bytes(self._get("/gradio_api/file=" + urllib.request.quote(str(f["path"]))))


def run(out_dir: Path, url: str = DEFAULT_URL, voxcpm: Path = Path(DEFAULT_VOXCPM), only=None, backend=None) -> dict:
    from import_voice import squeeze
    out_dir = Path(out_dir)
    script = json.loads((out_dir / "script.json").read_text(encoding="utf-8"))
    voice_assets = ROOT / "assets" / "voice"
    ref = voice_assets / "ref.wav"
    transcript = voice_assets / "ref.txt"
    if not ref.is_file() or not transcript.is_file():
        raise tts.TTSFailed("请在 assets/voice/ 配置 ref.wav 和 ref.txt，或运行 python tools/design_voice.py --auto。")
    ref_txt = transcript.read_text(encoding="utf-8").strip()
    segs = segments(script)
    want = [s for s in segs if not only or s[0] in only]
    if backend is None:
        backend = WebBackend(url, stage_ref(voxcpm, ref))
    vdir = out_dir / "voice"; raw = out_dir / "_voice_raw"
    tts.synthesize(want, raw, backend, ref, ref_txt)          # 逐段合成、失败只重试该段、时长核对
    voice = json.loads((vdir / "voice.json").read_text(encoding="utf-8")) if only and (vdir / "voice.json").is_file() else {}
    vdir.mkdir(parents=True, exist_ok=True)
    for sid, _ in want:
        x = squeeze(read_wav(raw / f"{sid}.wav"))
        write_wav(vdir / f"{sid}.wav", x); voice[sid] = round(len(x) / SR, 3)
    voice = {sid: voice[sid] for sid, _ in segs if sid in voice}
    if set(voice) != {sid for sid, _ in segs}:
        raise tts.TTSFailed("还有配音段没有生成：" + "、".join(s for s, _ in segs if s not in voice))
    (vdir / "voice.json").write_text(json.dumps(voice), encoding="utf-8")
    (vdir / "texts.json").write_text(json.dumps(dict(segs), ensure_ascii=False), encoding="utf-8")
    return voice


if __name__ == "__main__":
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("out_dir"); ap.add_argument("--url", default=os.environ.get("VOXCPM_URL", DEFAULT_URL))
    ap.add_argument("--voxcpm", default=os.environ.get("VOXCPM_DIR", DEFAULT_VOXCPM)); ap.add_argument("--only", nargs="*")
    a = ap.parse_args()
    try:
        print(run(Path(a.out_dir), a.url, Path(a.voxcpm), a.only))
    except (tts.TTSFailed, OSError, RuntimeError) as e:
        print("配音失败：", e); sys.exit(1)
