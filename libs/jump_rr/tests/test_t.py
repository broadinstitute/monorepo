"""Test the t value calculation."""

import dask.array as da
import numpy as np
import polars as pl
from scipy.stats import ttest_ind

from jump_rr.significance import (
    correct_multitest_threaded,
    get_metrics_for_ttest,
    pvals_from_profile,
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

    # Test t-statistic calculation.
    tstats = da.array(t_from_metrics(metrics)).compute()
    tstat = tstats[0].flatten()
    assert all(np.isclose(t, gt.statistic) for t, gt in zip(tstat, tpvals_scipy))

    # Test corrected p-value calculation.
    corrected_pvalue = pvals_from_profile(test_df).compute()
    # Correct scipy p values
    corrected_pvals_scipy = correct_multitest_threaded(
        [[gt.pvalue for gt in tpvals_scipy]]
    )
    assert all(
        np.isclose(p, p_gt[0])
        for p, p_gt in zip(corrected_pvalue, corrected_pvals_scipy)
    )
