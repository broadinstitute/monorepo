"""Test the t value calculation."""

import numpy as np
import polars as pl
from scipy.stats import ttest_ind

from jump_rr.significance import (
    correct_multitest_threaded,
    get_metrics_for_ttest,
    statistics_from_profile,
    t_from_metrics,
)


def test_pvalue() -> None:
    """Test t-statistic and corrected p-value calculation."""
    vals = [
        [[1, 2, 3, 4], [5, 6, 7, 9, 0]],
        [[1, 4, 7, 9], [5, 3, 2]],
    ]

    ids_trt = list(
        zip(
            *[
                (
                    ("trt", "negcon")[j],
                    "control" if j else ("a", "b")[i],
                    f"plate{i}",
                    v,
                )
                for i, pairs in enumerate(vals)
                for j, vals in enumerate(pairs)
                for v in vals
            ]
        )
    )

    test_df = pl.from_dict(
        {
            (
                "Metadata_pert_type",
                "Metadata_JCP2022",
                "Metadata_Plate",
                "feature1",
                "feature2",
            )[i]: v
            for i, v in enumerate(ids_trt)
        }
    )
    tpvals_scipy = [ttest_ind(x, y, alternative="two-sided") for x, y in vals]
    metrics = get_metrics_for_ttest(test_df)

    # Test t-statistic and Cohen's d calculation.
    t_, _, d_ = t_from_metrics(metrics)
    tstat = t_.flatten()
    assert all(np.isclose(t, gt.statistic) for t, gt in zip(tstat, tpvals_scipy))

    # Test Cohen's d: (mean_trt - mean_ctrl) / sqrt(pooled_variance)
    cohens_d = d_.flatten()
    for d, (trt, ctrl) in zip(cohens_d, vals):
        trt, ctrl = np.array(trt, dtype=float), np.array(ctrl, dtype=float)
        n1, n2 = len(trt), len(ctrl)
        df = n1 + n2 - 2
        sv = ((n1 - 1) * np.var(trt, ddof=1) + (n2 - 1) * np.var(ctrl, ddof=1)) / df
        expected_d = (np.mean(trt) - np.mean(ctrl)) / np.sqrt(sv)
        assert np.isclose(d, expected_d)

    # Test corrected p-value calculation.
    corrected_pvalue, _ = statistics_from_profile(test_df)
    corrected_pvalue = corrected_pvalue.compute()
    # Correct scipy p values
    corrected_pvals_scipy = correct_multitest_threaded(
        [[gt.pvalue for gt in tpvals_scipy]]
    )
    assert all(
        np.isclose(p, p_gt[0])
        for p, p_gt in zip(corrected_pvalue, corrected_pvals_scipy)
    )
