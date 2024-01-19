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
Calculate cosine similarity of the CRISPR profiles using GPU,
then wrangle information and produce an explorable data frame.

This is used on a server with GPUs and high RAM to analyse data massively.
"""
from itertools import cycle
from pathlib import Path

import cupy as cp
import cupyx.scipy.spatial as spatial
import numpy as np
import polars as pl
from broad_babel.query import run_query
from utils import batch_processing, parallel

assert cp.cuda.get_current_stream().done, "GPU not available"


def get_first_last_n(arr: cp.ndarray, n: int):
    # return tensor[:, [range(n), range(-n - 1, -1)]].reshape(-1, 2 * n)
    return arr[:, [range(n), range(-n - 1, -1)]].reshape(-1, 2 * n)


@batch_processing
def jcp_to_standard(x):
    return run_query(query=x, input_column="JCP2022", output_column="standard_key")[0][
        0
    ]


@batch_processing
def jcp_to_ncbi(x):
    return run_query(query=x, input_column="JCP2022", output_column="NCBI_Gene_ID")[0][
        0
    ]


# %%


dir_path = Path("/dgx1nas1/storage/data/shared/morphmap_profiles/crispr")
filename = "harmonized_no_sphering_profiles"
profiles_path = dir_path / f"{filename}.parquet"
checkpoint_path = Path("jcp_df.parquet")

# %% Set names
jcp_col = "Metadata_JCP2022"  # Name of columns in input data frames
url_col = "Metadata_image"  # Must start with "Metadata"
match_jcp_col = "Match"
match_url_col = "Match Example"
std_outname = "Gene/Compound"
ext_links_col = "Match resources"
ncbi_formatter = '{{"href": "https://www.ncbi.nlm.nih.gov/gene/{}", "label":"NCBI"}}'
url_template = (
    '"https://phenaid.ardigen.com/static-jumpcpexplorer/' 'images/{}_{{}}.jpg"'
)
img_formatter = '{{"img_src": {}, "href": {}, "width": 200}}'
n_vals_used = 25


# %% Load Metadata
df = pl.read_parquet(profiles_path)

# %% add build url from individual wells
df = df.with_columns(
    pl.concat_str(
        pl.col("Metadata_Source"),
        pl.col("Metadata_Plate"),
        pl.col("Metadata_Well"),
        separator="/",
    )
    .map_elements(lambda x: url_template.format(x))
    .alias(url_col)
)
grouped = df.group_by("Metadata_JCP2022")
med = grouped.median()
meta = grouped.agg(pl.col("^Metadata_.*$").map_elements(cycle))

urls = grouped.agg(pl.col(url_col).map_elements(cycle))

for srs in meta.iter_columns():
    med.replace_column(med.columns.index(srs.name), srs)

# vals = Tensor(med.select(pl.all().exclude("^Metadata.*$")).to_numpy())
vals = cp.array(med.select(pl.all().exclude("^Metadata.*$")))

# %%

# Calculate cosine similarty
cosine_sim = spatial.distance.cdist(vals, vals, metric="cosine")
# Sort by correlation

# Get most correlated and anticorrelated indices and values
mask = cp.ones(len(_sorted), dtype=bool)
mask[n_vals_used : -n_vals_used - 1] = False
mask[0] = False
indices = cosine_sim.argsort(axis=1)[:, mask].get()
values = cosine_sim[cp.indices(indices.shape)[0], indices].get()

## Build a dataframe containing matches
jcp_ids = urls.select(pl.col(jcp_col)).to_series().to_numpy().astype("<U15")
moving_idx = np.repeat(cycle(range(9)), len(vals))
urls_vals = urls.get_column(url_col).to_numpy()

jcp_df = pl.DataFrame(
    {
        "JCP2022": np.repeat(jcp_ids, n_vals_used * 2),
        match_jcp_col: jcp_ids[indices.flatten()].astype("<U15"),
        "Similarity": values.flatten(),
        url_col: [
            img_formatter.format(img_src, img_src)
            for x in urls.get_column(url_col).to_numpy()
            for j in range(n_vals_used * 2)
            if (img_src := next(x).format(j % 9))
        ],
        match_url_col: [
            img_formatter.format(img_src, img_src)
            for url, idx in zip(
                urls_vals[indices.flatten()], moving_idx[indices.flatten()]
            )
            if (img_src := next(url).format(next(idx)))
        ],
    }
)

jcp_df.write_parquet(checkpoint_path, compression="zstd")


# %% And then proceed to add gene names

uniq_jcp = jcp_df.select(pl.col("JCP2022")).to_series().unique().to_list()
mapper_values = parallel(uniq_jcp, jcp_to_standard)
mapper = {jcp: std for jcp, std in zip(uniq_jcp, mapper_values)}

ncbi_mapper_values = parallel(uniq_jcp, jcp_to_ncbi)
ncbi_mapper = {
    jcp: ncbi_formatter.format(idx) for jcp, idx in zip(uniq_jcp, ncbi_mapper_values)
}

jcp_translated = jcp_df.with_columns(
    pl.col("JCP2022").replace(mapper).alias(std_outname),
    pl.col(match_jcp_col).replace(mapper),
    pl.col(match_jcp_col).replace(ncbi_mapper).alias(ext_links_col),
)


matches = jcp_translated.with_columns(
    (pl.col("Similarity") * 1000).cast(pl.Int16)
).rename({url_col: f"{std_outname} Example"})

order = [
    std_outname,
    "Match",
    "Gene/Compound Example",
    match_url_col,
    "Similarity",
    ext_links_col,
    "JCP2022",
]
matches_translated = matches.select(order)

final_output = "crispr.parquet"
matches_translated.write_parquet(final_output, compression="zstd")


"""

# %% Upload to Zenodo
# Automated uploads are not working
# https://github.com/zenodo/zenodo/issues/2506

from os.path import expanduser
import requests
with open(expanduser("~") + "/.zenodo") as f:
    for line in f.readlines():
        name, access_token = line.strip("\n").split(": ")

params = {"access_token": access_token}
bucket_url = "https://zenodo.org/api/files/9ffb1b5b-1e3c-4618-ad91-36255e87b57e"
headers = {"Content-Type": "application/json"}
with open(final_output, "rb") as fp:
    r = requests.post(
        f"{bucket_url}?access_token={params['access_token']}",
        data=fp,
        headers=headers,
        params=params,
    )


depos_url =  "https://zenodo.org/api/deposit/depositions/10416605"
depos=requests.get(depos_url,params=params)
new = requests.post(depos.json()["links"]["newversion"], params=params, headers={"Accept": "application/json" ,**headers})

d = r.post(depos_url.json(""))
curl -X POST-H "Accept: application/json" -H "Content-Type: application/json" -H "Authorization: Bearer <TOKEN>" https://sandbox.zenodo.org/api/deposit/depositions/165/actions/newversion

"""

"""
Future plans:
- TODO Incorporate NCBI ids (already added on broad-babel)
- TODO add differentiating features when compared to their controls
- TODO add Average precision metrics
"""
