import ftplib
import os
from pathlib import Path

import pandas as pd
import requests
from tqdm.auto import tqdm


def download_ftp_file(host, remote_file_path, filepath: Path, redownload=False):
    if filepath.is_file() and not redownload:
        return
    try:
        if not isinstance(host, ftplib.FTP):
            ftp = ftplib.FTP(host, user="anonymous", passwd=f"anonymous@{host}")
        else:
            ftp = host
        # Get the file size
        file_size = ftp.size(remote_file_path)

        # Download the file
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with (
            filepath.open("wb") as local_file,
            tqdm(
                total=file_size,
                unit="B",
                unit_scale=True,
                desc="Downloading",
                ncols=80,
                leave=False,
            ) as pbar,
        ):

            def progress_callback(data):
                local_file.write(data)
                pbar.update(len(data))

            ftp.retrbinary("RETR " + remote_file_path, progress_callback)
    except Exception as e:
        print("An error occurred:", e)


def download_ftp_directory(ftp_server, remote_dir, local_dir, redownload=False):
    ftp = ftplib.FTP(ftp_server)
    ftp.login()
    os.makedirs(local_dir, exist_ok=True)
    ftp.cwd(remote_dir)

    local_file_list = local_dir / "_list.txt"
    remote_file_list = ftp.nlst()
    if not local_file_list.exists() or redownload:
        with local_file_list.open("w") as fwrite:
            fwrite.write("\n".join(remote_file_list))
    else:
        with local_file_list.open("r") as fread:
            local_file_list = fread.read().splitlines()
        remote_file_list = [f for f in remote_file_list if f not in local_file_list]

    for file_name in tqdm(remote_file_list, leave=False):
        local_file = Path(os.path.join(local_dir, file_name))
        try:
            ftp.cwd(file_name)  # If this works, it's a directory
            new_remote_dir = os.path.join(remote_dir, file_name)
            new_local_dir = os.path.join(local_dir, file_name)
            download_ftp_directory(ftp, new_remote_dir, new_local_dir)
            ftp.cwd("..")  # Go back up a level in the directory tree
        except Exception:
            download_ftp_file(ftp, file_name, local_file, redownload)
    ftp.quit()


def download_file(url, filepath: Path, redownload=False):
    if filepath.is_file() and not redownload:
        return
    response = requests.get(url, stream=True)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    total_size = int(response.headers.get("content-length", 0))
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
    gene_ids = pd.read_csv(dst, sep="\t", low_memory=False)
    gene_ids.dropna(subset="entrez_id", inplace=True)
    gene_ids["entrez_id"] = gene_ids["entrez_id"].astype(int)
    gene_mapper = gene_ids.set_index("entrez_id")["symbol"]
    return gene_mapper
