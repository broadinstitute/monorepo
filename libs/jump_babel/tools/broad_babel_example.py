#!/usr/bin/env python3
# %%
from broad_babel.query import broad_to_standard, export_csv, run_query

# %%

# Export the whole file
export_csv("./temporal.csv")

# %%
# Query from broad to standard

broad_to_standard("BRD-K18895904-001-16-1")

# %% If you query multiple entries you get a dictionary

broad_to_standard(("BRD-K36461289-001-05-8", "ccsbBroad304_16164"))

# %% More complex queries are available (see run_query documentation)

run_query(query="JCP2022_915119", input_column="jump_id", output_column="broad_sample")
