from __future__ import annotations

import logging

import numpy as np
import scipy.sparse as sp
from sklearn.feature_extraction.text import TfidfVectorizer

log = logging.getLogger("recsys")
ALPHA = 40.0 


def positives(train, ds, thr):
    if ds.explicit:
        t = train[train["rating"] >= thr]
        return t["user"].values, t["item"].values, np.ones(len(t))
    return train["user"].values, train["item"].values, np.log1p(train["rating"].values)


def to_csr(u, i, v, ds):
    return sp.csr_matrix((v, (u, i)), shape=(ds.n_users, ds.n_items))


class Model:
    name = "base"

    def fit(self, train, ds, thr):
        raise NotImplementedError

    def score(self, users):
        raise NotImplementedError


class Popular(Model):
    name = "popular"

    def fit(self, train, ds, thr):
        u, i, v = positives(train, ds, thr)
        self.pop = np.bincount(i, minlength=ds.n_items).astype(float)
        return self

    def score(self, users):
        return np.tile(self.pop, (len(users), 1))


class Content(Model):
    name = "content"

    def __init__(self, max_features=10000, min_df=2):
        self.mf, self.min_df = max_features, min_df

    def fit(self, train, ds, thr):
        self.X = build_tfidf(ds, self.mf, self.min_df)
        u, i, v = positives(train, ds, thr)
        W = to_csr(u, i, v, ds)
        norm = np.asarray(W.sum(axis=1)).ravel()
        norm[norm == 0] = 1
        self.W = sp.diags(1 / norm) @ W       
        return self

    def score(self, users):
        prof = self.W[users] @ self.X                    
        return (prof @ self.X.T).toarray()


def build_tfidf(ds, max_features=10000, min_df=2):
    texts = ds.items["text"].values
    try:
        return TfidfVectorizer(max_features=max_features, min_df=min_df).fit_transform(texts).tocsr()
    except ValueError:                                         
        return TfidfVectorizer(max_features=max_features, min_df=1).fit_transform(texts).tocsr()


class SVDModel(Model):
    name = "svd"

    def __init__(self, factors=50, epochs=20, seed=42):
        self.f, self.ep, self.seed = factors, epochs, seed

    def fit(self, train, ds, thr):
        if not ds.explicit:
            raise SystemExit("SVD (surprise) требует явных оценок: используйте movielens/amazon. Для lastfm - als/bpr.")
        lo, hi = train["rating"].min(), train["rating"].max()
        try:
            from surprise import SVD, Dataset as SDataset, Reader
        except ImportError:
            log.warning("scikit-surprise не установлен -> ЗАПАСНАЯ реализация (ALS-MF в numpy). "
                        "Для сдачи установите surprise!")
            return self._fallback(train, ds, lo, hi)
        data = SDataset.load_from_df(train[["user", "item", "rating"]], Reader(rating_scale=(lo, hi)))
        ts = data.build_full_trainset()       # сплит сделан вручную -> полный trainset оправдан
        algo = SVD(n_factors=self.f, n_epochs=self.ep, random_state=self.seed).fit(ts)
        self.mu = ts.global_mean
        self.bu = np.zeros(ds.n_users); self.bi = np.zeros(ds.n_items)
        self.P = np.zeros((ds.n_users, self.f)); self.Q = np.zeros((ds.n_items, self.f))
        for iu in ts.all_users():
            ru = ts.to_raw_uid(iu); self.bu[ru] = algo.bu[iu]; self.P[ru] = algo.pu[iu]
        for ii in ts.all_items():              
            ri = ts.to_raw_iid(ii); self.bi[ri] = algo.bi[ii]; self.Q[ri] = algo.qi[ii]
        return self

    def _fallback(self, train, ds, lo, hi):
        rng = np.random.default_rng(self.seed)
        R = to_csr(train["user"].values, train["item"].values, train["rating"].values, ds)
        self.mu = train["rating"].mean()
        res = train["rating"].values - self.mu
        cu = np.bincount(train["user"], minlength=ds.n_users); su = np.bincount(train["user"], res, ds.n_users)
        self.bu = su / (cu + 10)
        res = res - self.bu[train["user"].values]
        ci = np.bincount(train["item"], minlength=ds.n_items); si = np.bincount(train["item"], res, ds.n_items)
        self.bi = si / (ci + 10)
        res = res - self.bi[train["item"].values]
        E = to_csr(train["user"].values, train["item"].values, res + 1e-12, ds)
        self.P, self.Q = _als_explicit(E, self.f, 0.1 * 20, 8, rng)
        return self

    def score(self, users):
        return self.mu + self.bu[users][:, None] + self.bi[None, :] + self.P[users] @ self.Q.T


def _als_explicit(E, f, reg, iters, rng):
    nu, ni = E.shape
    X = rng.normal(0, 0.1, (nu, f)); Y = rng.normal(0, 0.1, (ni, f))

    def solve(M, F):
        out = np.zeros((M.shape[0], f)); I = reg * np.eye(f)
        for r in range(M.shape[0]):
            s, e = M.indptr[r], M.indptr[r + 1]
            if s == e:
                continue
            Fy = F[M.indices[s:e]]
            out[r] = np.linalg.solve(Fy.T @ Fy + I, Fy.T @ M.data[s:e])
        return out
    ET = E.T.tocsr()
    for _ in range(iters):
        X = solve(E, Y); Y = solve(ET, X)
    return X, Y


def _als_implicit(Cm1, f, reg, iters, rng):
    nu, ni = Cm1.shape
    X = rng.normal(0, 0.01, (nu, f)); Y = rng.normal(0, 0.01, (ni, f))

    def solve(M, F):
        FtF = F.T @ F + reg * np.eye(f)
        out = np.zeros((M.shape[0], f))
        for r in range(M.shape[0]):
            s, e = M.indptr[r], M.indptr[r + 1]
            if s == e:
                continue
            c = M.data[s:e]; Fy = F[M.indices[s:e]]
            out[r] = np.linalg.solve(FtF + (Fy.T * c) @ Fy, Fy.T @ (c + 1))
        return out
    CT = Cm1.T.tocsr()
    for _ in range(iters):
        X = solve(Cm1, Y); Y = solve(CT, X)
    return X, Y


class ImplicitModel(Model):
    def __init__(self, kind="als", factors=64, iters=15, seed=42):
        self.kind, self.f, self.iters, self.seed = kind, factors, iters, seed
        self.name = kind

    def fit(self, train, ds, thr):
        u, i, v = positives(train, ds, thr)
        conf = to_csr(u, i, 1 + ALPHA * v, ds)                 # users x items, CSR
        assert conf.format == "csr" and conf.shape == (ds.n_users, ds.n_items)
        try:
            if self.kind == "als":
                from implicit.cpu.als import AlternatingLeastSquares
                m = AlternatingLeastSquares(factors=self.f, regularization=0.01, iterations=self.iters,
                                            random_state=self.seed, num_threads=1, calculate_training_loss=False)
                m.fit(conf, show_progress=False)
            else:
                from implicit.cpu.bpr import BayesianPersonalizedRanking
                m = BayesianPersonalizedRanking(factors=self.f, iterations=100, random_state=self.seed, num_threads=1)
                m.fit((conf > 0).astype(np.float32).tocsr(), show_progress=False)
            self.U, self.V = np.asarray(m.user_factors), np.asarray(m.item_factors)
        except ImportError:
            if self.kind != "als":
                raise SystemExit("BPR требует установленной библиотеки implicit.")
            log.warning("implicit не установлен -> ЗАПАСНАЯ реализация ALS в numpy. Для сдачи установите implicit!")
            Cm1 = conf.copy(); Cm1.data = Cm1.data - 1
            self.U, self.V = _als_implicit(Cm1, self.f, 0.01 * 10, self.iters, np.random.default_rng(self.seed))
        return self

    def score(self, users):
        return self.U[users] @ self.V.T


def make_model(name, factors, seed):
    return {
        "popular": lambda: Popular(),
        "content": lambda: Content(),
        "svd": lambda: SVDModel(factors=factors, seed=seed),
        "als": lambda: ImplicitModel("als", factors=factors, seed=seed),
        "bpr": lambda: ImplicitModel("bpr", factors=factors, seed=seed),
    }[name]()
