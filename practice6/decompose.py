import json
import subprocess

import cv2


def parse_fps(s):
    try:
        a, b = str(s).split("/")
        return float(a) / float(b) if float(b) else 0.0
    except Exception:
        try:
            return float(s)
        except Exception:
            return 0.0


def _num(x, cast=float):
    try:
        return cast(x)
    except Exception:
        return None


def probe(path):
    cmd = ["ffprobe", "-v", "quiet", "-print_format", "json", "-show_streams", "-show_format", str(path)]
    data = json.loads(subprocess.check_output(cmd))
    streams = data.get("streams", [])
    v = next((s for s in streams if s.get("codec_type") == "video"), None)
    a = next((s for s in streams if s.get("codec_type") == "audio"), None)
    if v is None:
        raise ValueError("в файле нет видеопотока")
    fmt = data.get("format", {})
    return {
        "container": fmt.get("format_name"),
        "duration": _num(fmt.get("duration")),
        "size_mb": round((_num(fmt.get("size"), int) or 0) / 1e6, 2),
        "bit_rate": _num(fmt.get("bit_rate"), int),
        "video": {
            "codec": v.get("codec_name"), "width": v.get("width"), "height": v.get("height"),
            "fps": round(parse_fps(v.get("avg_frame_rate", "0/0")), 3),
            "bit_rate": _num(v.get("bit_rate"), int), "pix_fmt": v.get("pix_fmt"),
        },
        "audio": None if a is None else {
            "codec": a.get("codec_name"), "sample_rate": _num(a.get("sample_rate"), int),
            "channels": a.get("channels"),
        },
    }


def extract_audio(video, wav):
    subprocess.run(["ffmpeg", "-y", "-v", "error", "-i", str(video), "-vn", "-ac", "1", "-ar", "16000",
                    "-c:a", "pcm_s16le", str(wav)], check=True)


def pick_interval(duration, forced=None):
    if forced:
        return float(forced)
    if not duration or duration <= 600:
        return 1.0
    if duration <= 1800:
        return 2.0
    return 5.0


def iter_frames(path, interval=1.0):
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise IOError(f"OpenCV не смог открыть {path}")
    try:
        fps = cap.get(cv2.CAP_PROP_FPS)
        if not fps or fps != fps or fps < 1 or fps > 240:
            fps = 25.0
        step = max(1, int(round(fps * interval)))
        idx = 0
        while cap.grab():
            if idx % step == 0:
                ok, frame = cap.retrieve()
                if ok:
                    yield idx / fps, frame
            idx += 1
    finally:
        cap.release()


def grab_frame(path, t, out_jpg):
    cap = cv2.VideoCapture(str(path))
    try:
        cap.set(cv2.CAP_PROP_POS_MSEC, t * 1000)
        ok, frame = cap.read()
        if ok:
            cv2.imwrite(str(out_jpg), frame)
        return ok
    finally:
        cap.release()
