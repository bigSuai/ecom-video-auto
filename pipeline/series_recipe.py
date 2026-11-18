"""Resolve registered episodes into the member renderer's normal script contract."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SERIES = ROOT / "series"

def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))

def write(path, value):
    p = Path(path)
    tmp = p.with_name(p.name + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(p)

# Keep different promotional structures and hook treatments across the editorial rotation.
FORMATS = {
    "D": ("pain-then-result-first","result_first","ink","calm"),
    "F": ("day-in-life","pitfall","dusk","warm"),
    "C": ("contrast-then-suspense","best_feature","mint","tense"),
    "G": ("timer-race","steps","paper","upbeat"),
    "A": ("count-up","result_first","ink","playful"),
    "E": ("question-then-pitfall","pitfall","mint","warm"),
}

def prepare(recipe, dest):
    import shutil
    dest.mkdir(parents=True, exist_ok=True)
    if recipe.get("template"):
        src = SERIES / recipe["template"]
        script = read(src / "script.json")
        visual = src / "visual.js"
        for asset in sorted(p for p in src.iterdir() if p.suffix.lower() in {".webp", ".png", ".jpg", ".jpeg", ".svg"}):
            shutil.copyfile(asset, dest / asset.name)
    else:
        module = recipe["module"]
        structure, hook, theme, mood = recipe.get("format") or FORMATS[module]
        visual = SERIES / "workflow.js"
        heads = recipe["design"]
        types = ["photo","statement","footage","steps","reveal","cta"]
        scenes = [dict(type=kind, visual=vis, vo=vo, head=head,
                       palette=recipe["palette"], module=module, labels=heads[3], values=heads[4],
                       evidence=heads[6], keyword=recipe["keyword"], topic=recipe["title"])
                  for kind,vis,vo,head in zip(types,["opening","compare","live","align","resolution","claim"],
                                              recipe["voice"],[heads[0],heads[1],["本地实录","查看运行报告"],heads[2],heads[5],["免费领取",recipe["keyword"]+"助手"]])]
        scenes[0]["image"] = recipe["image"]
        scenes[1]["mascot"] = dict(pos="bottomRight",S=250,x=740,f=1450,pose="point",hop=[1.6,3.2])
        scenes[2].update(slot="mid", report_title="虚构样本 · 本次运行", report_note="来自观众领取包")
        scenes[3]["mid_hook"] = True
        scenes[4]["payoff"] = True
        scenes[5].update(mascot=dict(pos="cta",S=350,x=680,f=1445,pose="wave",hop=[1.5,3.5]),follow="关注",followed="已关注")
        script = dict(type="product",step=recipe["step"],angle_index=0,structure=structure,mid_hook=hook,
                      theme=theme,mood=mood,skill={"provided":True,"name":"ecommerce-automation"},
                      title=recipe["title"],tags=["#电商自动化","#电商运营","#店铺运营"],
                      images=[dict(scene=0,file=recipe["image"])],cta=dict(keyword=recipe["keyword"],platform="douyin"),scenes=scenes)
    script["id"] = recipe["id"]
    shutil.copyfile(visual,dest/"visual.js")
    write(dest/"script.json",script)
    return script

