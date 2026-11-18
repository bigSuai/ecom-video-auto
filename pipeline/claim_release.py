"""Build a deterministic viewer skill release from its portable distribution files."""
import hashlib
import json
import os
import re
import tempfile
import zipfile
from pathlib import Path

def digest(path):
    with Path(path).open("rb") as stream:
        h = hashlib.sha256()
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            h.update(chunk)
        return h.hexdigest()

def build_release(skill_root, output):
    src, out = Path(skill_root).resolve(), Path(output).resolve()
    mandatory = {"SKILL.md", "modules.json", "scripts/ecommerce.py"}
    registry = json.loads((src / "modules.json").read_text(encoding="utf-8-sig"))
    version = registry["version"]
    if not re.fullmatch(r"[0-9]+(?:\.[0-9]+){1,3}(?:[-+][A-Za-z0-9.-]+)?", version):
        raise ValueError("领取包版本号无效")
    if out == src or src in out.parents:
        raise ValueError("领取包输出目录必须位于技能源码外")
    allowed = {"agents":{".yaml",".yml"}, "scripts":{".py"}, "references":{".md"}, "assets":{".json"}}
    files = {}
    for p in src.rglob("*"):
        rel = p.relative_to(src)
        if not p.is_file() or any(s.startswith(".") or s=="__pycache__" for s in rel.parts):
            continue
        if not (rel.as_posix() in mandatory or (len(rel.parts)==1 and p.suffix==".md")
                or (len(rel.parts)>1 and p.suffix in allowed.get(rel.parts[0],set()))):
            continue
        if p.resolve()!=p or not p.resolve().is_relative_to(src):
            raise ValueError(f"领取包文件不是普通源文件：{rel}")
        files[rel.as_posix()] = p
    if not mandatory.issubset(files):
        raise ValueError("领取包文件不完整")
    out.mkdir(parents=True,exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=out,suffix=".tmp",delete=False) as stream:
        temp=Path(stream.name)
    try:
        with zipfile.ZipFile(temp,"w") as archive:
            for name,p in sorted(files.items()):
                info=zipfile.ZipInfo("ecommerce-automation/"+name,(2020,1,1,0,0,0))
                info.create_system=3
                info.external_attr=0o100644<<16
                archive.writestr(info,p.read_bytes(),compress_type=zipfile.ZIP_DEFLATED)
        sha=digest(temp)
        final=out/f"ecommerce-automation-v{version}-{sha[:16]}.zip"
        os.replace(temp,final)
        return {"archive":str(final),"sha256":sha,"version":version}
    finally:
        temp.unlink(missing_ok=True)

