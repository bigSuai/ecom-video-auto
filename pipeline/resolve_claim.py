"""Resolve a viewer's keyword to the exact verified ZIP for an already rendered episode."""
import argparse
import json
from pathlib import Path

from claim_release import digest
from series_recipe import read


def resolve(output, keyword, topic=None):
    root = Path(output).resolve()
    state = read(root / "series.json")
    brand = keyword.strip()
    hits = []
    for row in state["claims"]:
        if row["keyword"] != brand or (topic and row["topic"] != topic):
            continue
        episode = state["episodes"][row["topic"]]
        if (episode.get("status") != "ready" or row["archive"] != episode["claim"]
                or row["sha256"] != episode["skill_sha256"] or row["video"] != episode["video"]):
            raise ValueError("领取索引与成片记录不一致")
        hits.append(row)
    if not hits:
        raise ValueError("此关键词尚无已出片的领取项")
    if len({(r["archive"], r["sha256"]) for r in hits}) > 1:
        raise ValueError("相同关键词对应多个版本，请同时传入 --topic")
    selected = hits[0]
    archive = (root / selected["archive"]).resolve()
    if archive.parent != (root/"claims").resolve() or not archive.is_file() or digest(archive) != selected["sha256"]:
        raise ValueError("领取 ZIP 缺失或内容与本集不符")
    return {"keyword":brand, "topics":[r["topic"] for r in hits],
            "archive":str(archive),"sha256":selected["sha256"]}


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output",required=True,type=Path)
    parser.add_argument("--keyword",required=True)
    parser.add_argument("--topic",help="同关键词多版本时由视频编号指定")
    args = parser.parse_args()
    try:
        print(json.dumps(resolve(args.output,args.keyword,args.topic),ensure_ascii=False))
    except (OSError,KeyError,ValueError) as error:
        parser.exit(1,str(error)+"\n")
