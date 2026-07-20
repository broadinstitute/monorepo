#!/usr/bin/env jupyter
"""Generate feature rankings for the profile used by the JUMP production paper."""

from pathlib import Path
from time import perf_counter

import dask.array as da
import duckdb
import numpy as np
import polars as pl

from jump_rr.consensus import add_sample_images, get_consensus_meta_urls, get_range
from jump_rr.datasets import get_dataset
from jump_rr.formatters import add_external_sites
from jump_rr.index_selection import get_ranks_per_feature, get_ranks_per_perturbation
from jump_rr.mappers import (
    get_compound_mappers,
    get_external_mappers,
    get_synonym_mapper,
)
from jump_rr.parse_features import get_feature_groups
from jump_rr.production_support import (
    add_production_activity,
    rename_production_features,
    write_production_metadata,
)
from jump_rr.significance import add_pert_type, statistics_from_profile

output_dir = Path("./databases")
dataset = "compound_no_source7"
dataset_type = "compound"
n_features_per_compound = 10
n_compounds_per_feature = 50
feature_decomposition = ("Compartment", "Feature", "Channel", "Suffix")

jcp_short = "JCP2022"
jcp_col = "Metadata_JCP2022"
std_outname = "Perturbation"
img_col = f"{std_outname} example image"
ext_links_col = "Resources"
value_col = "Median"
significance_col = "Feature significance"
feature_rank_col = "Feature Rank"
perturbation_rank_col = "Perturbation Rank"
effect_col = "Cohen's d"
abs_effect_col = "|Cohen's d|"
activity_cols = {
    "corrected_p_value": "Corrected p-value",
    "mean_average_precision": "Phenotypic activity",
}
ndecimals = 5
unranked_sentinel = 99999  # Datasette sorts nulls first.

print(f"Processing features for {dataset}")
t0 = perf_counter()
profile = rename_production_features(pl.read_parquet(get_dataset(dataset)))
profile = add_pert_type(profile, dataset=dataset_type)
feature_significance, cohens_d = statistics_from_profile(profile)

consensus, _ = get_consensus_meta_urls(
    profile.filter(pl.col("Metadata_pert_type") != "negcon"), jcp_col
)
consensus = consensus.sort(jcp_col)
median_values = consensus.select(pl.exclude("^Metadata.*$")).to_numpy()

per_perturbation = get_ranks_per_perturbation(
    feature_significance, n_features_per_compound
)
perturbation_indices = da.vstack(
    (
        da.indices((len(per_perturbation), n_features_per_compound)).reshape((2, -1)),
        per_perturbation.flatten(),
    )
).compute()

per_feature = get_ranks_per_feature(da.abs(cohens_d), n_compounds_per_feature)
feature_indices = da.vstack(
    (
        da.indices((per_feature.shape[1], n_compounds_per_feature)).reshape((2, -1)),
        per_feature.T.flatten(),
    )
).compute()

with duckdb.connect() as connection:
    selected = connection.execute(
        "SELECT x,y,"
        "any_value(rankf) AS rankf,"
        "any_value(rankg) AS rankg"
        " FROM (SELECT * FROM"
        " (SELECT column0 as x,column1 as rankf,column2 as y"
        " FROM perturbation_indices)"
        " UNION ALL BY NAME"
        " (SELECT column0 AS y,column1 AS rankg, column2 AS x"
        " FROM feature_indices))"
        " GROUP By x,y"
        " ORDER BY y,x,rankf"
    ).fetchnumpy()

xs = selected["x"]
ys = selected["y"]
feature_ranks = selected["rankf"].filled(unranked_sentinel)
perturbation_ranks = selected["rankg"].filled(unranked_sentinel)

decomposed_features = get_feature_groups(
    tuple(consensus.select(pl.exclude("^Metadata.*$")).columns),
    feature_decomposition,
)
significance_values = da.around(feature_significance, ndecimals).compute()
effect_values = np.around(cohens_d.compute(), 3)

result = pl.DataFrame(
    {
        **{
            key: value
            for key, value in zip(
                decomposed_features.columns,
                decomposed_features.to_numpy()[ys].T,
            )
        },
        significance_col: significance_values[xs, ys],
        effect_col: effect_values[xs, ys],
        abs_effect_col: abs(effect_values[xs, ys]),
        value_col: np.around(median_values[xs, ys].astype(np.float64), 3),
        jcp_short: consensus[jcp_col][xs],
        perturbation_rank_col: perturbation_ranks,
        feature_rank_col: feature_ranks,
    }
)

result = add_sample_images(
    result,
    profile.select("^Metadata.*$"),
    get_range(dataset_type),
    img_col,
    left_col=jcp_short,
    right_col=jcp_col,
)
jcp_to_std, jcp_to_entrez, _, _ = get_external_mappers(profile, jcp_col, dataset_type)
result = add_production_activity(
    result,
    left_on=jcp_short,
    right_on=jcp_col,
    columns=activity_cols,
)
result = result.with_columns(
    pl.col(jcp_short).replace(jcp_to_std).alias(std_outname),
    pl.col(jcp_short)
    .replace(jcp_to_entrez)
    .replace(get_synonym_mapper())
    .alias("Synonyms"),
)
compound_resources = [
    (key, jcp_short, mapper) for key, mapper in get_compound_mappers()
]
result = add_external_sites(result, ext_links_col, compound_resources)

order = (
    *decomposed_features.columns,
    significance_col,
    effect_col,
    abs_effect_col,
    std_outname,
    *activity_cols.values(),
    img_col,
    value_col,
    perturbation_rank_col,
    feature_rank_col,
    jcp_short,
    ext_links_col,
    "Synonyms",
)
final = result.select(order)

output_dir.mkdir(parents=True, exist_ok=True)
final.write_parquet(output_dir / f"{dataset}_features.parquet", compression="zstd")
write_production_metadata("feature", final.columns)
print(f"Processed {dataset} features in {perf_counter() - t0:.2f} seconds")
