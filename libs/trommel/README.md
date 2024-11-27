# trommel

This is a collection of clean-up functions and small pipelines for morphological profiling.

A `trommel` is a revolving cylindrical sieve used for screening or sizing rock and ore, it helps separate the minerals from the waste. This tool aims to fulfill the same purpose for morphological profiling, and possibly many other high-throughput datasets.

# Quick Start
```python
import polars as pl
import polars.selectors as cs
from trommel.core import basic_cleanup

meta_selector = cs.by_dtype(pl.String)
profiles = pl.scan_parquet("https://cellpainting-gallery.s3.amazonaws.com/cpg0016-jump-assembled/source_all/workspace/profiles/jump-profiling-recipe_2024_a917fa7/CRISPR/profiles_wellpos_cc_var_mad_outlier_featselect_sphering_harmony_PCA_corrected/profiles.parquet", n_rows=100).collect()

"""
shape: (100, 3_677)
┌───────────┬───────────┬───────────┬───────────┬───┬───────────┬───────────┬───────────┬──────────┐
│ Metadata_ ┆ Metadata_ ┆ Metadata_s ┆ Metadata_ ┆ … ┆ Nuclei_Te ┆ Nuclei_Te ┆ Nuclei_Te ┆ Nuclei_T │
│ Source    ┆ Plate     ┆ Well      ┆ JCP2022   ┆   ┆ xture_Var ┆ xture_Var ┆ xture_Var ┆ exture_V │
│ ---       ┆ ---       ┆ ---       ┆ ---       ┆   ┆ iance_RNA ┆ iance_RNA ┆ iance_RNA ┆ ariance_ │
│ str       ┆ str       ┆ str       ┆ str       ┆   ┆ _5_…      ┆ _5_…      ┆ _5_…      ┆ RNA_5_…  │
│           ┆           ┆           ┆           ┆   ┆ ---       ┆ ---       ┆ ---       ┆ ---      │
│           ┆           ┆           ┆           ┆   ┆ f32       ┆ f32       ┆ f32       ┆ f32      │
╞═══════════╪═══════════╪═══════════╪═══════════╪═══╪═══════════╪═══════════╪═══════════╪══════════╡
│ source_13 ┆ CP-CC9-R1 ┆ A02       ┆ JCP2022_8 ┆ … ┆ 6.226163  ┆ 6.449576  ┆ 6.233986  ┆ 6.447817 │
│           ┆ -01       ┆           ┆ 00002     ┆   ┆           ┆           ┆           ┆          │
│ source_13 ┆ CP-CC9-R1 ┆ A03       ┆ JCP2022_8 ┆ … ┆ 7.107765  ┆ 7.359348  ┆ 7.119856  ┆ 7.359909 │
│           ┆ -01       ┆           ┆ 00573     ┆   ┆           ┆           ┆           ┆          │
│ source_13 ┆ CP-CC9-R1 ┆ A04       ┆ JCP2022_8 ┆ … ┆ 8.922542  ┆ 9.2922    ┆ 8.964124  ┆ 9.255968 │
│           ┆ -01       ┆           ┆ 06794     ┆   ┆           ┆           ┆           ┆          │
│ source_13 ┆ CP-CC9-R1 ┆ A05       ┆ JCP2022_8 ┆ … ┆ 7.982674  ┆ 8.243299  ┆ 7.974916  ┆ 8.25239  │
│           ┆ -01       ┆           ┆ 02800     ┆   ┆           ┆           ┆           ┆          │
│ source_13 ┆ CP-CC9-R1 ┆ A06       ┆ JCP2022_8 ┆ … ┆ 10.368849 ┆ 10.728938 ┆ 10.346541 ┆ 10.69108 │
│           ┆ -01       ┆           ┆ 02216     ┆   ┆           ┆           ┆           ┆ 2        │
│ …         ┆ …         ┆ …         ┆ …         ┆ … ┆ …         ┆ …         ┆ …         ┆ …        │
│ source_13 ┆ CP-CC9-R1 ┆ E10       ┆ JCP2022_8 ┆ … ┆ 6.193636  ┆ 6.414464  ┆ 6.199627  ┆ 6.40822  │
│           ┆ -01       ┆           ┆ 01144     ┆   ┆           ┆           ┆           ┆          │
│ source_13 ┆ CP-CC9-R1 ┆ E11       ┆ JCP2022_8 ┆ … ┆ 5.278385  ┆ 5.445997  ┆ 5.277493  ┆ 5.447682 │
│           ┆ -01       ┆           ┆ 05271     ┆   ┆           ┆           ┆           ┆          │
│ source_13 ┆ CP-CC9-R1 ┆ E12       ┆ JCP2022_8 ┆ … ┆ 5.334033  ┆ 5.501099  ┆ 5.344191  ┆ 5.507084 │
│           ┆ -01       ┆           ┆ 06272     ┆   ┆           ┆           ┆           ┆          │
│ source_13 ┆ CP-CC9-R1 ┆ E13       ┆ JCP2022_8 ┆ … ┆ 7.073516  ┆ 7.312291  ┆ 7.087072  ┆ 7.332959 │
│           ┆ -01       ┆           ┆ 02990     ┆   ┆           ┆           ┆           ┆          │
│ source_13 ┆ CP-CC9-R1 ┆ E14       ┆ JCP2022_8 ┆ … ┆ 6.127821  ┆ 6.326293  ┆ 6.127594  ┆ 6.340693 │
│           ┆ -01       ┆           ┆ 04381     ┆   ┆           ┆           ┆           ┆          │
└───────────┴───────────┴───────────┴───────────┴───┴───────────┴───────────┴───────────┴──────────┘
"""

cleanup = basic_cleanup(profiles, meta_selector = meta_selector)

"""
shape: (100, 554)
┌─────────────────┬────────────────┬───────────────┬──────────────────┬───┬─────────────────┬─────────────────┬─────────────────┬─────────────────┐
│ Metadata_Source ┆ Metadata_Plate ┆ Metadata_Well ┆ Metadata_JCP2022 ┆ … ┆ Nuclei_Texture_ ┆ Nuclei_Texture_ ┆ Nuclei_Texture_ ┆ Nuclei_Texture_ │
│ ---             ┆ ---            ┆ ---           ┆ ---              ┆   ┆ SumAverage_AGP_ ┆ SumAverage_ER_3 ┆ SumVariance_DNA ┆ SumVariance_Mit │
│ str             ┆ str            ┆ str           ┆ str              ┆   ┆ …               ┆ …               ┆ …               ┆ …               │
│                 ┆                ┆               ┆                  ┆   ┆ ---             ┆ ---             ┆ ---             ┆ ---             │
│                 ┆                ┆               ┆                  ┆   ┆ f32             ┆ f32             ┆ f32             ┆ f32             │
╞═════════════════╪════════════════╪═══════════════╪══════════════════╪═══╪═════════════════╪═════════════════╪═════════════════╪═════════════════╡
│ source_13       ┆ CP-CC9-R1-01   ┆ A02           ┆ JCP2022_800002   ┆ … ┆ 0.113776        ┆ -0.577417       ┆ -0.138683       ┆ 17.711971       │
│ source_13       ┆ CP-CC9-R1-01   ┆ A03           ┆ JCP2022_800573   ┆ … ┆ 0.563728        ┆ 0.259718        ┆ -0.028451       ┆ 7.942208        │
│ source_13       ┆ CP-CC9-R1-01   ┆ A04           ┆ JCP2022_806794   ┆ … ┆ 0.650211        ┆ 0.682264        ┆ -0.001948       ┆ 3.534184        │
│ source_13       ┆ CP-CC9-R1-01   ┆ A05           ┆ JCP2022_802800   ┆ … ┆ 0.458357        ┆ 0.305402        ┆ -0.032553       ┆ 5.978285        │
│ source_13       ┆ CP-CC9-R1-01   ┆ A06           ┆ JCP2022_802216   ┆ … ┆ 0.719411        ┆ 0.932589        ┆ 0.086287        ┆ 14.690929       │
│ …               ┆ …              ┆ …             ┆ …                ┆ … ┆ …               ┆ …               ┆ …               ┆ …               │
│ source_13       ┆ CP-CC9-R1-01   ┆ E10           ┆ JCP2022_801144   ┆ … ┆ -0.070035       ┆ 0.063227        ┆ 0.024047        ┆ -0.151976       │
│ source_13       ┆ CP-CC9-R1-01   ┆ E11           ┆ JCP2022_805271   ┆ … ┆ -0.317568       ┆ -0.168455       ┆ 0.045889        ┆ -0.012995       │
│ source_13       ┆ CP-CC9-R1-01   ┆ E12           ┆ JCP2022_806272   ┆ … ┆ -0.102242       ┆ -0.071743       ┆ 0.09979         ┆ -3.231946       │
│ source_13       ┆ CP-CC9-R1-01   ┆ E13           ┆ JCP2022_802990   ┆ … ┆ 0.035003        ┆ -0.124911       ┆ 0.163038        ┆ 4.087936        │
│ source_13       ┆ CP-CC9-R1-01   ┆ E14           ┆ JCP2022_804381   ┆ … ┆ -0.416099       ┆ -0.806152       ┆ 0.055316        ┆ -2.082987       │
└─────────────────┴────────────────┴───────────────┴──────────────────┴───┴─────────────────┴─────────────────┴─────────────────┴─────────────────┘"""
```
The basic cleanup steps are:
1. Remove NaNs
2. Calculate Robust Mean Average Deviation (following [pycytominer's](https://github.com/cytomining/pycytominer/blob/f6d0f6668571e39a8cf3a10dc290389b42891777/pycytominer/operations/transform.py#L313) implementation)
3. Remove outliers
4. Remove redundant (highly correlated) features 

# Additional information
## Related projects
- [pycytominer](https://github.com/cytomining/pycytominer): The closest match, but with more complexity imbued and many of the math functions are pandas-centric.
- [EFAAR](https://github.com/recursionpharma/EFAAR_benchmarking/blob/trunk/efaar_benchmarking/efaar.py): Much simpler implementation, but it commits similar hard-coding of cellprofiler features. We instead try to be agnostic to the way of the selectors, but we do commit to using `polars`. 

## Future features
- Full separation of data + metadata
- Additional processing and clean-up functions
- Additional default pipelines
