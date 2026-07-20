#!/usr/bin/env jupyter
"""Generate compound matches for the profile used by the JUMP production paper."""

from pathlib import Path
from time import perf_counter

import dask.array as da
import numpy as np
import polars as pl
import polars.selectors as cs

from jump_rr.consensus import add_sample_images, get_consensus_meta_urls, get_range
from jump_rr.datasets import get_dataset
from jump_rr.formatters import add_external_sites
from jump_rr.index_selection import get_bottom_top_indices
from jump_rr.mappers import (
    get_compound_mappers,
    get_external_mappers,
    get_synonym_mapper,
)
from jump_rr.production_support import (
    add_production_activity,
    write_production_metadata,
)


def pairwise_cosine_sim(x: da.Array, y: da.Array) -> da.Array:
    """Compute pairwise cosine similarity between two sets of vectors."""
    x_norm = x / da.linalg.norm(x, axis=1)[:, da.newaxis]
    y_norm = y / da.linalg.norm(y, axis=1)[:, da.newaxis]
    return da.matmul(x_norm, y_norm.T)


output_dir = Path("./databases")
dataset = "compound_no_source7"
dataset_type = "compound"
n_vals_used = 10

jcp_short = "JCP2022"
jcp_col = "Metadata_JCP2022"
std_outname = "Perturbation"
img_col = f"{std_outname} example image"
match_col = "Match"
match_jcp_col = f"{match_col} {jcp_short}"
match_img_col = f"{match_col} example image"
dist_col = "Perturbation-Match Similarity"
ext_links_col = f"{match_col} resources"
activity_cols = {
    "corrected_p_value": "Corrected p-value",
    "mean_average_precision": "Phenotypic activity",
}

print(f"Processing {dataset}")
t0 = perf_counter()
profile = pl.read_parquet(get_dataset(dataset))
consensus, _ = get_consensus_meta_urls(profile, jcp_col)
values = da.array(consensus.select(cs.by_dtype(pl.Float32)).to_numpy())
cosine_sim = pairwise_cosine_sim(values, values)

cosine_sim_computed = cosine_sim.compute()
xs, ys = get_bottom_top_indices(cosine_sim, n_vals_used, skip_first=True)
jcp_ids = consensus[jcp_col].to_numpy().astype("<U15")

matches = pl.DataFrame(
    {
        jcp_short: np.repeat(jcp_ids, n_vals_used * 2),
        match_jcp_col: jcp_ids[ys].astype("<U15"),
        dist_col: cosine_sim_computed[xs, ys],
    }
)

profile_metadata = profile.select("^Metadata.*$")
query_images = add_sample_images(
    matches,
    profile_metadata,
    get_range(dataset_type),
    img_col,
    left_col=jcp_short,
    right_col=jcp_col,
)
match_images = add_sample_images(
    matches,
    profile_metadata,
    get_range(dataset_type),
    match_img_col,
    left_col=match_jcp_col,
    right_col=jcp_col,
)
jcp_cols = (jcp_short, match_jcp_col)
matches = matches.join(
    query_images.select(pl.col((*jcp_cols, img_col))), on=jcp_cols
).join(match_images.select(pl.col((*jcp_cols, match_img_col))), on=jcp_cols)

jcp_to_std, jcp_to_entrez, _, _ = get_external_mappers(profile, jcp_col, dataset_type)
matches = matches.with_columns(
    pl.col(jcp_short).replace(jcp_to_std).alias(std_outname),
    pl.col(match_jcp_col).replace(jcp_to_std).alias(match_col),
    pl.col(jcp_short)
    .replace(jcp_to_entrez)
    .replace(get_synonym_mapper())
    .alias("Synonyms"),
)
matches = add_production_activity(
    matches,
    left_on=jcp_short,
    right_on=jcp_col,
    columns=activity_cols,
)
matches = add_production_activity(
    matches,
    left_on=match_jcp_col,
    right_on=jcp_col,
    columns=activity_cols,
    suffix=" Match",
)

compound_resources = [
    (key, match_jcp_col, mapper) for key, mapper in get_compound_mappers()
]
matches = add_external_sites(matches, ext_links_col, compound_resources)

order = (
    std_outname,
    match_col,
    img_col,
    match_img_col,
    dist_col,
    ext_links_col,
    "Synonyms",
    jcp_short,
    match_jcp_col,
    *[
        f"{name}{suffix}"
        for suffix in ("", " Match")
        for name in activity_cols.values()
    ],
)
final = matches.with_columns(pl.col(dist_col).cast(pl.Float64).round(3)).select(order)

output_dir.mkdir(parents=True, exist_ok=True)
final.write_parquet(output_dir / f"{dataset}.parquet", compression="zstd")
write_production_metadata("matches", final.columns)
print(f"Matched pairwise {dataset} in {perf_counter() - t0:.2f} seconds")
