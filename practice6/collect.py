import hashlib
import re
import shutil
from pathlib import Path

from common import log, log_error, vdir, write_json
from decompose import probe

VIDEO_EXT = {".mp4", ".mkv", ".webm", ".avi", ".mov", ".m4v", ".flv"}


def read_sources(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    return [l.strip() for l in lines if l.strip() and not l.strip().startswith("#")]


def _safe_id(s):
    return re.sub(r"[^\w.-]+", "_", s).strip("_").lower()[:60]


def _find_video(d):
    for p in sorted(Path(d).glob("video.*")):
        if p.suffix.lower() in VIDEO_EXT:
            return p
    return None


def _finish(meta, path, cfg):
    meta["video_file"] = f"{meta['id']}/{path.name}"
    meta["tech"] = probe(path)
    if not meta.get("duration"):
        meta["duration"] = meta["tech"]["duration"]
    views = meta.get("view_count")
    if views:
        meta["engagement_rate"] = round(((meta.get("like_count") or 0) + (meta.get("comment_count") or 0)) / views, 5)
    write_json(Path(cfg.data_dir) / meta["id"] / "meta.json", meta)
    return meta


def _collect_url(url, cfg):
    import yt_dlp
    
    ydl_opts = {
        "quiet": True, 
        "skip_download": True, 
        "noplaylist": True,
        "socket_timeout": 30
    }
    
    with yt_dlp.YoutubeDL(ydl_opts) as ydl:
        info = ydl.extract_info(url, download=False)
        
    vid = _safe_id(f"{info.get('extractor_key', 'web')}_{info['id']}")
    d = vdir(cfg.data_dir, vid)
    path = _find_video(d)
    
    if path is None:
        opts = {
            "quiet": True, 
            "noplaylist": True, 
            "restrictfilenames": True,
            "socket_timeout": 30,
            "format": f"best[height<={cfg.max_height}]/bv*[height<={cfg.max_height}]+ba/best",
            "merge_output_format": "mp4", 
            "outtmpl": str(d / "video.%(ext)s")
        }
        with yt_dlp.YoutubeDL(opts) as ydl:
            ydl.download([url])
        path = _find_video(d)
        if path is None:
            raise FileNotFoundError("yt-dlp не создал файл")
            
    meta = {"id": vid, "source": url, "source_type": "url",
            "title": info.get("title"), "description": info.get("description") or "",
            "duration": info.get("duration"), "view_count": info.get("view_count"),
            "like_count": info.get("like_count"), "comment_count": info.get("comment_count"),
            "upload_date": info.get("upload_date"), "tags": info.get("tags") or [],
            "categories": info.get("categories") or [], "uploader": info.get("uploader"),
            "webpage_url": info.get("webpage_url") or url}
    return _finish(meta, path, cfg)

def _collect_local(src, cfg):
    p = Path(src).expanduser()
    if not p.is_file():
        raise FileNotFoundError(f"нет файла: {src}")
    vid = "local_" + hashlib.sha1(str(p.resolve()).encode("utf-8")).hexdigest()[:8]
    d = vdir(cfg.data_dir, vid)
    dst = d / ("video" + p.suffix.lower())
    if not dst.exists():
        shutil.copy2(p, dst)
    meta = {"id": vid, "source": str(p), "source_type": "local", "title": p.stem, "description": "",
            "tags": [], "categories": [], "webpage_url": None}
    return _finish(meta, dst, cfg)


def collect_all(sources, cfg):
    metas = []
    for i, src in enumerate(sources, 1):
        log(f"[collect {i}/{len(sources)}] {src}")
        try:
            metas.append(_collect_url(src, cfg) if src.startswith(("http://", "https://")) else _collect_local(src, cfg))
        except Exception as e:
            log_error(cfg.data_dir, src, "collect", f"{type(e).__name__}: {e}")
            log(f"  ! пропущен: {e}")
    return metas