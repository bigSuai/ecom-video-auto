"""网页版配音：用一个假的 gradio 服务验证调用格式、取回、失败只重试该段。"""
import json, sys, threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import numpy as np
import pytest
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "tools")); sys.path.insert(0, str(ROOT / "pipeline"))
from audio import SR, write_wav
import web_tts, tts

REFERENCE_TEXT = "这是网页版配音测试使用的虚构参考文本。"


@pytest.fixture
def voice_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(web_tts, "ROOT", tmp_path)
    assets = tmp_path / "assets" / "voice"
    assets.mkdir(parents=True)
    samples = np.arange(SR) / SR
    write_wav(assets / "ref.wav", np.asarray(0.3 * np.sin(2 * np.pi * 440 * samples), dtype=np.float32))
    (assets / "ref.txt").write_text(REFERENCE_TEXT, encoding="utf-8")


def _server(tmp, fail_first=0):
    calls = {"post": [], "n": 0}
    class H(BaseHTTPRequestHandler):
        def log_message(self, *a): pass
        def do_POST(self):
            body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
            calls["post"].append(body)
            self.send_response(200); self.end_headers(); self.wfile.write(json.dumps({"event_id": str(len(calls["post"]))}).encode())
        def do_GET(self):
            calls["n"] += 1
            self.send_response(200); self.end_headers()
            if calls["n"] <= fail_first:
                self.wfile.write(b"event: error\ndata: null\n\n"); return
            text = calls["post"][-1]["data"][0]
            n = int(len(text) / 4.5 * SR); t = np.arange(n) / SR
            wav = tmp / f"gen{calls['n']}.wav"; write_wav(wav, np.concatenate([np.zeros(4800), 0.4 * np.sin(2 * np.pi * 300 * t), np.zeros(4800)]).astype(np.float32))
            self.wfile.write(("event: complete\ndata: " + json.dumps([{"path": str(wav)}, 42]) + "\n\n").encode())
    srv = HTTPServer(("127.0.0.1", 0), H); threading.Thread(target=srv.serve_forever, daemon=True).start()
    return srv, calls


def _out(tmp):
    out = tmp / "out" / "x"; out.mkdir(parents=True)
    (out / "script.json").write_text(json.dumps({"scenes": [{"type": "statement", "vo": "老客户该回访谁，先把名单备好。"},
                                                            {"type": "cta", "vo": "关注我，上线后领取。"}]}, ensure_ascii=False), encoding="utf-8")
    return out


def test_web_voice_end_to_end(tmp_path, voice_reference):
    srv, calls = _server(tmp_path)
    out = _out(tmp_path); vox = tmp_path / "VoxCPM"
    v = web_tts.run(out, f"http://127.0.0.1:{srv.server_port}", vox)
    assert set(v) == {"s01", "s02"} and all(d > 1 for d in v.values())
    assert (vox / "output" / "gradio" / "ecomvoice_ref" / "ref.wav").is_file()
    d = calls["post"][0]["data"]
    assert d[2]["path"].endswith("ref.wav") and d[3] is True and d[4] == REFERENCE_TEXT
    assert d[5:] == [2, False, False, 10, 42]
    assert json.loads((out / "voice" / "texts.json").read_text(encoding="utf-8"))["s02"] == "关注我，上线后领取。"
    srv.shutdown()


def test_retry_only_failed_segment(tmp_path, voice_reference):
    srv, calls = _server(tmp_path, fail_first=1)
    out = _out(tmp_path)
    web_tts.run(out, f"http://127.0.0.1:{srv.server_port}", tmp_path / "V")
    assert len(calls["post"]) == 3                      # 第一段失败一次重试，第二段一次成功
    srv.shutdown()


def test_only_keeps_other_segments(tmp_path, voice_reference):
    srv, calls = _server(tmp_path)
    out = _out(tmp_path); url = f"http://127.0.0.1:{srv.server_port}"
    web_tts.run(out, url, tmp_path / "V")
    n = len(calls["post"]); web_tts.run(out, url, tmp_path / "V", only=["s02"])
    assert len(calls["post"]) == n + 1 and set(json.loads((out / "voice" / "voice.json").read_text())) == {"s01", "s02"}
    srv.shutdown()


def test_server_down_fails_cleanly(tmp_path, voice_reference):
    out = _out(tmp_path)
    with pytest.raises(tts.TTSFailed):
        web_tts.run(out, "http://127.0.0.1:9", tmp_path / "V")
    assert not (out / "voice" / "voice.json").exists()


def test_clean_install_explains_missing_reference(tmp_path, monkeypatch):
    monkeypatch.setattr(web_tts, "ROOT", tmp_path)
    with pytest.raises(tts.TTSFailed, match=r"ref\.wav 和 ref\.txt"):
        web_tts.run(_out(tmp_path), "http://127.0.0.1:9", tmp_path / "V")
