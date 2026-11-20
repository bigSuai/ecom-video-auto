import zipfile

import pytest

from claim_release import build_release, digest
from series_batch import can_reuse, key_for, load_catalog
from series_recipe import ROOT, prepare, write
import make


def test_registered_episodes_are_authored_and_distributable(tmp_path):
    catalog = load_catalog()
    assert {r["module"] for r in catalog} == set("ABCDEFG")
    src = ROOT / "audience/ecommerce-automation"
    package = build_release(src, tmp_path/"first")
    second = build_release(src, tmp_path/"second")
    assert package["sha256"] == second["sha256"]
    with zipfile.ZipFile(package["archive"]) as z:
        for r in catalog:
            assert "ecommerce-automation/assets/demo/" + r["module"] + ".json" in z.namelist()
            path = tmp_path / r["id"]
            script = prepare(r, path)
            assert all(sc.get("visual") for sc in script["scenes"])
            assert script["scenes"][0]["slot"] == "hook"
            assert script["scenes"][0]["visual"] == r["id"] + "_hook"
            assert ("scale_example" in script["scenes"][0]) == (r["id"] == "listing-queue")
            assert any(sc.get("slot") == "mid" for sc in script["scenes"])
            assert (path/"visual.js").is_file()
        assert not any("__pycache__" in n for n in z.namelist())

    with pytest.raises(ValueError, match="专属分镜"):
        prepare(dict(catalog[0], id="new-ceramic-topic"), tmp_path/"unbound")


def test_visuals_are_required_before_render(tmp_path):
    p = tmp_path/"script.json"
    write(p, {"id":"preview", "scenes":[{"visual":"hero"}, {"type":"steps"}]})
    with pytest.raises(make.Stop,match="专属"):
        make.run(p, [], "fake")


def test_evidence_does_not_accept_a_different_clip_or_measured_count(tmp_path):
    src = ROOT/"audience/ecommerce-automation"
    release = build_release(src,tmp_path/"claims")
    record = tmp_path/"capture"
    record.mkdir()
    sha = digest(src/"assets/demo/B.json")
    write(record/"run.json",{"status":"completed","run_id":"r","input_sha256":sha,
                             "summary":{"processed_rows":3},"processing_seconds":0.1})
    for name in ("clip.mp4","execution.webm","report.html","result.json"):
        (record/name).write_bytes(name.encode())
    pack = {"review":"ok","clip":"clip.mp4","measured":{"items":3,"seconds":0.1},
            "evidence":{"module":"B","run_id":"r","input_sha256":sha,"release_sha256":release["sha256"],
                        "report":"report.html","report_sha256":digest(record/"report.html"),
                        "result_sha256":digest(record/"result.json"),"clip_sha256":digest(record/"clip.mp4"),
                        "raw_sha256":digest(record/"execution.webm")}}
    write(record/"pack.json",pack)
    item={"key":"k","evidence":"capture","status":"captured"}
    assert can_reuse(item,"k",release,"capture",tmp_path)
    assert not can_reuse(item,"k",release,"run",tmp_path)
    pack["measured"]["items"] += 1
    write(record/"pack.json",pack)
    assert not can_reuse(item,"k",release,"capture",tmp_path)
    pack["measured"]["items"] -= 1
    write(record/"pack.json",pack)
    (record/"execution.webm").write_bytes(b"other file")
    assert not can_reuse(item,"k",release,"capture",tmp_path)


def test_changed_voice_invalidates_render_cache(tmp_path):
    recipe=load_catalog()[0]
    folder=tmp_path/recipe["id"]/"voice"
    folder.mkdir(parents=True)
    wav=folder/"s01.wav"
    wav.write_bytes(b"first")
    old=key_for(recipe,{"sha256":"test"},tmp_path)
    wav.write_bytes(b"second")
    assert key_for(recipe,{"sha256":"test"},tmp_path) != old

def test_frame_based_trim_finds_four_views_and_rejects_missing_section(monkeypatch,tmp_path):
    from types import SimpleNamespace
    import series_evidence
    colors=[(220,20,20),(20,220,20),(20,20,220),(20,220,220)]
    pixels=b"".join(bytes(color)*100 for color in colors)
    monkeypatch.setattr(series_evidence.subprocess,"run",lambda *args,**kwargs: SimpleNamespace(stdout=pixels))
    assert series_evidence.recorded_starts(tmp_path/"raw.webm",[1.4,2.1,2.1,2.4]) == [.04,4.04,8.04,12.04]
    with pytest.raises(ValueError,match="原始录像"):
        series_evidence.recorded_starts(tmp_path/"raw.webm",[1.4,2.1,2.1,6])

def test_keyword_returns_only_a_verified_ready_release(tmp_path):
    from resolve_claim import resolve
    path=tmp_path/"claims/viewer.zip"
    path.parent.mkdir()
    path.write_bytes(b"example contents")
    row={"keyword":"查价","topic":"ceramic","archive":"claims/viewer.zip","sha256":digest(path),"video":"film.mp4"}
    item={"status":"ready","claim":row["archive"],"skill_sha256":row["sha256"],"video":row["video"]}
    write(tmp_path/"series.json",{"claims":[row],"episodes":{"ceramic":item}})
    assert resolve(tmp_path,"查价")["archive"]==str(path)
    with pytest.raises(ValueError,match="尚无"):
        resolve(tmp_path,"上架")
    path.write_bytes(b"other contents")
    with pytest.raises(ValueError,match="不符"):
        resolve(tmp_path,"查价")


def test_dual_capture_requires_distinct_traceable_slots():
    from series_batch import footage_edits
    hook = {"start": 0, "dur": 2.88, "speed": 1}
    mid = {"start": 2.88, "dur": 4.96, "speed": 1}
    pack = {"highlights": {"hook": hook, "mid": mid}, "steps": [{"slot": "hook"}, {"slot": "mid"}]}
    assert footage_edits(pack) == pack["highlights"]
    pack["highlights"] = {"mid": mid}
    with pytest.raises(ValueError, match="开头和中段"):
        footage_edits(pack)
    pack["highlights"] = {"hook": hook, "mid": {**mid, "start": 0}}
    with pytest.raises(ValueError, match="剪辑范围"):
        footage_edits(pack)
