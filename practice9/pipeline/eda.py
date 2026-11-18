from __future__ import annotations

import json
from pathlib import Path

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


def run_eda(ds, out: Path):
    df = ds.inter
    per_user = np.bincount(df["user"], minlength=ds.n_users)
    per_item = np.bincount(df["item"], minlength=ds.n_items)
    srt = np.sort(per_item)[::-1]
    stats = {
        "dataset": ds.name, "n_users": ds.n_users, "n_items": ds.n_items, "n_interactions": int(len(df)),
        "sparsity": 1 - len(df) / (ds.n_users * ds.n_items),
        "density_pct": 100 * len(df) / (ds.n_users * ds.n_items),
        "interactions_per_user": {"min": int(per_user.min()), "median": float(np.median(per_user)),
                                  "mean": float(per_user.mean()), "max": int(per_user.max())},
        "interactions_per_item": {"min": int(per_item.min()), "median": float(np.median(per_item)),
                                  "mean": float(per_item.mean()), "max": int(per_item.max())},
        "share_of_interactions_in_top1pct_items": float(srt[:max(1, ds.n_items // 100)].sum() / srt.sum()),
        "items_with_empty_text_pct": float((ds.items["text"].str.strip() == "").mean() * 100),
        "explicit": ds.explicit, "has_time": ds.has_time,
    }
    (out / "eda.json").write_text(json.dumps(stats, ensure_ascii=False, indent=2))

    fig, ax = plt.subplots(1, 3, figsize=(15, 4))
    if ds.explicit:
        vals, cnts = np.unique(df["rating"], return_counts=True)
        ax[0].bar(vals.astype(str), cnts); ax[0].set_title("Распределение оценок")
    else:
        ax[0].hist(np.log10(df["rating"] + 1), bins=40); ax[0].set_title("log10(число прослушиваний+1)")
    ax[1].hist(per_user, bins=np.logspace(0, np.log10(per_user.max() + 1), 40)); ax[1].set_xscale("log")
    ax[1].set_title("Активность пользователей"); ax[1].set_xlabel("взаимодействий на пользователя")
    ax[2].plot(np.arange(1, len(srt) + 1), srt); ax[2].set_xscale("log"); ax[2].set_yscale("log")
    ax[2].set_title("Популярность объектов (долгий хвост)"); ax[2].set_xlabel("ранг объекта")
    fig.tight_layout(); fig.savefig(out / "eda.png", dpi=130); plt.close(fig)
    return stats


def coverage_plot(rows, out: Path, k):
    names = [r[0] for r in rows]; vals = [r[1] for r in rows]
    fig, ax = plt.subplots(figsize=(6, 3.5))
    ax.bar(names, vals); ax.set_title(f"Покрытие каталога @{k}"); ax.set_ylabel("доля каталога")
    plt.xticks(rotation=30, ha="right"); fig.tight_layout(); fig.savefig(out / "coverage.png", dpi=130); plt.close(fig)
