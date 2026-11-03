from collections import defaultdict
from pathlib import Path

import numpy as np

from common import read_json, write_json
from visual import read_frames, ru


def merge_times(times, max_gap):
    out = []
    for t in sorted(times):
        if out and t - out[-1][1] <= max_gap:
            out[-1][1] = t
        else:
            out.append([t, t])
    return [tuple(x) for x in out]


def loud_events(db, cfg):
    arr = np.array(db, dtype=float)
    active = arr[arr > -80] 
    if active.size < 5 or active.std() < 1.0:
        return []
    mean, std = active.mean(), active.std()
    z = (arr - mean) / std
    idx = [i for i in range(len(arr)) if z[i] >= cfg.loud_z and arr[i] >= cfg.loud_floor_db]
    events = []
    for a, b in merge_times(idx, 1):
        zmax = float(z[a:b + 1].max())
        events.append({"kind": "loud_peak", "label": "всплеск громкости", "start": float(a), "end": float(b + 1),
                       "confidence": round(min(1.0, zmax / (2 * cfg.loud_z)), 2)})
    return events


def scene_events(rows, interval, cfg):
    events = []
    cuts = [r for r in rows if r["scene_corr"] is not None and r["scene_corr"] < cfg.scene_corr]
    for a, b in merge_times([r["t"] for r in cuts], interval * 1.01):
        corr = min(r["scene_corr"] for r in cuts if a <= r["t"] <= b)
        events.append({"kind": "scene_change", "label": "смена сцены", "start": max(0.0, a - interval), "end": b,
                       "confidence": round(float(min(1.0, max(0.0, 1 - corr))), 2)})
    return events


def object_events(rows, interval, cfg):
    times, confs = defaultdict(list), defaultdict(list)
    for r in rows:
        for d in r["dets"]:
            if d["p"] >= cfg.yolo_conf:
                times[d["c"]].append(r["t"])
                confs[d["c"]].append(d["p"])
    events = []
    for cls, ts in times.items():
        for a, b in merge_times(ts, cfg.obj_max_gap + interval):
            end = b + interval
            if end - a < cfg.obj_min_duration:
                continue
            c = [p for t, p in zip(ts, confs[cls]) if a <= t <= b]
            events.append({"kind": "object", "label": ru(cls), "class": cls, "start": a, "end": end,
                           "confidence": round(float(np.mean(c)), 2)})
    return events


def build_events(vid, data_dir, cfg):
    d = Path(data_dir) / vid
    an = read_json(d / "analysis.json", {})
    interval = an.get("frame_interval", 1.0)
    events = []
    if (d / "detections.jsonl").exists():
        rows = read_frames(d / "detections.jsonl")
        events += scene_events(rows, interval, cfg) + object_events(rows, interval, cfg)
    db = read_json(d / "loudness.json")
    if db:
        events += loud_events(db, cfg)
    for e in events:
        e["video"] = vid
        e["start"], e["end"] = round(e["start"], 2), round(e["end"], 2)
    events.sort(key=lambda e: (e["start"], e["kind"]))
    write_json(d / "events.json", events)
    return events
