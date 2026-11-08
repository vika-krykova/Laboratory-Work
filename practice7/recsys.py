#!/usr/bin/env python
from __future__ import annotations

import argparse
import json
import logging
import os
import platform
import time
from importlib import metadata
from pathlib import Path

os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")  
os.environ.setdefault("OMP_NUM_THREADS", "1")

import numpy as np
import pandas as pd

from recsys_lib import data as D
from recsys_lib import eda, evaluate as E, metrics as M, models as MD

log = logging.getLogger("recsys")
MODELS = ["popular", "content", "svd", "als"]


def versions():
    out = {"python": platform.python_version()}
    for p in ["numpy", "scipy", "pandas", "scikit-learn", "scikit-surprise", "implicit"]:
        try:
            out[p] = metadata.version(p)
        except metadata.PackageNotFoundError:
            out[p] = "not installed"
    return out


def parse():
    a = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    a.add_argument("--dataset", required=True, choices=["movielens", "lastfm", "amazon"])
    a.add_argument("--path", required=True, help="папка (movielens/lastfm) или файл отзывов jsonl[.gz] (amazon)")
    a.add_argument("--meta", help="amazon: файл метаданных jsonl[.gz]")
    a.add_argument("--max-rows", type=int, help="amazon: прочитать не больше N отзывов")
    a.add_argument("--model", default="all", help="popular|content|svd|als|bpr|all (all = подходящие датасету)")
    a.add_argument("--k", type=int, nargs="+", default=[5, 10])
    a.add_argument("--evaluate", action="store_true", help="считать метрики; без флага - только выгрузка рекомендаций")
    a.add_argument("--eda", action="store_true", help="построить EDA (eda.json, eda.png)")
    a.add_argument("--output", default="results")
    a.add_argument("--seed", type=int, default=42)
    a.add_argument("--min-interactions", type=int, default=5, help="k-core фильтр для пользователей и объектов")
    a.add_argument("--n-test", type=int, default=5, help="сколько взаимодействий пользователя уходит в тест")
    a.add_argument("--min-history", type=int, default=10, help="пользователи с меньшей историей не попадают в тест")
    a.add_argument("--rel-threshold", type=float, default=4.0, help="явные оценки: рейтинг >= порога = положительное")
    a.add_argument("--factors", type=int, default=50)
    a.add_argument("--segment-threshold", type=int, help="граница light/heavy по числу train-взаимодействий (по умолчанию медиана)")
    a.add_argument("--mmr", type=float, nargs="*", default=[], help="значения lambda для MMR-переранжирования")
    a.add_argument("--cases", type=int, default=2, help="сколько пользователей выгрузить для ручного разбора")
    a.add_argument("--sample-users", type=int, default=20, help="сколько пользователей попадёт в recs.json")
    return a.parse_args()


def main():
    args = parse()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s", datefmt="%H:%M:%S")
    out = Path(args.output); out.mkdir(parents=True, exist_ok=True)
    np.random.seed(args.seed)
    run = {"args": vars(args), "versions": versions()}
    log.info("versions: %s | seed=%d", run["versions"], args.seed)

    t0 = time.time()
    ds = D.load_dataset(args.dataset, args.path, args.meta, args.min_interactions, args.min_interactions, args.max_rows)
    train, test = D.split(ds, args.n_test, args.min_history, args.seed)
    dens = len(ds.inter) / (ds.n_users * ds.n_items)
    run["data"] = {"users": ds.n_users, "items": ds.n_items, "interactions": len(ds.inter), "sparsity": 1 - dens,
                   "train": len(train), "test": len(test), "split": "per-user chronological" if ds.has_time
                   else "per-user random leave-N-out (no timestamps)", "load_sec": time.time() - t0}
    log.info("после фильтрации: %d users, %d items, %d inter, sparsity=%.4f; train=%d test=%d; split=%s",
             ds.n_users, ds.n_items, len(ds.inter), 1 - dens, len(train), len(test), run["data"]["split"])
    if args.eda:
        log.info("EDA: %s", json.dumps(eda.run_eda(ds, out), ensure_ascii=False))

    rel = E.relevant_matrix(test, ds, args.rel_threshold)
    n_rel_all = np.asarray(rel.sum(1)).ravel()
    users = np.flatnonzero(n_rel_all > 0)    
    seen = MD.to_csr(train["user"].values, train["item"].values, np.ones(len(train)), ds)
    seen.data[:] = 1
    ntrain = np.bincount(train["user"], minlength=ds.n_users)
    thr_seg = args.segment_threshold or int(np.median(ntrain[users]))
    seg = {"all": np.ones(len(users), bool), f"light(<= {thr_seg})": ntrain[users] <= thr_seg,
           f"heavy(> {thr_seg})": ntrain[users] > thr_seg}
    log.info("пользователей в оценке: %d (из %d); порог сегментов=%d", len(users), ds.n_users, thr_seg)
    run["data"].update(eval_users=int(len(users)), segment_threshold=thr_seg)

    names = args.model.split(",") if args.model != "all" else (
        ["popular", "content", "svd", "als"] if ds.explicit else ["popular", "content", "als"])
    X = MD.build_tfidf(ds)
    cats = [set(c.split("|")) - {""} or {"?"} for c in ds.items["category"]]
    item_users = np.asarray(seen.sum(0)).ravel()
    pop = np.bincount(train["item"], minlength=ds.n_items).astype(float)
    kmax = max(args.k)
    n_cand = max(kmax, 50) if args.mmr else kmax
    rng = np.random.default_rng(args.seed)
    sample = np.sort(rng.choice(len(users), size=min(args.sample_users, len(users)), replace=False))
    case_idx = sample[:args.cases]

    rows, all_recs, timings, cov_rows = [], {}, {}, []
    for name in names:
        t = time.time()
        model = MD.make_model(name, args.factors, args.seed).fit(train, ds, args.rel_threshold)
        timings[name] = {"fit_sec": round(time.time() - t, 2)}
        cand = E.recommend_all(model, users, seen, n_cand, pop)
        variants = {name: cand[:, :kmax]}
        for lam in args.mmr:
            variants[f"{name}+mmr{lam}"] = E.mmr_rerank(cand, X, lam, kmax)
        for vname, recs in variants.items():
            all_recs[vname] = recs
            if not args.evaluate:
                continue
            sub = rel[users][np.arange(len(users))[:, None], recs]
            hits = np.asarray(sub.todense() if hasattr(sub, "todense") else sub).astype(bool)
            for k in args.k:
                per = M.ranking_metrics(hits, n_rel_all[users], k)
                for sname, mask in seg.items():
                    n = int(mask.sum())
                    if n == 0:
                        continue
                    for mn, arr in per.items():
                        v = arr[mask]
                        rows.append(dict(dataset=ds.name, model=vname, segment=sname, metric=mn, K=k,
                                         value=float(v.mean()), ci95=float(1.96 * v.std(ddof=1) / np.sqrt(n)) if n > 1 else np.nan,
                                         n_users=n))
                    r = recs[mask][:, :k]
                    cm, ct = M.category_stats(cats, r)
                    sub = r[:1000]
                    for mn, v in [("coverage", M.coverage(r, ds.n_items)),
                                  ("diversity_ild", M.intra_list_diversity(X, sub)),
                                  ("novelty", M.novelty(r, item_users, ds.n_users)),
                                  ("categories_per_list", cm), ("categories_total", ct)]:
                        rows.append(dict(dataset=ds.name, model=vname, segment=sname, metric=mn, K=k, value=float(v),
                                         ci95=np.nan, n_users=n))
            if args.evaluate:
                cov_rows.append((vname, M.coverage(recs[:, :kmax], ds.n_items)))
        log.info("%s: fit=%.1fs", name, timings[name]["fit_sec"])

    run["timings"] = timings
    if args.evaluate:
        mdf = pd.DataFrame(rows)
        mdf.to_csv(out / "metrics.csv", index=False, float_format="%.5f")
        eda.coverage_plot(cov_rows, out, kmax)
        piv = mdf[(mdf.segment == "all") & (mdf.K == kmax)].pivot(index="model", columns="metric", values="value")
        log.info("\n%s", piv.round(4).to_string())
        write_cases(out, ds, train, test, users, all_recs, case_idx, rel, kmax, args.rel_threshold)

    sample_json = {m: {str(ds.user_raw[users[i]]): [{"item": str(ds.item_raw[j]), "title": ds.items["title"][j]}
                                                      for j in recs[i]] for i in sample}
                   for m, recs in all_recs.items()}
    (out / "recs.json").write_text(json.dumps(sample_json, ensure_ascii=False, indent=1))
    (out / "run_log.json").write_text(json.dumps(run, ensure_ascii=False, indent=1, default=str))
    log.info("готово -> %s", out)


def write_cases(out, ds, train, test, users, all_recs, idx, rel, k, thr):
    L = [f"# Ручной разбор ({ds.name}, top-{k})\n",
         "Для каждого пользователя ниже напишите в отчете: согласны ли вы с рекомендациями и почему.\n"]
    for i in idx:
        u = users[i]
        h = train[train.user == u].sort_values("rating", ascending=False).head(15)
        t = test[test.user == u]
        relset = set(rel[u].indices)
        L.append(f"\n## Пользователь {ds.user_raw[u]} (train: {int((train.user == u).sum())} взаимодействий)\n")
        L.append("**Топ истории (train):**\n")
        L += [f"- {ds.items['title'][r.item]} [{ds.items['category'][r.item]}] — {r.rating:g}" for r in h.itertuples()]
        L.append("\n**Скрытые релевантные (test):**\n")
        L += [f"- {ds.items['title'][j]} [{ds.items['category'][j]}]" for j in sorted(relset)]
        for m, recs in all_recs.items():
            L.append(f"\n**{m}:**\n")
            L += [f"{n}. {'✅ ' if j in relset else ''}{ds.items['title'][j]} [{ds.items['category'][j]}]"
                  for n, j in enumerate(recs[i][:k], 1)]
    (out / "cases.md").write_text("\n".join(L), encoding="utf-8")


if __name__ == "__main__":
    main()
