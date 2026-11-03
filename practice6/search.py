"""Поиск по транскриптам и найденным объектам. Консольный интерфейс:  python search.py "ремонт" """
import argparse
import sys
from pathlib import Path

from audio import good_segments
from common import load_metas, read_json
from config import Config
from textutils import normalize


def fmt_time(t):
    t = int(t)
    return f"{t // 60:02d}:{t % 60:02d}"


def timestamp_url(meta, t):
    """Ссылка на момент: YouTube принимает &t=75s; для локальных файлов — #t=75 (media fragment)."""
    t = int(max(0, t))
    url = meta.get("webpage_url")
    if url:
        return f"{url}{'&' if '?' in url else '?'}t={t}s"
    return f"{meta['video_file']}#t={t}"


def load_index(cfg):
    topics = read_json(Path(cfg.data_dir) / "topics.json", {}) or {}
    assign = topics.get("assignment", {})
    index = []
    for m in load_metas(cfg.data_dir):
        d = Path(cfg.data_dir) / m["id"]
        segs = good_segments(read_json(d / "transcript.json"), cfg.no_speech_max)
        for s in segs:
            s["_tok"] = set(normalize(s["text"]))
        index.append({"meta": m, "segments": segs, "events": read_json(d / "events.json", []),
                      "cluster": assign.get(m["id"])})
    return index


def search(index, query, cluster=None):
    q = set(normalize(query))
    if not q:
        return []
    hits = []
    for v in index:
        if cluster is not None and v["cluster"] != cluster:
            continue
        m = v["meta"]
        for s in v["segments"]:
            if q <= s["_tok"]:
                hits.append({"video": m["id"], "title": m["title"], "kind": "речь", "start": s["start"],
                             "end": s["end"], "text": s["text"], "url": timestamp_url(m, s["start"])})
        for e in v["events"]:
            if e["kind"] == "object" and q <= set(normalize(e["label"])):
                hits.append({"video": m["id"], "title": m["title"], "kind": "объект", "start": e["start"],
                             "end": e["end"], "text": f"{e['label']} (уверенность {e['confidence']})",
                             "url": timestamp_url(m, e["start"])})
    return sorted(hits, key=lambda h: (h["video"], h["start"]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("query", nargs="?")
    ap.add_argument("--data", default="data")
    args = ap.parse_args()
    index = load_index(Config(data_dir=args.data))
    print(f"Роликов в индексе: {len(index)}. Пустой ввод — выход.")
    q = args.query
    while True:
        if q is None:
            try:
                q = input("\nЗапрос> ").strip()
            except EOFError:
                break
        if not q:
            break
        hits = search(index, q)
        print(f"Найдено: {len(hits)}")
        for h in hits[:50]:
            print(f"  [{h['kind']}] {h['title'][:40]} | {fmt_time(h['start'])}-{fmt_time(h['end'])} | {h['text'][:80]}\n      {h['url']}")
        if args.query:
            break
        q = None


if __name__ == "__main__":
    sys.exit(main())
