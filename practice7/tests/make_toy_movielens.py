"""ТОЛЬКО для проверки, что пайплайн запускается. Синтетика: метрики на ней НЕ годятся для отчёта."""
import sys
from pathlib import Path
import numpy as np, pandas as pd

out = Path(sys.argv[1]); out.mkdir(parents=True, exist_ok=True)
rng = np.random.default_rng(0)
G = ["Action", "Comedy", "Drama", "Sci-Fi", "Romance", "Horror"]
nu, ni = 400, 600
ig = rng.integers(0, len(G), ni); ug = rng.integers(0, len(G), nu)
pop = rng.zipf(1.6, ni).clip(max=50).astype(float); pop /= pop.sum()
rows = []
for u in range(nu):
    n = int(rng.integers(15, 80))
    w = pop * np.where(ig == ug[u], 6, 1); w /= w.sum()
    items = rng.choice(ni, n, replace=False, p=w)
    for t, i in enumerate(items):
        r = np.clip(np.round(3 + 1.5 * (ig[i] == ug[u]) + rng.normal(0, .7)), 1, 5)
        rows.append((u + 1, i + 1, r, 1_000_000 + u * 10 + t))
pd.DataFrame(rows, columns=["userId", "movieId", "rating", "timestamp"]).to_csv(out / "ratings.csv", index=False)
pd.DataFrame({"movieId": np.arange(1, ni + 1), "title": [f"Movie {i} ({1990 + i % 30})" for i in range(ni)],
              "genres": [G[g] + ("|" + G[(g + 1) % 6] if i % 3 == 0 else "") for i, g in enumerate(ig)]}
             ).to_csv(out / "movies.csv", index=False)
