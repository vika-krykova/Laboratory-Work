from collections import Counter
from pathlib import Path

import numpy as np
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics import silhouette_score

from audio import good_segments
from common import read_json, write_json
from textutils import normalize, _WORD, _norm_word
from visual import read_frames, ru


def video_text(meta, data_dir, cfg):
    d = Path(data_dir) / meta["id"]
    tr = read_json(d / "transcript.json")
    speech = " ".join(s["text"] for s in good_segments(tr, cfg.no_speech_max))
    parts = [meta.get("title") or "", (meta.get("description") or "")[:1000],
             " ".join(meta.get("tags") or []), speech]
    fr = d / "detections.jsonl"
    if fr.exists():
        rows = read_frames(fr)
        if rows:
            cnt = Counter(c for r in rows for c in {x["c"] for x in r["dets"] if x["p"] >= cfg.yolo_conf})
            parts.append(" ".join(ru(c).replace(" ", "_") for c, n in cnt.items() if n / len(rows) >= 0.2))
    return " ".join(parts)


def _surface_map(texts):
    cnt = {}
    for t in texts:
        for w in _WORD.findall(t.lower().replace("ё", "е")):
            tok = _norm_word(w)
            cnt.setdefault(tok, Counter())[w] += 1
    return {k: v.most_common(1)[0][0] for k, v in cnt.items()}


def cluster_videos(metas, data_dir, cfg):
    texts = [video_text(m, data_dir, cfg) for m in metas]
    n = len(metas)
    vec = TfidfVectorizer(tokenizer=normalize, lowercase=False, token_pattern=None, sublinear_tf=True,
                          max_features=5000, max_df=0.9 if n >= 8 else 1.0)
    X = vec.fit_transform(texts)
    terms = np.array(vec.get_feature_names_out())
    surf = _surface_map(texts)
    sil_by_k, noise = {}, 0

    if n < 3:
        labels = np.zeros(n, dtype=int)
    elif cfg.topic_method == "hdbscan":
        from sklearn.cluster import HDBSCAN
        from sklearn.decomposition import TruncatedSVD
        comp = max(1, min(50, X.shape[1] - 1, n - 1))
        Z = TruncatedSVD(comp, random_state=42).fit_transform(X)
        labels = HDBSCAN(min_cluster_size=2).fit_predict(Z)
        noise = int((labels == -1).sum())
        if len(set(labels) - {-1}) >= 2 and (labels != -1).sum() > len(set(labels) - {-1}):
            m = labels != -1
            sil_by_k["hdbscan"] = round(float(silhouette_score(X[m], labels[m], metric="cosine")), 3)
    else:
        best, labels = -2, None
        for k in range(2, min(cfg.max_k, n - 1) + 1):
            lab = KMeans(n_clusters=k, random_state=42, n_init=10).fit_predict(X)
            if len(set(lab)) < 2:
                continue
            s = float(silhouette_score(X, lab, metric="cosine"))
            sil_by_k[k] = round(s, 3)
            if s > best:
                best, labels = s, lab
        if labels is None:
            labels = np.zeros(n, dtype=int)

    clusters = []
    for c in sorted(set(int(x) for x in labels)):
        idx = [i for i in range(n) if labels[i] == c]
        centroid = np.asarray(X[idx].mean(axis=0)).ravel()
        top = [surf.get(terms[j], terms[j]) for j in centroid.argsort()[::-1][:8] if centroid[j] > 0]
        clusters.append({"cluster": c, "size": len(idx), "top_terms": top,
                         "videos": [metas[i]["id"] for i in idx]})
    result = {"method": cfg.topic_method, "n_videos": n, "silhouette_by_k": sil_by_k,
              "noise": noise, "clusters": clusters,
              "assignment": {metas[i]["id"]: int(labels[i]) for i in range(n)}}
    write_json(Path(data_dir) / "topics.json", result)
    return result
