import numpy as np

from backend.pipeline.phase4_statistics_output.step20_robust_stats_deviation_score import robust_z_scores
from backend.pipeline.phase4_statistics_output.step21_outlier_thresholding import compute_threshold


def test_statistics_and_threshold_contracts():
    scores, median, mad = robust_z_scores(np.array([2.0]), np.array([[1.0], [1.0], [1.0]]))
    assert scores.shape == median.shape == mad.shape == (1,)
    assert scores[0] == 0.0
    assert compute_threshold("summed_z", 14) == 3.0
    assert compute_threshold("mahalanobis", 14) > 0.0
