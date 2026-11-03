import wave
import os
import numpy as np


def loudness_db(wav_path, win=1.0):
    out = []
    with wave.open(str(wav_path), "rb") as w:
        n = max(1, int(w.getframerate() * win))
        while True:
            raw = w.readframes(n)
            if not raw:
                break
            x = np.frombuffer(raw, dtype=np.int16).astype(np.float32) / 32768.0
            rms = float(np.sqrt(np.mean(x * x))) if x.size else 0.0
            out.append(round(max(-90.0, 20 * np.log10(rms + 1e-9)), 2))
    return out


class WhisperASR:
    def __init__(self, model_name="base", language="ru"):
        import whisper
        
        local_model_path = f"{model_name}.pt"
        
        if os.path.exists(local_model_path):
            print(f"[ASR] Используем локальную модель: {local_model_path}")
            self.model = whisper.load_model(local_model_path)
        else:
            print(f"[ASR] Модель {model_name} не найдена локально. Скачиваем из интернета...")
            self.model = whisper.load_model(model_name)
            
        self.language = language
        try:
            import torch
            self.fp16 = torch.cuda.is_available()
        except Exception:
            self.fp16 = False

    def __call__(self, wav_path):
        r = self.model.transcribe(str(wav_path), language=self.language, fp16=self.fp16,
                                  condition_on_previous_text=False)   # меньше «зацикливаний» на тишине
        segs = [{"start": round(s["start"], 2), "end": round(s["end"], 2), "text": s["text"].strip(),
                 "no_speech_prob": round(float(s.get("no_speech_prob", 0)), 3),
                 "avg_logprob": round(float(s.get("avg_logprob", 0)), 3)} for s in r["segments"]]
        return {"language": r.get("language"), "text": r["text"].strip(), "segments": segs}


def good_segments(transcript, no_speech_max=0.6):
    return [s for s in (transcript or {}).get("segments", [])
            if s["text"] and s.get("no_speech_prob", 0) <= no_speech_max]