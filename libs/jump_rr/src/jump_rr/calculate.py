#!/usr/bin/env jupyter

# ---
# jupyter:
#   jupytext:
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.15.2
#   kernelspec:
#     display_name: Python 3
#     language: python
#     name: python3
# ---

"""
Calculate cosine distance of CRISPR and ORF profiles using a GPU,
then wrangle information and produce an explorable data frame.

This is intended for use on a server with GPUs and high RAM to analyse data massively.
"""
from itertools import cycle
from pathlib import Path

import cupy as cp
import cupyx.scipy.spatial as spatial
import numpy as np
import polars as pl
from broad_babel.query import run_query
from jump_rr.concensus import get_concensus_meta_urls

assert cp.cuda.get_current_stream().done, "GPU not available"

# %% Setup
## Paths
dir_path = Path("/dgx1nas1/storage/data/shared/morphmap_profiles/")
datasets_filenames = (
    ("crispr", "harmonized_no_sphering_profiles"),
    ("orf", "transformed_inf_eff_filtered"),
)
output_dir = Path("./databases")

## Parameters
n_vals_used = 25  # Number of top and bottom matches used
dist_as_sim = True  # Display distance as integers instead of floats

## Column names
jcp_short = "JCP2022"  # Shortened input data frame
jcp_col = f"Metadata_{jcp_short}"  # Traditional JUMP metadata colname
url_col = "Metadata_image"  # Must start with "Metadata" for URL grouping to work
match_col = "Match"  # Highest matches
match_url_col = f"{match_col} Example"  # URL with image examples
dist_col = "Similarity"  # Metric name
std_outname = "Gene/Compound"  # Standard item name
ext_links_col = f"{match_col} resources"  # Link to external resources (e.g., NCBI)

# HTML formatters
external_formatter = (
    '{{"href": "https://www.ncbi.nlm.nih.gov/gene/{}", "label":"External"}}'
)
url_template = (
    '"https://phenaid.ardigen.com/static-jumpcpexplorer/' 'images/{}_{{}}.jpg"'
)
img_formatter = '{{"img_src": {}, "href": {}, "width": 200}}'


# precor_file = "full_profiles_cc_adj_mean_corr.parquet"
# precor_path = dir_path / "orf" / precorrection_file
# precor = pl.read_parquet(precorrection_path)
# med, meta, urls  = get_concensus_meta_urls(precor)

# # Group features in a consistent manner
# # apples with apples, oranges with oranges
# # Two cases
# # - Channel-based
# # - Non-channel based shape
# data_only =med.select(pl.all().exclude("^Metadata.*$"))
# cols = data_only.columns

# # regex = re.compile(r"^\([A-za-z]+\)_\(\S+\)_\(DNA|RNA|Mito|ERAGP\)_\(\S+\)$")
# masks = "|".join(("Cells","Nuclei","Cytoplasm","Image"))
# channels = "|".join(("DNA","AGP","RNA","ER","Mito","Image"))
# chless_feats ="|".join(("AreaShape","Neighbors","RadialDistribution","Location","Count","Number","Parent","Children","ObjectSkeleton","Threshold"))

# std = re.compile(f"({masks})_(\S+)_(Orig)?({channels})(_.*)?")
# chless = re.compile(f"({masks})_({chless_feats})_?([a-zA-Z]+)?(.*)?")

# results = [(std.findall(x) or chless.findall(x))[0] for x in cols]
# # Convert to format MASK,FEATURE,CHANNEL(opt),SUFFIX
# results = [(x[0], ''.join(x[1:3]),"" ,x[3]) if len(x)<5 else (*x[:2],''.join(x[2:4]),x[4]) for x in results]

# feature_meta = pl.DataFrame(results, schema=[("Mask",str),("Feature",str),("Channel",str),( "suffix" ,str)])

# features = pl.concat((feature_meta, data_only.transpose()),how="vertical")
# vals = cp.array(med.select(pl.all().exclude("^Metadata.*$")))

# %% Processing starts
for dataset, filename in datasets_filenames:
    profiles_path = dir_path / dataset / f"{filename}.parquet"

    # %% Load Metadata
    df = pl.read_parquet(profiles_path)

    # %% add build url from individual wells
    med, mrys, urls = get_concensus_meta_urls(df)

    vals = cp.array(med.select(pl.all().exclude("^Metadata.*$")))

    # %% Calculate cosine distance
    cosine_sim = spatial.distance.cdist(vals, vals, metric="cosine")

    # Get most correlated and anticorrelated indices and values
    mask = cp.ones(len(cosine_sim), dtype=bool)
    mask[n_vals_used : -n_vals_used - 1] = False
    mask[0] = False
    indices = cosine_sim.argsort(axis=1)[:, mask].get()
    values = cosine_sim[cp.indices(indices.shape)[0], indices].get()

    # Build a dataframe containing matches
    offset = dataset != "crispr"
    cycles = cycle(range(offset, 9 + offset))  # 0-8 if CRISPR; 1-9 if ORF
    jcp_ids = urls.select(pl.col(jcp_col)).to_series().to_numpy().astype("<U15")
    moving_idx = np.repeat(cycles, len(indices))
    url_vals = urls.get_column(url_col).to_numpy()

    jcp_df = pl.DataFrame(
        {
            jcp_short: np.repeat(jcp_ids, n_vals_used * 2),
            match_col: jcp_ids[indices.flatten()].astype("<U15"),
            dist_col: values.flatten(),
            url_col: [  # Secuentially produce multiple images
                img_formatter.format(img_src, img_src)
                for x in url_vals
                for j in range(n_vals_used * 2)
                if (img_src := next(x).format(next(cycles)))
            ],
            match_url_col: [  # Use indices to fetch matches
                img_formatter.format(img_src, img_src)
                for url, idx in zip(
                    url_vals[indices.flatten()], moving_idx[indices.flatten()]
                )
                if (img_src := next(url).format(next(idx)))
            ],
        }
    )

    # %% Add gene name translations
    uniq_jcp = tuple(jcp_df.unique(subset=jcp_short).to_numpy()[:, 0])  # [0]
    mapper_values = run_query(
        query=uniq_jcp,
        input_column=jcp_short,
        output_column=f"{jcp_short},standard_key,NCBI_Gene_ID",
        predicate=f"AND plate_type = '{dataset}'",
    )

    jcp_external_mapper = {}
    jcp_std_mapper = {}
    for jcp, std, external_id in mapper_values:
        jcp_external_mapper[jcp] = external_formatter.format(external_id)
        jcp_std_mapper[jcp] = std

    jcp_translated = jcp_df.with_columns(
        pl.col(jcp_short).replace(jcp_std_mapper).alias(std_outname),
        pl.col(match_col).replace(jcp_std_mapper),
        pl.col(match_col).replace(jcp_external_mapper).alias(ext_links_col),
    )

    if dist_as_sim:
        jcp_translated = jcp_translated.with_columns(
            (1 - pl.col(dist_col)).round(3).alias(dist_col)  # .cast(str)            )
        )

    matches = jcp_translated.rename({url_col: f"{std_outname} Example"})

    # Sort columns
    order = [
        std_outname,
        match_col,
        f"{std_outname} Example",
        match_url_col,
        dist_col,
        ext_links_col,
        jcp_short,
    ]
    matches_translated = matches.select(order)

    # %% Save results
    output_dir.mkdir(parents=True, exist_ok=True)
    final_output = output_dir / f"{dataset}.parquet"
    matches_translated.write_parquet(final_output, compression="zstd")

    # - TODO add Average precision metrics
    # - STOP add differentiating features when compared to their controls
