# notebooks/01_filter_annotations.py
# ---
# jupyter:
#   jupytext:
#     formats: ipynb,py:percent
#     text_representation:
#       extension: .py
#       format_name: percent
#       format_version: '1.3'
#       jupytext_version: 1.14.5
# ---

# %% [markdown]
# # Compound-Target Annotation Analysis and Filtering
#
# This notebook processes and filters compound-target relationship annotations to:
# 1. Standardize relationship types
# 2. Remove hub compounds
# 3. Analyze relationship co-occurrences
# 4. Generate filtered dataset for downstream use
#
# First get the annotations:
# rsync -avz "spirit:/home/shsingh/work/projects/annotator/outputs/{unichem_pubchem_mapper.parquet,mychem_pubchem_mapper.parquet,mychem_chembl_mapper.parquet,unichem_drugbank_mapper.parquet,annotations.parquet,gene_interactions.parquet,compound_interactions.parquet,unichem_chembl_mapper.parquet,mychem_drugbank_mapper.parquet,biokg}" .

# %% [markdown]
# ## Setup

# %%
from pathlib import Path
from jump_compound_annotator.data_processing import AnnotationProcessor

PROJECT_ROOT = Path(__file__).parent
OUTPUT_DIR = PROJECT_ROOT / "outputs"

# Constants
RELATIONSHIP_TYPE_MAPPING = {
    "DOWNREGULATES_CHdG": "downregulates",
    "CdG": "downregulates",
    "UPREGULATES_CHuG": "upregulates",
    "CuG": "upregulates",
    "DRUG_TARGET": "targets",
    "target": "targets",
    "DRUG_CARRIER": "carries",
    "carrier": "carries",
    "DRUG_ENZYME": "enzyme",
    "enzyme": "enzyme",
    "DRUG_TRANSPORTER": "transports",
    "transporter": "transports",
    "BINDS_CHbG": "binds",
    "CbG": "binds",
    "DRUG_BINDING_GENE": "binds",
}

EXCLUDED_RELATIONSHIPS = ["DPI", "DRUG_BINDINH_GENE"]
HUB_COMPOUND_THRESHOLD = 0.999  # 99.9th percentile for filtering hub compounds

# %% [markdown]

# %% [markdown]
# ## Load and Process Annotations

# %%
# Initialize processor
processor = AnnotationProcessor(OUTPUT_DIR)

# Load raw annotations
annotations = processor.load_annotations()
print(f"Initial annotations shape: {annotations.shape}")

# %% [markdown]
# ## Clean and Standardize

# %%
# Standardize relationship types
annotations = processor.standardize_relationship_types(
    annotations, RELATIONSHIP_TYPE_MAPPING
)

# Remove excluded relationships
annotations = annotations.query("not rel_type.isin(@EXCLUDED_RELATIONSHIPS)")

# Remove duplicates
annotations = annotations.drop_duplicates(
    ["inchikey", "rel_type", "target"]
).reset_index(drop=True)

print(f"Shape after initial cleaning: {annotations.shape}")

# %% [markdown]
# ## Analyze Relationship Co-occurrences

# %%
# Add link IDs and calculate co-occurrences
annotations = processor.create_link_ids(annotations)
cooc = processor.calculate_cooccurrence(annotations)

# Calculate normalized co-occurrences
m_edges = processor.calculate_normalized_cooccurrence(cooc)

# # Visualize co-occurrences
# plt.figure(figsize=(12, 8))
# sns.heatmap(cooc, annot=True, cmap="viridis")
# plt.title("Relationship Type Co-occurrences")
# plt.tight_layout()
# plt.savefig(OUTPUT_DIR / "cooccurrence_matrix.png")

# %% [markdown]
# ## Filter Hub Compounds

# %%
# Remove hub compounds
annotations = processor.filter_hub_compounds(annotations, HUB_COMPOUND_THRESHOLD)

print(f"Shape after hub filtering: {annotations.shape}")

# %% [markdown]
# ## Final Statistics

# %%
# Calculate and display final statistics
final_stats = {
    "Total Annotations": len(annotations),
    "Unique Targets": annotations["target"].nunique(),
    "Unique Compounds": annotations.inchikey.nunique(),
    "Relationship Types": annotations.rel_type.nunique(),
}

print("\nFinal Dataset Statistics:")
for key, value in final_stats.items():
    print(f"{key}: {value}")

# %% [markdown]
# ## Save Filtered Dataset

# %%
# Save filtered annotations
output_file = OUTPUT_DIR / "filtered_annotations.parquet"
annotations.to_parquet(output_file, index=False)
print(f"Saved filtered annotations to: {output_file}")
