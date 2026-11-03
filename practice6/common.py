import csv
import json
import time
from pathlib import Path


def log(msg):
    print(time.strftime("%H:%M:%S"), msg, flush=True)


def vdir(data_dir, vid):
    p = Path(data_dir) / vid
    p.mkdir(parents=True, exist_ok=True)
    return p


def read_json(path, default=None):
    p = Path(path)
    if not p.exists():
        return default
    with open(p, encoding="utf-8") as f:
        return json.load(f)


def write_json(path, obj):
    p = Path(path)
    tmp = p.with_suffix(p.suffix + ".tmp")
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=1)
    tmp.replace(p)


def log_error(data_dir, source, stage, reason):
    p = Path(data_dir) / "errors.csv"
    p.parent.mkdir(parents=True, exist_ok=True)
    new = not p.exists()
    with open(p, "a", newline="", encoding="utf-8-sig") as f:
        w = csv.writer(f, delimiter=";")
        if new:
            w.writerow(["time", "source", "stage", "reason"])
        w.writerow([time.strftime("%Y-%m-%d %H:%M:%S"), source, stage, str(reason)[:300]])


def load_metas(data_dir):
    metas = []
    for p in sorted(Path(data_dir).glob("*/meta.json")):
        m = read_json(p)
        if m:
            metas.append(m)
    return metas
