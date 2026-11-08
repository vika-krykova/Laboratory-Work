from __future__ import annotations

import gzip
import json
import re
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd


@dataclass
class Dataset:
    name: str
    inter: pd.DataFrame 
    items: pd.DataFrame 
    explicit: bool
    user_raw: np.ndarray  
    item_raw: np.ndarray    
    has_time: bool

    @property
    def n_users(self):
        return len(self.user_raw)

    @property
    def n_items(self):
        return len(self.item_raw)


def _kcore(df, min_u, min_i):
    while True:
        n0 = len(df)
        df = df[df.groupby("user_raw")["user_raw"].transform("size") >= min_u]
        df = df[df.groupby("item_raw")["item_raw"].transform("size") >= min_i]
        if len(df) == n0:
            return df


def _finalize(name, df, items_raw, explicit, min_u, min_i):
    df = df.sort_values(["user_raw", "item_raw", "ts"], kind="stable")
    df = df.drop_duplicates(["user_raw", "item_raw"], keep="last")  
    df = _kcore(df, min_u, min_i)
    users = np.sort(df["user_raw"].unique())
    items = np.sort(df["item_raw"].unique())
    df = df.assign(user=np.searchsorted(users, df["user_raw"]),
                   item=np.searchsorted(items, df["item_raw"]))
    it = items_raw.reindex(items)
    it["title"] = it["title"].fillna("").astype(str)
    it["text"] = it["text"].fillna("").astype(str)
    it["category"] = it["category"].fillna("").astype(str)
    it = it.reset_index(drop=True)
    inter = df[["user", "item", "rating", "ts"]].reset_index(drop=True)
    return Dataset(name, inter, it, explicit, users, items, bool(inter["ts"].notna().all()))


def _open(path):
    path = str(path)
    return gzip.open(path, "rt", encoding="utf-8") if path.endswith(".gz") else open(path, encoding="utf-8")


def load_movielens(path, min_u=5, min_i=5):
    p = Path(path)
    if (p / "ratings.csv").exists():  
        r = pd.read_csv(p / "ratings.csv").rename(columns={"userId": "user_raw", "movieId": "item_raw", "timestamp": "ts"})
        m = pd.read_csv(p / "movies.csv").rename(columns={"movieId": "item_raw"})
        tags = pd.read_csv(p / "tags.csv") if (p / "tags.csv").exists() else None
        if tags is not None:
            tags = tags.groupby("movieId")["tag"].apply(lambda s: " ".join(s.astype(str).str.lower()))
    else:   
        r = pd.read_csv(p / "ratings.dat", sep="::", engine="python",
                        names=["user_raw", "item_raw", "rating", "ts"])
        m = pd.read_csv(p / "movies.dat", sep="::", engine="python", encoding="latin-1",
                        names=["item_raw", "title", "genres"])
        tags = None
    m = m.set_index("item_raw")
    genres = m["genres"].replace("(no genres listed)", "")
    clean_title = m["title"].str.replace(r"\(\d{4}\)", "", regex=True)
    text = clean_title + " " + genres.str.replace("|", " ", regex=False)
    if tags is not None:
        text = text + " " + tags.reindex(m.index).fillna("")
    items = pd.DataFrame({"title": m["title"], "text": text, "category": genres})
    r = r.assign(rating=r["rating"].astype(float), ts=r["ts"].astype(float))
    return _finalize("movielens", r[["user_raw", "item_raw", "rating", "ts"]], items, True, min_u, min_i)


def load_lastfm(path, min_u=5, min_i=5):
    p = Path(path)
    ua = pd.read_csv(p / "user_artists.dat", sep="\t").rename(
        columns={"userID": "user_raw", "artistID": "item_raw", "weight": "rating"})
    ua = ua.assign(rating=ua["rating"].astype(float), ts=np.nan) 
    art = pd.read_csv(p / "artists.dat", sep="\t", quoting=3, on_bad_lines="skip").rename(
        columns={"id": "item_raw", "name": "title"}).set_index("item_raw")
    tags = pd.read_csv(p / "tags.dat", sep="\t", encoding="latin-1").set_index("tagID")["tagValue"]
    uta = pd.read_csv(p / "user_taggedartists.dat", sep="\t")
    cnt = uta.groupby(["artistID", "tagID"]).size().reset_index(name="n")
    cnt["tag"] = cnt["tagID"].map(tags).astype(str).str.replace(r"\s+", "_", regex=True)
    text = cnt.groupby("artistID").apply(lambda g: " ".join(np.repeat(g["tag"].values, g["n"].clip(upper=5).values)),
                                         include_groups=False)
    top = cnt.sort_values(["artistID", "n", "tag"], ascending=[True, False, True]).groupby("artistID")["tag"].apply(
        lambda s: "|".join(s.head(3)))
    items = pd.DataFrame({"title": art["title"], "text": text.reindex(art.index).fillna(""),
                          "category": top.reindex(art.index).fillna("")})
    return _finalize("lastfm", ua[["user_raw", "item_raw", "rating", "ts"]], items, False, min_u, min_i)


def _first(d, *keys):
    for k in keys:
        if k in d and d[k] is not None:
            return d[k]
    return None


def load_amazon(path, meta=None, min_u=5, min_i=5, max_rows=None):
    rows, texts = [], {}
    with _open(path) as f:
        for n, line in enumerate(f):
            if max_rows and n >= max_rows:
                break
            d = json.loads(line)
            u, i = _first(d, "reviewerID", "user_id"), _first(d, "asin", "parent_asin")
            rt = _first(d, "overall", "rating")
            if u is None or i is None or rt is None:
                continue
            ts = _first(d, "unixReviewTime", "timestamp")
            ts = float(ts) / 1000 if ts and ts > 1e11 else float(ts or np.nan)
            rows.append((u, i, float(rt), ts))
            t = ((_first(d, "summary", "title") or "") + " " + (_first(d, "reviewText", "text") or ""))[:1500]
            texts.setdefault(i, []).append(t)
    df = pd.DataFrame(rows, columns=["user_raw", "item_raw", "rating", "ts"])
    items = pd.DataFrame({"title": "", "text": pd.Series({i: " ".join(v[:5]) for i, v in texts.items()}),
                          "category": ""})
    items.index.name = "item_raw"
    items["title"] = ""
    if meta:
        mt, mc = {}, {}
        with _open(meta) as f:
            for line in f:
                d = json.loads(line)
                i = _first(d, "asin", "parent_asin")
                if i not in items.index:
                    continue
                desc = _first(d, "description") or []
                desc = " ".join(desc) if isinstance(desc, list) else str(desc)
                mt[i] = str(_first(d, "title") or "")
                cats = _first(d, "category", "categories") or []
                mc[i] = "|".join(str(c) for c in cats[:3]) if isinstance(cats, list) else str(cats)
                items.loc[i, "text"] = mt[i] + " " + desc + " " + items.loc[i, "text"]
        items["title"] = pd.Series(mt).reindex(items.index).fillna("")
        items["category"] = pd.Series(mc).reindex(items.index).fillna("")
    return _finalize("amazon", df, items, True, min_u, min_i)


def load_dataset(name, path, meta=None, min_u=5, min_i=5, max_rows=None):
    if name == "movielens":
        return load_movielens(path, min_u, min_i)
    if name == "lastfm":
        return load_lastfm(path, min_u, min_i)
    if name == "amazon":
        return load_amazon(path, meta, min_u, min_i, max_rows)
    raise ValueError(name)


def split(ds: Dataset, n_test=5, min_hist=10, seed=42):
    df = ds.inter.sort_values(["user", "item"], kind="stable").reset_index(drop=True) 
    key = df["ts"].values if ds.has_time else np.random.default_rng(seed).random(len(df))
    pos = pd.Series(key).groupby(df["user"].values).rank(method="first", ascending=False).values - 1
    size = df.groupby("user")["user"].transform("size").values
    is_test = (pos < n_test) & (size >= min_hist)
    return df[~is_test].reset_index(drop=True), df[is_test].reset_index(drop=True)
