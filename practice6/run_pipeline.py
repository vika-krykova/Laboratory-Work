import argparse
from pathlib import Path

import numpy as np

from audio import loudness_db
from collect import collect_all, read_sources
from common import load_metas, log, log_error, read_json, write_json
from config import Config
from decompose import extract_audio, pick_interval
from events import build_events
from visual import analyze_frames


def _safe(cfg, vid, stage, fn, *a):
    try:
        return fn(*a)
    except Exception as e:
        log_error(cfg.data_dir, vid, stage, f"{type(e).__name__}: {e}")
        log(f"  ! {stage}: {e}")
        return None


def process_video(meta, cfg, detector=None, asr=None, force=False):
    vid = meta["id"]
    d = Path(cfg.data_dir) / vid
    video = Path(cfg.data_dir) / meta["video_file"]
    interval = pick_interval(meta.get("duration"), cfg.frame_interval)
    an = {"frame_interval": interval, "has_audio": meta["tech"]["audio"] is not None}
    wav, tr_path = d / "audio.wav", d / "transcript.json"

    if an["has_audio"]:
        if force or not wav.exists():
            _safe(cfg, vid, "audio_extract", extract_audio, video, wav)
        if wav.exists() and (force or not (d / "loudness.json").exists()):
            db = _safe(cfg, vid, "loudness", loudness_db, wav)
            if db is not None:
                write_json(d / "loudness.json", db)
    else:
        log_error(cfg.data_dir, vid, "audio", "в ролике нет аудиодорожки: транскрипт невозможен")

    if asr and wav.exists() and (force or not tr_path.exists()):
        tr = _safe(cfg, vid, "asr", asr, wav)
        if tr is not None:
            write_json(tr_path, tr)
            if not tr["text"].strip():  
                db = read_json(d / "loudness.json", [])
                why = "тишина" if db and np.mean(db) < -60 else "речь не распознана (музыка/шум/другой язык?)"
                log_error(cfg.data_dir, vid, "asr", f"пустой транскрипт: {why}")

    det_path = d / "detections.jsonl"
    if force or not det_path.exists():
        n = _safe(cfg, vid, "frames", analyze_frames, video, det_path, detector, interval)
        an["n_samples"] = n

    old = read_json(d / "analysis.json", {})
    old.update(an)
    write_json(d / "analysis.json", old)
    return build_events(vid, cfg.data_dir, cfg)


def process_all(sources, cfg, detector=None, asr=None, force=False, stage="all"):
    if stage in ("all", "collect"):
        collect_all(sources, cfg)
    metas = load_metas(cfg.data_dir)
    if stage in ("all", "analyze"):
        for i, m in enumerate(metas, 1):
            log(f"[analyze {i}/{len(metas)}] {m['title']}")
            process_video(m, cfg, detector, asr, force)
    if stage in ("all", "aggregate"):
        from dashboard import build_dashboard
        from report import make_report
        from topics import cluster_videos
        if len(metas) >= 1:
            _safe(cfg, "-", "topics", cluster_videos, metas, cfg.data_dir, cfg)
            _safe(cfg, "-", "report", make_report, cfg)
            _safe(cfg, "-", "dashboard", build_dashboard, cfg)
    return metas


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--sources", default="sources.txt")
    ap.add_argument("--data", default="data")
    ap.add_argument("--out", default="out")
    ap.add_argument("--stage", choices=["all", "collect", "analyze", "aggregate"], default="all")
    ap.add_argument("--whisper", default="base")
    ap.add_argument("--yolo", default="yolov8n.pt")
    ap.add_argument("--conf", type=float, default=0.4, help="порог YOLO для анализа")
    ap.add_argument("--lang", default="ru", help="язык речи или auto")
    ap.add_argument("--method", choices=["kmeans", "hdbscan"], default="kmeans")
    ap.add_argument("--skip-yolo", action="store_true")
    ap.add_argument("--skip-asr", action="store_true")
    ap.add_argument("--force", action="store_true")
    a = ap.parse_args()
    cfg = Config(data_dir=a.data, out_dir=a.out, yolo_model=a.yolo, yolo_conf=a.conf, whisper_model=a.whisper,
                 language=None if a.lang == "auto" else a.lang, topic_method=a.method)

    detector = asr = None
    if a.stage in ("all", "analyze"):
        if not a.skip_yolo:
            from visual import YoloDetector
            detector = YoloDetector(cfg.yolo_model, cfg.yolo_min_conf)
        if not a.skip_asr:
            from audio import WhisperASR
            asr = WhisperASR(cfg.whisper_model, cfg.language)
    sources = read_sources(a.sources) if a.stage in ("all", "collect") else []
    process_all(sources, cfg, detector, asr, a.force, a.stage)
    log(f"Готово. Отчёт: {cfg.out_dir}/report.md, интерфейс: {cfg.out_dir}/dashboard.html, ошибки: {cfg.data_dir}/errors.csv")


if __name__ == "__main__":
    main()
