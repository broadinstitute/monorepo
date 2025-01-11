import pandas as pd
from jump_compound_annotator.utils import download_ftp_file
from pathlib import Path


def read_gene_info_file(output_path: Path, redownload):
    filepath = output_path / "ncbi/gene_info.gz"
    remote_file_path = "/gene/DATA/GENE_INFO/Mammalia/Homo_sapiens.gene_info.gz"
    host = "ftp.ncbi.nih.gov"
    download_ftp_file(host, remote_file_path, filepath, redownload)
    return pd.read_csv(filepath, sep="\t")


def get_xrefs(output_dir: str, redownload):
    gene_ids = read_gene_info_file(Path(output_dir), redownload)
    xrefs = gene_ids[["Symbol", "dbXrefs"]].drop_duplicates()
    xrefs = xrefs.query('dbXrefs!="-"').set_index("Symbol")
    xrefs = xrefs["dbXrefs"].str.split("|").explode()
    xrefs = xrefs.str.split(":").apply(lambda x: x[-2:])
    xrefs = pd.DataFrame(
        xrefs.tolist(), index=xrefs.index, columns=["database", "id"]
    ).reset_index()
    xrefs = xrefs.drop_duplicates(["database", "id"], keep=False)
    return xrefs


def get_synonyms(output_dir: str, redownload):
    gene_ids = read_gene_info_file(Path(output_dir), redownload)

    synonyms = gene_ids[["Symbol", "Synonyms"]].drop_duplicates()
    synonyms = synonyms.query('Synonyms!="-"').set_index("Symbol")["Synonyms"]
    synonyms = synonyms.str.split("|").explode().reset_index()
    synonyms = synonyms.drop_duplicates("Synonyms", keep=False)
    return synonyms
