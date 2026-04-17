# /// script
# requires-python = ">=3.10"
# dependencies = [
#     "marimo",
#     "duckdb>=1.1.3",
#     "pooch>=3.0.0",
#     "broad-babel>=0.1.27",
# ]
# ///

"""Centralized data loading, mapping, formatting, and metadata helpers for the JUMP pipeline."""

import marimo

__generated_with = "0.23.1"
app = marimo.App(width="medium")

with app.setup:
    import json
    from functools import cache
    from pathlib import Path
    from urllib.request import urlopen

    import duckdb
    import marimo as mo  # noqa: F401
    import pooch
    from broad_babel.query import run_query

    SUBSETS = ("crispr", "orf", "compound")
    JCP_COL = "Metadata_JCP2022"
    JCP_SHORT = "JCP2022"
    STD_OUTNAME = "Perturbation"
    REPLICABILITY_COLS = {
        "corrected_p_value": "Corrected p-value",
        "mean_average_precision": "Phenotypic activity",
    }

    MAPPERS = {
        "omim": (
            "https://www.omim.org/static/omim/data/mim2gene.txt",
            "6f82401c77e9c9375a206d7b65f5cdb2d84020d92b784631575749222efd049c",
        ),
        "synonym": (
            "https://ftp.ncbi.nlm.nih.gov/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz",
            "841808c6b72a122af5f3e7ad9cdb19575ed3a14d064694eebe710f2703eef1d0",
        ),
        "compound": (
            "https://zenodo.org/api/records/15644946/files/jcp_to_dbs.parquet/content",
            "04cda85280b512ffde836ec2aa1d9fd7114e9b5cf6f9c395c648b0eaba4497ca",
        ),
    }

    DATASET_MD5S = {
        "compound": "1dd9b76ce9635cc98ea2c6a58f4c1d6ed6aafc1a3990ddcb997162d16582c00f",
        "crispr": "019cd1b767db48dad6fbab5cbc483449a229a44c2193d2341a8d331d067204c8",
        "orf": "32f25ee6fdc4dcfa3349397ddf0e1f6ca2594001b8266c5dc0644fa65944f193",
        "crispr_interpretable": "6153c9182faf0a0a9ba22448dfa5572bd7de9b943007356830304834e81a1d05",
        "orf_interpretable": "ae3fea5445022ebd0535fcbae3cfbbb14263f63ea6243f4bac7e4c384f8d3bbf",
        "compound_interpretable": "42028e8c60692df545e0b1dd087fc9b911f5117c318a8819d768cff251e4edda",
    }

    PROFILE_INDEX_URL = "https://raw.githubusercontent.com/jump-cellpainting/datasets/99b8501e2da16bb01792124df22d23ce7aa93668/manifests/profile_index.json"

    _DESCRIPTIONS = {
        "Channel": "Image channel, which shows the stain for DNA, Mito (mitochondria), RNA, AGP (actin, Golgi, plasma membrane) or ER (Endoplasmic Reticulum).",
        "Resources": "External links that provide further information on the gene or chemical perturbation (e.g., NCBI, ChEMBL).",
        "Feature": "Morphological feature obtained from CellProfiler. This value is the result after data normalization. Its units are the number of median absolute deviations (MAD) from the median.",
        "Perturbation": "Chemical or genetic perturbation. If genetic (overexpression or knock-out) it is the NCBI gene symbol. If it is a chemical perturbation this is the InChiKey. ",
        "Perturbation example image": "Sample image of the perturbation. It cycles over the available images for every occurrence of the perturbation.",
        "JCP2022": "JUMP id. This identifier is unique for any given reagent for a genetic or chemical perturbation across all three datasets (ORF, CRISPR and compounds) and is only repeated for biological replicates.",
        "Compartment": "Mask used to calculate the feature. It can be Nuclei, Cytoplasm or Cells (the union of both Nuclei and Cytoplasm).",
        "Match": "Perturbations with the highest correlation or anti-correlation relative to 'Perturbation'.",
        "Match Example": "Sample image of the matched perturbation. It cycles over the available images.",
        "Match JCP2022": "JUMP id for the matched perturbation. This identifier is unique for any given perturbation across all three datasets (ORF, CRISPR and compounds) and is only repeated for biological replicates.",
        "Match resources": "External links that provide further information on the matched perturbation (e.g., NCBI, ChEMBL).",
        "Median": "Median value of the feature for the perturbation when aggregating all replicates.",
        "Match example image": "Sample image of the perturbation's match. It cycles over the available images for every occurrence of the perturbation.",
        "Perturbation-Match Similarity": "Cosine similarity between the normalized morphological profiles of the two perturbations. Negative values indicate the perturbations' profiles are anti-correlated. Ranges from -1 to 1.",
        "Suffix": "Suffix associated with a CellProfiler feature.",
        "Phenotypic activity": "Mean average precision of the perturbation. It determines its distinctiveness to the negative control. An empty value indicates that the value was discarded due to low infection efficiency.",
        "Feature significance": "Statistical significance of the difference between a morphological feature in a perturbation compared to the control condition. Lower values suggest a stronger effect of the perturbation on that particular feature. The p-value goes through the Benjamini-Hochberg FDR correction",
        "Phenotypic activity Match": "Phenotypic activity of the matched perturbation.",
        "Corrected p-value": "Statistical significance of how distinctive a perturbation is relative to the negative control. It correlates negatively to mean average precision, but adjusted based on its composition of positive and negative values.",
        "Corrected p-value Match": "Corrected p-value of the matched perturbation.",
        "Synonyms": "Other names of the perturbation. If it is a number it indicates that the gene name was not found.",
        "Feature Rank": "The rank of feature significance when compared to all the features for a given perturbation.",
        "Perturbation Rank": "Rank of this perturbation among all perturbations for a given feature, ordered by effect size (1 = strongest effect).",
        "Cohen's d": "Standardized effect size (mean difference / pooled SD). Positive = treatment > control. Sample-size independent, unlike the t-statistic.",
        "|Cohen's d|": "Absolute value of Cohen's d. Sort descending to find the strongest effects regardless of direction.",
        "Source": "Identifier of the partner that produced the data numbered between 1 and 15.",
        "Plate": "Identifier of the plate.",
        "Well": "Identifier of the well. Generally 384-well plates, ranging from A01 to P24.",
        "Site X": "Identifier of the Field of View (FoV). Ranging from 0 to 9 (depending on the dataset).",
    }


# --- datasets ---


@app.function
def get_profiles_url(dataset: str) -> str:
    """Select the correct url from the JUMP manifest."""
    with urlopen(PROFILE_INDEX_URL) as url:
        data = json.load(url)
    for entry in data:
        if entry["subset"] == dataset:
            return entry["url"]


@app.function
def get_dataset(dataset: str, return_pooch: bool = True) -> str:
    """Retrieve the latest morphological profiles using standard names."""
    result = get_profiles_url(dataset)
    if return_pooch:
        result = pooch.retrieve(result, DATASET_MD5S[dataset])
    return result


@app.function
def load_profiles(dset: str) -> duckdb.DuckDBPyRelation:
    """Load morphological profiles for a named JUMP subset."""
    path = get_dataset(dset)
    return duckdb.sql(f"SELECT * FROM read_parquet('{path}')")


@app.function
def load_profiles_lazy(dset: str) -> duckdb.DuckDBPyRelation:
    """Lazy-scan the parquet file for a named JUMP subset."""
    url = get_dataset(dset, return_pooch=False)
    return duckdb.sql(f"SELECT * FROM read_parquet('{url}')")


# --- consensus ---


@app.function
def compute_consensus(
    df: duckdb.DuckDBPyRelation, col: str
) -> tuple[duckdb.DuckDBPyRelation, None]:
    """Compute aggregated median values for a given dataframe."""
    feat_cols = [c for c in df.columns if not c.startswith("Metadata_") and c != col]
    medians = ", ".join(f'MEDIAN("{c}") AS "{c}"' for c in feat_cols)
    med = duckdb.sql(f'SELECT "{col}", {medians} FROM df GROUP BY "{col}"')
    return med, None


@app.function
def get_range(dataset: str) -> range:
    """Generate a range of site indices based on the dataset type."""
    offset = dataset != "crispr"
    max_offset = (dataset == "compound") * (-3)
    return range(offset, 9 + offset + max_offset)


@app.function
def add_sample_images(
    df: duckdb.DuckDBPyRelation,
    meta_df: duckdb.DuckDBPyRelation,
    rng: range,
    col_outname: str,
    left_col: str = "JCP2022",
    right_col: str = "Metadata_JCP2022",
    seed: int = 2,
) -> duckdb.DuckDBPyRelation:
    """Add sample images to a DuckDB relation."""
    max_site = max(rng)
    min_site = min(rng)
    img_tpl = format_value("img", "phenaid")

    return duckdb.sql(f"""
        WITH numbered AS (
            SELECT df.*,
                ROW_NUMBER() OVER (PARTITION BY "{left_col}") - 1 AS _modulo
            FROM df
        ),
        joined AS (
            SELECT numbered.*,
                meta_df.Metadata_Source AS _img_src,
                meta_df.Metadata_Plate AS _img_plt,
                meta_df.Metadata_Well AS _img_wl
            FROM numbered
            JOIN meta_df ON numbered."{left_col}" = meta_df."{right_col}"
        ),
        deduped AS (
            SELECT * EXCLUDE (_rn) FROM (
                SELECT *,
                    ROW_NUMBER() OVER (
                        PARTITION BY "{left_col}", _modulo
                        ORDER BY hash(_img_src || _img_plt || _img_wl || CAST({seed} AS VARCHAR))
                    ) AS _rn
                FROM joined
            ) WHERE _rn = 1
        ),
        with_site AS (
            SELECT *,
                (_modulo % {max_site}) + {min_site} AS _sample_site
            FROM deduped
        )
        SELECT * EXCLUDE (_modulo, _sample_site, _img_src, _img_plt, _img_wl),
            printf('{img_tpl}',
                _img_src, _img_plt, _img_wl, CAST(_sample_site AS VARCHAR),
                _img_src, _img_plt, _img_wl, CAST(_sample_site AS VARCHAR)
            ) AS "{col_outname}"
        FROM with_site
    """)


# --- formatters ---


@app.function
@cache
def get_url_label(key: str) -> tuple[str, str]:
    """Retrieve a URL template and label for a given url source (vendor)."""
    vendors = dict(
        entrez=("https://www.ncbi.nlm.nih.gov/gene/{}", "NCBI"),
        genecards=(
            "https://www.genecards.org/cgi-bin/carddisp.pl?gene={}",
            "GeneCards",
        ),
        omim=("https://www.omim.org/entry/{}", "OMIM"),
        ensembl=("https://useast.ensembl.org/Homo_sapiens/Gene/Splice?g={}", "Ensembl"),
        phenaid=(
            "https://phenaid.ardigen.com/static-jumpcpexplorer/images/{}/{}/{}_{}.jpg",
            None,
        ),
        chembl=("https://www.ebi.ac.uk/chembl/explore/compound/{}", "CHEMBL"),
        drugbank=("https://go.drugbank.com/drugs/{}", "DrugBank"),
        pubchem=("https://pubchem.ncbi.nlm.nih.gov/compound/{}", "PubChem"),
    )
    return vendors[key]


@app.function
@cache
def format_value(fmt: str, vendor: str) -> str:
    """Generate a DuckDB printf format string for URL construction."""
    url_template, label = get_url_label(vendor)
    url_sql = url_template.replace("{}", "%s")
    if fmt == "href":
        return '{"href": "' + url_sql + '", "label": "' + label + '"}'
    elif fmt == "img":
        return '{"img_src": "' + url_sql + '", "href": "' + url_sql + '", "width": 200}'


@app.function
def add_external_sites(
    df: duckdb.DuckDBPyRelation,
    ext_links_col: str,
    key_source_mapper: list,
) -> duckdb.DuckDBPyRelation:
    """Add external site information as a JSON array column."""
    mapper_names = []
    for i, (key, source, mapper) in enumerate(key_source_mapper):
        name = f"_ext_mapper_{i}"
        mapper_names.append(name)
        keys = [str(k) for k in mapper.keys()] if mapper else []
        vals = [str(v) for v in mapper.values()] if mapper else []
        duckdb.execute(
            f"CREATE OR REPLACE TEMP TABLE {name} AS "
            "SELECT UNNEST($1::VARCHAR[]) AS _key, UNNEST($2::VARCHAR[]) AS _val",
            [keys, vals],
        )

    joins = "\n    ".join(
        f'LEFT JOIN _ext_mapper_{i} ON CAST(base."{source}" AS VARCHAR) = _ext_mapper_{i}._key'
        for i, (key, source, mapper) in enumerate(key_source_mapper)
    )

    href_parts = []
    for i, (key, _, _) in enumerate(key_source_mapper):
        tpl = format_value("href", key)
        href_parts.append(
            f"CASE WHEN _ext_mapper_{i}._val IS NOT NULL AND _ext_mapper_{i}._val != '' "
            f"THEN printf('{tpl}', _ext_mapper_{i}._val) END"
        )

    list_expr = f"list_filter(list_value({', '.join(href_parts)}), x -> x IS NOT NULL)"

    _result_arrow = duckdb.sql(f"""
        WITH ext AS (
            SELECT base.*, {list_expr} AS _links
            FROM df AS base
            {joins}
        )
        SELECT * EXCLUDE (_links),
            CASE WHEN len(_links) > 0
            THEN '[' || array_to_string(_links, ', ') || ']'
            ELSE '' END AS "{ext_links_col}"
        FROM ext
    """).arrow()

    for name in mapper_names:
        duckdb.execute(f"DROP TABLE IF EXISTS {name}")

    return duckdb.sql("SELECT * FROM _result_arrow")


@app.function
def _write_parquet(data, path):
    """Write a DuckDB relation to zstd-compressed parquet."""
    duckdb.sql("SELECT * FROM data").write_parquet(str(path), compression="zstd")


# --- mappers ---


@app.function
def get_mapper(
    ids: tuple[str],
    plate_type: str,
    input_col: str = "JCP2022",
    output_cols: tuple[str] = ("standard_key", "NCBI_Gene_ID"),
) -> list[dict]:
    """Generate translators based on an identifier using broad-babel."""
    mapper_values = run_query(
        query=ids,
        input_column=input_col,
        output_columns=",".join((input_col, *output_cols)),
        predicate=f"AND plate_type = '{plate_type}'",
    )
    mappers = {k: {} for k in output_cols}
    for input_id, *output_ids in mapper_values:
        for k, new_id in zip(mappers.keys(), output_ids):
            mappers[k][input_id] = new_id
    return list(mappers.values())


@app.function
def get_omim_mappers(other_ids) -> tuple[dict, dict]:
    """Retrieve omim and ensembl mappers from a relation."""
    url, known_hash = MAPPERS["omim"]
    path = pooch.retrieve(url, known_hash)
    gene_names = duckdb.sql(  # noqa: F841
        f"SELECT #1, #3, #4, #5 FROM read_csv_auto('{path}', normalize_names=True)"
    )
    valid = duckdb.sql(  # noqa: F841
        "SELECT * FROM gene_names A"
        " INNER JOIN other_ids B ON A.approved_gene_symbol_hgnc = B.std"
    )
    return (
        dict(duckdb.sql(
            "SELECT approved_gene_symbol_hgnc, mim_number FROM valid"
        ).fetchall()),
        dict(duckdb.sql(
            "SELECT approved_gene_symbol_hgnc, ensembl_gene_id_ensembl FROM valid"
        ).fetchall()),
    )


@app.function
def build_mappers(
    df, jcp_col: str, dset: str
) -> tuple[dict, dict, dict, dict]:
    """Build JCP-to-standard, JCP-to-entrez, std-to-omim, std-to-ensembl mappers."""
    uniq = tuple(
        r[0] for r in duckdb.sql(f'SELECT DISTINCT "{jcp_col}" FROM df').fetchall()
    )
    jcp_to_std, jcp_to_entrez = get_mapper(uniq, dset)
    assert len(jcp_to_std), f"No mappers were found {jcp_col=}, {dset=}"

    entrez_to_omim = {}
    entrez_to_ensembl = {}

    if any(jcp_to_entrez.values()):
        duckdb.execute(
            "CREATE OR REPLACE TEMP TABLE _other_raw AS "
            "SELECT UNNEST($1::VARCHAR[]) AS entrez, UNNEST($2::VARCHAR[]) AS std",
            [list(jcp_to_entrez.values()), list(jcp_to_std.values())],
        )
        other_ids = duckdb.sql(  # noqa: F841
            "SELECT DISTINCT * FROM _other_raw"
            " WHERE NOT regexp_matches(entrez, '[A-Z]')"
        )
        entrez_to_omim, entrez_to_ensembl = get_omim_mappers(other_ids)
        duckdb.execute("DROP TABLE IF EXISTS _other_raw")

    return jcp_to_std, jcp_to_entrez, entrez_to_omim, entrez_to_ensembl


@app.function
def build_key_source_mapper(
    dset: str,
    jcp_col: str,
    jcp_to_std: dict,
    jcp_to_entrez: dict,
    std_to_omim: dict,
    std_to_ensembl: dict,
) -> list:
    """Build the key-source-mapper list for external links (genetic vs compound)."""
    if dset != "compound" and not dset.startswith("compound"):
        return [
            ("entrez", jcp_col, jcp_to_entrez),
            ("omim", STD_OUTNAME, std_to_omim),
            (
                "genecards",
                STD_OUTNAME,
                dict(zip(jcp_to_std.values(), jcp_to_std.values())),
            ),
            ("ensembl", STD_OUTNAME, std_to_ensembl),
        ]
    return [(k, jcp_col, v) for k, v in get_compound_mappers()]


@app.function
def get_synonym_mapper() -> dict[str, str]:
    """Retrieve a dictionary mapping GeneIDs to their corresponding synonyms."""
    url, known_hash = MAPPERS["synonym"]
    path = pooch.retrieve(url, known_hash)
    result = duckdb.sql(f"""
        SELECT CAST("GeneID" AS VARCHAR),
               "Symbol" || '|' || "Synonyms"
        FROM read_csv_auto('{path}', delim='\t')
        WHERE "Synonyms" != '-'
    """).fetchall()
    return dict(result)


@app.function
def get_compound_mappers() -> tuple[tuple[str, dict[str, str | int]]]:
    """Get mapping between jcp ids and compound ids from different databases."""
    url, known_hash = MAPPERS["compound"]
    path = pooch.retrieve(url, known_hash)
    tb = duckdb.sql(  # noqa: F841
        f"SELECT Metadata_JCP2022, COLUMNS('id.*')"
        f" FROM read_parquet('{path}')"
        " WHERE Metadata_JCP2022 IS NOT NULL"
    )
    rows = duckdb.sql(
        "UNPIVOT tb ON CAST(COLUMNS(* EXCLUDE Metadata_JCP2022) AS VARCHAR)"
        " INTO NAME name VALUE value"
    ).fetchall()

    mappers = {}
    for jcp, name, value in rows:
        clean_name = name[3:]  # remove "id_" prefix
        if clean_name not in mappers:
            mappers[clean_name] = {}
        if value is not None:
            mappers[clean_name][jcp] = str(value)

    return mappers.items()


# --- replicability ---


@app.function
def add_replicability(
    profiles: duckdb.DuckDBPyRelation,
    left_on: str,
    right_on: str = "Metadata_JCP2022",
    cols_to_add: dict = None,
    suffix: str = "",
) -> duckdb.DuckDBPyRelation:
    """Add a column indicating replicability to the input relation."""
    if cols_to_add is None:
        cols_to_add = {
            "corrected_p_value": "Corrected p-value",
            "mean_average_precision": "Phenotypic activity",
        }

    base_url = "https://github.com/jump-cellpainting/2024_Chandrasekaran_Morphmap/raw/c47ad6c953d70eb9e6c9b671c5fe6b2c82600cfc/03.retrieve-annotations/output/{}"

    jcp = duckdb.sql(f'SELECT "{left_on}" FROM profiles LIMIT 1').fetchone()[0]

    match jcp[8]:
        case "8":
            filepath = base_url.format(
                "phenotypic-activity-wellpos_cc_var_mad_outlier_featselect_sphering_harmony_PCA_corrected.csv.gz"
            )
            reader = "read_csv_auto"
        case "9":
            filepath = base_url.format(
                "phenotypic-activity-wellpos_cc_var_mad_outlier_featselect_sphering_harmony.csv.gz"
            )
            reader = "read_csv_auto"
        case "0":
            filepath = "https://zenodo.org/api/records/15122159/files/profiles_var_mad_int_featselect_harmony_map_negcon.parquet/content"
            reader = "read_parquet"
        case _:
            raise Exception("Invalid JCP")

    # Download to local cache for reliable access
    local_path = pooch.retrieve(filepath, known_hash=None)

    select_parts = [
        f'ROUND(CAST("{old}" AS DOUBLE), 5) AS "{new}{suffix}"'
        for old, new in cols_to_add.items()
    ]
    select_parts.append(f'CAST("{right_on}" AS VARCHAR) AS _repl_key')

    result_cols = ", ".join(
        f'_repl."{new}{suffix}"' for new in cols_to_add.values()
    )

    return duckdb.sql(f"""
        SELECT profiles.*, {result_cols}
        FROM profiles
        LEFT JOIN (
            SELECT {', '.join(select_parts)} FROM {reader}('{local_path}')
        ) AS _repl
        ON CAST(profiles."{left_on}" AS VARCHAR) = _repl._repl_key
    """)


# --- metadata ---


@app.function
def write_metadata(dset: str, table_type: str, colnames: tuple[str]) -> None:
    """Write metadata file to customize Datasette."""
    if dset == "compound":
        prefix = "If you have an InChIKey for your compound, choose Perturbation. If you have a JCP ID, choose JCPID_2022. If you have neither, go <a href = https://broadinstitute.github.io/jump_hub/reference/01_chemical_query.html>here</a> to look up the JCP ID for your compound or a close analog."
    elif dset in ("crispr", "orf"):
        prefix = 'Choose "Synonyms", and "contains", and type in your gene name in all capital letters in the box below.'
    elif table_type == "gallery":
        prefix = ""

    if table_type == "matches":
        prefix = (
            "Explore the most similar perturbations to find matches (up to 50 will be shown). "
            + prefix
            + 'Click the "Perturbation-Match Similarity" header to sort the matches. '
        )
    elif table_type == "gallery":
        prefix = "Explore the JUMP images. " + prefix
    elif table_type == "feature":
        prefix = "Explore statistically significant features. " + prefix

    if table_type != "gallery":
        valid_names = colnames
    else:
        valid_names = (*[x for x in colnames if not x.startswith("Site")], "Site X")

    source_name = dset
    if table_type == "feature":
        source_name += "_interpretable"

    source_url = get_profiles_url(source_name)

    broad_suffix = dset
    if table_type != "matches":
        broad_suffix = "_".join((dset, table_type))

    data = {
        "databases": {
            "data": {
                "source": "JUMP Consortium",
                "source_url": "http://broad.io/jump",
                "tables": {
                    "content": {
                        "description_html": f"{prefix} <a href = https://github.com/jump-cellpainting/datasets/blob/main/manifests/profile_index.json> Data Index</a>. <a href = {source_url}>Download</a> source profiles. <a href = https://broad.io/jump>JUMP Hub</a> for more information and tutorials. <a href = http://broad.io/{broad_suffix}>Latest</a> version of this page.",
                        "title": f"{dset.upper()} {_table_type_to_suffix(table_type)}",
                    }
                },
            }
        }
    }

    metadata_dir = Path(__file__).parent.parent / "metadata"
    metadata_dir.mkdir(parents=True, exist_ok=True)
    with (metadata_dir / f"{dset}_{table_type}.json").open("w") as f:
        data["databases"]["data"]["tables"]["content"]["columns"] = {
            x: _DESCRIPTIONS.get(x) for x in valid_names
        }
        print(json.dumps(data, indent=4), file=f)


@app.function
def _table_type_to_suffix(table_type: str) -> str | None:
    """Convert a table type to a title suffix."""
    match table_type:
        case "matches":
            return "Matches"
        case "feature":
            return "Feature Ranking"
        case "gallery":
            return "Gallery"


# --- Interactive UI ---


@app.cell
def _(mo):
    mo.md("# JUMP Data Loader\nSelect a dataset to inspect its profiles.")
    return ()


@app.cell
def _(mo):
    subset_selector = mo.ui.dropdown(
        options=list(SUBSETS),
        value="crispr",
        label="Dataset",
    )
    subset_selector
    return (subset_selector,)


@app.cell
def _(mo):
    run_btn = mo.ui.run_button(label="Load dataset")
    run_btn
    return (run_btn,)


@app.cell
def _(mo, run_btn, subset_selector):
    mo.stop(not run_btn.value)
    _data = load_profiles_lazy(subset_selector.value)
    _cols = _data.columns
    _meta_cols = [c for c in _cols if c.startswith("Metadata_")]
    _feat_cols = [c for c in _cols if not c.startswith("Metadata_")]
    mo.md(
        f"**{subset_selector.value}** — "
        f"{len(_meta_cols)} metadata columns, {len(_feat_cols)} feature columns"
    )
    return ()


if __name__ == "__main__":
    app.run()
