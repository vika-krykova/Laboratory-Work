import numpy as np
from sklearn.metrics import ndcg_score

from recsys_lib.metrics import ranking_metrics, coverage


def test_known_example():
    hits = np.array([[1, 0, 1]], dtype=bool)      
    m = ranking_metrics(hits, [2], 3)
    assert np.isclose(m["precision"][0], 2 / 3)
    assert np.isclose(m["recall"][0], 1.0)
    assert np.isclose(m["map"][0], (1 + 2 / 3) / 2)
    assert np.isclose(m["ndcg"][0], (1 + 0.5) / (1 + 1 / np.log2(3)))


def test_ndcg_matches_sklearn():
    hits = np.array([[0, 1, 0, 1, 0]], dtype=bool)
    ours = ranking_metrics(hits, [2], 5)["ndcg"][0]
    true = np.array([[0, 1, 0, 1, 0]]); score = np.array([[5, 4, 3, 2, 1]])
    assert np.isclose(ours, ndcg_score(true, score))


def test_perfect_and_empty():
    assert np.isclose(ranking_metrics(np.ones((1, 3), bool), [3], 3)["ndcg"][0], 1.0)
    assert ranking_metrics(np.zeros((1, 3), bool), [3], 3)["map"][0] == 0


def test_coverage():
    assert coverage(np.array([[0, 1], [1, 2]]), 10) == 0.3
