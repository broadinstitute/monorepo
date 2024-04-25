import ftplib
from pathlib import Path

import pandas as pd
import requests
from tqdm.auto import tqdm


def download_ftp_file(host, remote_file_path, filepath: Path, redownload=False):
    if filepath.is_file() and not redownload:
        return
    try:
        ftp = ftplib.FTP(host, user="anonymous", passwd=f"anonymous@{host}")
        # Get the file size
        file_size = ftp.size(remote_file_path)

        # Download the file
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with (
            filepath.open("wb") as local_file,
            tqdm(
                total=file_size, unit="B", unit_scale=True, desc="Downloading", ncols=80
            ) as pbar,
        ):

            def progress_callback(data):
                local_file.write(data)
                pbar.update(len(data))

            ftp.retrbinary("RETR " + remote_file_path, progress_callback)
    except Exception as e:
        print("An error occurred:", e)
    finally:
        ftp.quit()


def download_file(url, filepath: Path, redownload=False):
    if filepath.is_file() and not redownload:
        return
    response = requests.get(url, stream=True)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    total_size = int(response.headers.get("content-length"))
    block_size = 1024 * 1024  # 1 MB

    with filepath.open("wb") as fwriter:
        for data in tqdm(
            response.iter_content(block_size),
            desc="Downloading",
            unit="MB",
            total=total_size // block_size,
        ):
            fwriter.write(data)


def load_jump_ids(output_path):
    ids = list(map(pd.read_csv, output_path.glob("ids/ids_*.csv")))
    if not ids:
        raise ValueError("IDs files not found")
    ids = pd.concat(ids).drop_duplicates().reset_index(drop=True)
    return ids


def ncbi_to_symbol(output_path: Path):
    url = "https://g-a8b222.dd271.03c0.data.globus.org/pub/databases/genenames/hgnc/tsv/hgnc_complete_set.txt"
    dst = output_path / "hgnc" / "complete_set.txt"
    download_file(url, dst)
    gene_ids = pd.read_csv(dst, sep="\t")
    gene_ids.dropna(subset="entrez_id", inplace=True)
    gene_ids["entrez_id"] = gene_ids["entrez_id"].astype(int)
    gene_mapper = gene_ids.set_index("entrez_id")["symbol"]
    return gene_mapper
