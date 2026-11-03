from collections import Counter, defaultdict
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

from audio import good_segments
from common import load_metas, read_json
from textutils import normalize, has_lemmatizer, _WORD, _norm_word
from visual import read_frames, ru

KIND_RU = {"object": "объект", "loud_peak": "всплеск громкости", "scene_change": "смена сцены"}
COLORS = {"object": "#4c78a8", "loud_peak": "#f58518", "scene_change": "#8e6bbf"}


def md_table(df, max_rows=30):
    if df.empty:
        return "_нет данных_\n"
    df = df.head(max_rows)
    head = "| " + " | ".join(map(str, df.columns)) + " |\n|" + "---|" * len(df.columns) + "\n"
    rows = "".join("| " + " | ".join(str(x) for x in r) + " |\n" for r in df.itertuples(index=False))
    return head + rows


def _save(fig, out, name):
    fig.tight_layout()
    fig.savefig(Path(out) / name, dpi=130)
    plt.close(fig)


def videos_table(metas, cfg):
    rows = []
    for m in metas:
        d = Path(cfg.data_dir) / m["id"]
        tr = read_json(d / "transcript.json")
        t, v = m["tech"], m["tech"]["video"]
        rows.append({"id": m["id"], "title": (m["title"] or "")[:45], "duration_s": round(m.get("duration") or 0),
                     "resolution": f"{v['width']}x{v['height']}", "codec": v["codec"], "fps": v["fps"],
                     "has_audio": t["audio"] is not None, "views": m.get("view_count"),
                     "engagement": m.get("engagement_rate"),
                     "segments": len(good_segments(tr, cfg.no_speech_max)) if tr else None,
                     "words": len((tr or {}).get("text", "").split()) if tr else None})
    return pd.DataFrame(rows)


def object_stats(metas, cfg):
    st = defaultdict(lambda: {"videos": set(), "frames": 0, "conf": [], "max": 0})
    total = 0
    for m in metas:
        p = Path(cfg.data_dir) / m["id"] / "detections.jsonl"
        if not p.exists():
            continue
        for r in read_frames(p):
            total += 1
            cnt = Counter(d["c"] for d in r["dets"] if d["p"] >= cfg.yolo_conf)
            for c, k in cnt.items():
                s = st[c]
                s["videos"].add(m["id"]); s["frames"] += 1; s["max"] = max(s["max"], k)
            for d in r["dets"]:
                if d["p"] >= cfg.yolo_conf:
                    st[d["c"]]["conf"].append(d["p"])
    rows = [{"class": ru(c), "class_en": c, "videos": len(s["videos"]), "frames": s["frames"],
             "share_of_frames_%": round(100 * s["frames"] / max(total, 1), 1),
             "mean_conf": round(float(np.mean(s["conf"])), 2), "max_per_frame": s["max"]}
            for c, s in st.items()]
    return pd.DataFrame(rows).sort_values("frames", ascending=False) if rows else pd.DataFrame(), total


def conf_sweep(metas, cfg):
    confs = []
    n_frames = 0
    per_frame = []
    for m in metas:
        p = Path(cfg.data_dir) / m["id"] / "detections.jsonl"
        if p.exists():
            for r in read_frames(p):
                n_frames += 1
                per_frame.append([d["p"] for d in r["dets"]])
    ths = np.round(np.arange(0.25, 0.95, 0.05), 2)
    tot = [sum(1 for f in per_frame for p in f if p >= t) for t in ths]
    any_ = [100 * sum(1 for f in per_frame if any(p >= t for p in f)) / max(n_frames, 1) for t in ths]
    return ths, tot, any_


def term_stats(metas, cfg, top=30):
    cnt, docs, surf = Counter(), Counter(), {}
    for m in metas:
        tr = read_json(Path(cfg.data_dir) / m["id"] / "transcript.json")
        text = " ".join(s["text"] for s in good_segments(tr, cfg.no_speech_max))
        toks = normalize(text)
        cnt.update(toks); docs.update(set(toks))
        for w in _WORD.findall(text.lower().replace("ё", "е")):
            surf.setdefault(_norm_word(w), Counter())[w] += 1
    return pd.DataFrame([{"term": surf.get(t, Counter({t: 1})).most_common(1)[0][0], "count": n, "videos": docs[t]}
                         for t, n in cnt.most_common(top)])


def make_report(cfg):
    out = Path(cfg.out_dir); out.mkdir(parents=True, exist_ok=True)
    metas = load_metas(cfg.data_dir)
    topics = read_json(Path(cfg.data_dir) / "topics.json", {}) or {}
    events = [e for m in metas for e in read_json(Path(cfg.data_dir) / m["id"] / "events.json", [])]

    vt = videos_table(metas, cfg); vt.to_csv(out / "videos.csv", index=False, sep=";", encoding="utf-8-sig")
    ev = pd.DataFrame(events)
    if not ev.empty:
        ev["kind_ru"] = ev["kind"].map(KIND_RU)
        ev.to_csv(out / "events.csv", index=False, sep=";", encoding="utf-8-sig")
    ot, n_frames = object_stats(metas, cfg); ot.to_csv(out / "objects_stats.csv", index=False, sep=";", encoding="utf-8-sig")
    ts = term_stats(metas, cfg); ts.to_csv(out / "terms_stats.csv", index=False, sep=";", encoding="utf-8-sig")

    if not ot.empty:
        top = ot.head(15).iloc[::-1]
        fig, ax = plt.subplots(figsize=(7, 5)); ax.barh(top["class"], top["frames"], color="#4c78a8")
        ax.set_xlabel(f"кадров с объектом (conf ≥ {cfg.yolo_conf})"); ax.set_title("Топ-15 распознанных объектов")
        _save(fig, out, "objects_top.png")
        ths, tot, any_ = conf_sweep(metas, cfg)
        fig, ax = plt.subplots(figsize=(7, 4)); ax.plot(ths, tot, "o-", color="#4c78a8"); ax.set_ylabel("всего детекций")
        ax.set_xlabel("порог conf"); ax2 = ax.twinx(); ax2.plot(ths, any_, "s--", color="#f58518")
        ax2.set_ylabel("% кадров хотя бы с одним объектом"); ax.axvline(cfg.yolo_conf, color="gray", ls=":")
        ax.set_title("Чувствительность к порогу YOLO"); _save(fig, out, "conf_sweep.png")
    if not ev.empty:
        piv = ev.pivot_table(index="video", columns="kind", values="start", aggfunc="count", fill_value=0)
        fig, ax = plt.subplots(figsize=(7, 4)); bottom = np.zeros(len(piv))
        for k in piv.columns:
            ax.bar(range(len(piv)), piv[k], bottom=bottom, label=KIND_RU.get(k, k), color=COLORS.get(k)); bottom += piv[k].values
        ax.set_xticks(range(len(piv))); ax.set_xticklabels([v[-8:] for v in piv.index], rotation=45, ha="right")
        ax.set_ylabel("число событий"); ax.legend(); ax.set_title("События по роликам"); _save(fig, out, "events_by_video.png")
        # громкость + события для ролика с наибольшим числом событий
        best = ev["video"].value_counts().index[0]
        db = read_json(Path(cfg.data_dir) / best / "loudness.json")
        if db:
            fig, ax = plt.subplots(figsize=(9, 3.5)); ax.plot(range(len(db)), db, color="#555", lw=1)
            for e in events:
                if e["video"] == best:
                    ax.axvspan(e["start"], e["end"], color=COLORS.get(e["kind"]), alpha=0.25)
            ax.set_xlabel("секунды"); ax.set_ylabel("dBFS"); ax.set_title(f"Громкость и события: {best}")
            _save(fig, out, "timeline_example.png")
    if topics.get("clusters"):
        cl = topics["clusters"]
        fig, ax = plt.subplots(figsize=(7, 4))
        ax.bar([f"{c['cluster']}: {', '.join(c['top_terms'][:3])}" for c in cl], [c["size"] for c in cl], color="#54a24b")
        ax.set_ylabel("роликов"); ax.set_title("Тематическое распределение"); plt.setp(ax.get_xticklabels(), rotation=30, ha="right")
        _save(fig, out, "topics.png")

    errs = Path(cfg.data_dir) / "errors.csv"
    errs_md = md_table(pd.read_csv(errs, sep=";", encoding="utf-8-sig")) if errs.exists() else "_ошибок нет_\n"
    kinds = ev["kind_ru"].value_counts().rename_axis("вид").reset_index(name="событий") if not ev.empty else pd.DataFrame()
    tcl = pd.DataFrame([{"тема": c["cluster"], "роликов": c["size"], "ключевые слова": ", ".join(c["top_terms"]),
                         "ролики": ", ".join(c["videos"])} for c in topics.get("clusters", [])])

    md = f"""# Практика 6. Автоматический анализ и семантическая обработка видео

> Заготовка сгенерирована автоматически. Таблицы и графики — результат запуска; разделы «Комментарий»
> и «Обоснование» нужно написать самому по своим данным (что получилось, что нет, почему).

## 0. Данные
Обработано роликов: **{len(metas)}**, проанализировано кадров: **{n_frames}**,
лемматизация: **{'pymorphy3' if has_lemmatizer() else 'грубый стемминг (установите pymorphy3)'}**.

{md_table(vt)}
Пропуски и предупреждения (data/errors.csv):

{errs_md}
**Комментарий:** _TODO_

## 1. Ключевые визуальные характеристики и объекты
{md_table(ot, 15)}
![](objects_top.png)

**Комментарий:** _TODO: какие объекты ожидались для темы, какие найдены, где модель ошибается_

## 2. Временные метки значимых событий
{md_table(kinds)}
Полный список: `events.csv`. Пример таймлайна:

![](timeline_example.png)
![](events_by_video.png)

**Комментарий:** _TODO_

## 3. Статистика по распознанным сущностям
Объекты — таблица в п.1 (`objects_stats.csv`). Самые частые термины в речи (`terms_stats.csv`):

{md_table(ts, 20)}
**Комментарий:** _TODO_

## 4. Интерактивная временная шкала
Файл `dashboard.html` (запуск: `python -m http.server` в корне проекта, затем `/out/dashboard.html`).
Поиск по слову или объекту, клик по событию/результату перематывает видео.

## 5. Тематические распределения
Метод: **{topics.get('method')}**, silhouette по k: `{topics.get('silhouette_by_k')}`.

{md_table(tcl)}
![](topics.png)

**Комментарий:** _TODO: прочитайте 3–5 роликов из каждого кластера — тема действительно общая?_

## Обоснование параметров
| Параметр | Значение | Почему |
|---|---|---|
| YOLO | {cfg.yolo_model} | _TODO (скорость/качество на CPU)_ |
| Порог conf | {cfg.yolo_conf} | _TODO: см. `conf_sweep.png`_ |
| Whisper | {cfg.whisper_model} | _TODO_ |
| Шаг кадров | 1 / 2 / 5 с в зависимости от длины | компромисс «полнота / время» |
| Громкость | z ≥ {cfg.loud_z}, не тише {cfg.loud_floor_db} dB | _TODO_ |
| Смена сцены | корреляция гистограмм < {cfg.scene_corr} | _TODO_ |
| Объект как событие | ≥ {cfg.obj_min_duration} с, пропуск ≤ {cfg.obj_max_gap} с | _TODO_ |

![](conf_sweep.png)

## Ручная проверка
Результат `python validate.py --score` (случайные события, сверка с видео): _TODO_

## Ограничения и этика
_TODO: морфология при поиске, ошибки Whisper на шуме, условия платформ. Эмоции и «внимание» по лицам не выводились._
"""
    (out / "report.md").write_text(md, encoding="utf-8")
    return out / "report.md"
