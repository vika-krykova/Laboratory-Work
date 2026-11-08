from __future__ import annotations

import numpy as np
import scipy.sparse as sp

from . import metrics as M


def recommend_all(model, users, seen, n_cand, pop, batch=512):
    out = np.empty((len(users), n_cand), dtype=np.int64)
    tie = 1e-9 * pop / max(pop.max(), 1)     
    for s in range(0, len(users), batch):
        u = users[s:s + batch]
        S = np.asarray(model.score(u), dtype=np.float64) + tie[None, :]
        r, c = seen[u].nonzero()
        S[r, c] = -np.inf
        top = np.argpartition(-S, n_cand - 1, axis=1)[:, :n_cand]
        order = np.argsort(-np.take_along_axis(S, top, 1), axis=1, kind="stable")
        out[s:s + batch] = np.take_along_axis(top, order, 1)
    return out


def mmr_rerank(cand, X, lam, k):
    n, C = cand.shape
    rel = 1 - np.arange(C) / max(C - 1, 1)
    out = np.empty((n, k), dtype=np.int64)
    for a in range(n):
        Xc = X[cand[a]]
        sim = (Xc @ Xc.T).toarray()
        chosen = [0]
        while len(chosen) < k:
            mx = sim[:, chosen].max(1)
            val = lam * rel - (1 - lam) * mx
            val[chosen] = -np.inf
            chosen.append(int(val.argmax()))
        out[a] = cand[a, chosen]
    return out


def relevant_matrix(test, ds, thr):
    t = test[test["rating"] >= thr] if ds.explicit else test
    return sp.csr_matrix((np.ones(len(t), dtype=bool), (t["user"].values, t["item"].values)),
                         shape=(ds.n_users, ds.n_items))
