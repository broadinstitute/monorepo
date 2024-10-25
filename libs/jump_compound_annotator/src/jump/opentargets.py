from pathlib import Path

import pandas as pd

from jump.utils import download_ftp_directory

FTP_SERVER = "ftp.ebi.ac.uk"
REMOTE_ROOT = "/pub/databases/opentargets/platform/24.09/output/etl/parquet"


def _open(output_path: Path, folder, redownload=False):
    remote_dir = REMOTE_ROOT + f"/{folder}"
    local_dir = output_path / f"opentargets/{folder}"
    download_ftp_directory(FTP_SERVER, remote_dir, local_dir, redownload)
    dfs = []
    for path in local_dir.glob("*parquet"):
        dfs.append(pd.read_parquet(path))
    df = pd.concat(dfs)
    return df


def get_compound_annotations(output_dir: str):
    df = _open(Path(output_dir), "molecule")
    df = df.dropna(subset=["inchiKey", "linkedTargets"]).copy()
    df["targets"] = df["linkedTargets"].apply(lambda x: x.get("rows", []))
    df = df[df["targets"].apply(len) > 0]
    df = df.explode("targets")
    mapper = pd.read_csv(
        Path(output_dir) / "hgnc/complete_set.txt", sep="\t", low_memory=False
    )
    mapper = mapper.drop_duplicates(subset="ensembl_gene_id").set_index(
        "ensembl_gene_id"
    )["symbol"]
    df["target"] = df["targets"].map(mapper)
    df["rel_type"] = "target"
    df["database"] = "opentargets"
    df["source"] = df["id"]
    df["source_id"] = "chembl"
    return df[["source", "target", "rel_type", "source_id"]].reset_index(drop=True)
