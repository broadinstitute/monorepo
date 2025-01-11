from pathlib import Path
import pandas as pd

from jump_compound_annotator.utils import load_jump_ids

output_dir = "./output/"
output_path = Path(output_dir)
jump_ids = load_jump_ids(output_path)

# File from http://stitch.embl.de/download/chemicals.inchikeys.v5.0.tsv.gz
keys = pd.read_csv(output_path / "stitch/chemicals.inchikeys.v5.0.tsv.gz", sep="\t")
keys = keys.query("inchikey.isin(@jump_ids.inchikey)")

# File generated from http://useast.ensembl.org/biomart/martview/ with
# Attributes ['Protein stable ID', 'HGNC symbol'] from 'Human Genes' filter
mapper = pd.read_csv(output_path / "stitch/mart_export.txt.gz", sep="\t")
mapper = mapper.dropna()
mapper["protein"] = "9606." + mapper["Protein stable ID"]

# File from http://stitch.embl.de/download/protein_chemical.links.v5.0/9606.protein_chemical.links.v5.0.tsv.gz
l_path = output_path / "stitch/9606.protein_chemical.links.transfer.v5.0.tsv.gz"
links = pd.read_csv(l_path, sep="\t")
query = "chemical.isin(@keys.flat_chemical_id) and protein.isin(@mapper.protein)"
jump_links = links.query(query)
jump_links = jump_links.merge(mapper, on="protein")
jump_links = jump_links.merge(keys, left_on="chemical", right_on="flat_chemical_id")
annotations = jump_links.pivot_table(
    index="inchikey", columns="HGNC symbol", values="combined_score"
)
