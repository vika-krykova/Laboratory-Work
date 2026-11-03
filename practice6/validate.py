import argparse
import csv
import random
from collections import defaultdict
from pathlib import Path

from common import load_metas, read_json
from config import Config
from decompose import grab_frame
from search import fmt_time, timestamp_url

FIELDS = ["n", "video", "kind", "label", "start", "end", "time", "confidence", "frame", "link", "verdict", "comment"]


def make_sheet(cfg, n, seed):
    metas = {m["id"]: m for m in load_metas(cfg.data_dir)}
    events = [e for vid in metas for e in read_json(Path(cfg.data_dir) / vid / "events.json", [])]
    sample = random.Random(seed).sample(events, min(n, len(events)))
    out = Path(cfg.out_dir) / "validation"
    out.mkdir(parents=True, exist_ok=True)
    rows = []
    for i, e in enumerate(sample, 1):
        m = metas[e["video"]]
        img = out / f"{i:02d}_{e['video']}_{e['kind']}_{int(e['start'])}s.jpg"
        grab_frame(Path(cfg.data_dir) / m["video_file"], (e["start"] + e["end"]) / 2, img)
        rows.append({"n": i, "video": e["video"], "kind": e["kind"], "label": e["label"], "start": e["start"],
                     "end": e["end"], "time": f"{fmt_time(e['start'])}-{fmt_time(e['end'])}",
                     "confidence": e["confidence"], "frame": img.name, "link": timestamp_url(m, e["start"] - 2),
                     "verdict": "", "comment": ""})
    path = Path(cfg.out_dir) / "validation.csv"
    with open(path, "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=FIELDS, delimiter=";")
        w.writeheader()
        w.writerows(rows)
    print(f"Выборка из {len(rows)} событий: {path}. Откройте кадры/ссылки, впишите verdict (1/0).")
    print("Для loud_peak кадр не показателен — слушайте ролик с указанного времени.")


def score(cfg):
    path = Path(cfg.out_dir) / "validation.csv"
    stats = defaultdict(lambda: [0, 0])
    with open(path, encoding="utf-8-sig") as f:
        for r in csv.DictReader(f, delimiter=";"):
            v = (r["verdict"] or "").strip()
            if v in ("0", "1"):
                stats[r["kind"]][0] += 1
                stats[r["kind"]][1] += int(v)
    total = [sum(s[0] for s in stats.values()), sum(s[1] for s in stats.values())]
    for k, (n, ok) in sorted(stats.items()):
        print(f"{k:14s} проверено {n}, верно {ok}, доля {ok / n:.0%}")
    if total[0]:
        print(f"{'ВСЕГО':14s} проверено {total[0]}, верно {total[1]}, доля {total[1] / total[0]:.0%}")
    else:
        print("Нет заполненных verdict.")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--n", type=int, default=5)
    ap.add_argument("--seed", type=int, default=42)
    ap.add_argument("--score", action="store_true")
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="out")
    a = ap.parse_args()
    cfg = Config(data_dir=a.data, out_dir=a.out)
    score(cfg) if a.score else make_sheet(cfg, a.n, a.seed)
