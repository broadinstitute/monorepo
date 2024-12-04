import numpy as np
import polars as pl
import polars.selectors as cs

from trommel.core import basic_cleanup


def generate_random_dataset(nrows: int = 100, ncols: int = 2000, nmeta: int = 2):
    rng = np.random.default_rng(12345)

    rints = rng.integers(low=0, high=10000, size=nrows * ncols).reshape(nrows, ncols)

    df = pl.DataFrame(rints, schema=[f"X_{i}" for i in range(ncols)])
    df_meta = df.with_columns(
        [pl.lit(f"Meta_{i}").alias(f"Meta_{i}") for i in range(nmeta)]
    )

    return df_meta


def test_basic_cleanup():
    """
    Test that the basic cleanup works fine
    """
    data = generate_random_dataset()

    result = basic_cleanup(data, cs.by_dtype(pl.String))

    # Make sure the processed data is smaller
    assert len(result) and result.shape[1]<data.shape[1]
