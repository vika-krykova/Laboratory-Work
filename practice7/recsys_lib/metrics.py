from __future__ import annotations

import numpy as np


def ranking_metrics(hits, n_rel, k):
    h = hits[:, :k].astype(float)
    n_rel = np.asarray(n_rel, dtype=float)
    cum = np.cumsum(h, axis=1)
    ranks = np.arange(1, k + 1)
    disc = 1.0 / np.log2(ranks + 1)
    ap = (cum / ranks * h).sum(1) / np.minimum(n_rel, k)
    dcg = (h * disc).sum(1)
    idcg = np.cumsum(disc)[np.minimum(n_rel, k).astype(int) - 1]
    return {"precision": h.sum(1) / k, "recall": h.sum(1) / n_rel, "map": ap, "ndcg": dcg / idcg}


def coverage(recs, n_items):
    return len(np.unique(recs)) / n_items


def intra_list_diversity(X, recs):
    k = recs.shape[1]
    if k < 2:
        return np.nan
    out = []
    for r in recs:
        S = (X[r] @ X[r].T).toarray()
        out.append(1 - (S.sum() - np.trace(S)) / (k * (k - 1)))
    return float(np.mean(out))


def category_stats(cats, recs):
    per, allc = [], set()
    for r in recs:
        s = set().union(*(cats[i] for i in r))
        per.append(len(s)); allc |= s
    return float(np.mean(per)), len(allc)


def novelty(recs, item_users, n_users):
    p = np.maximum(item_users, 1) / n_users
    return float((-np.log2(p[recs])).mean())
