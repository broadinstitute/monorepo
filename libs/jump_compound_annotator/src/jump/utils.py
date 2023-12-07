import ftplib
from pathlib import Path
import pandas as pd
import requests
from tqdm.auto import tqdm
from importlib.resources import files


def download_ftp_file(host,
                      remote_file_path,
                      filepath: Path,
                      redownload=False):
    if filepath.is_file() and not redownload:
        return
    try:
        ftp = ftplib.FTP(host, user='anonymous', passwd=f'anonymous@{host}')
        # Get the file size
        file_size = ftp.size(remote_file_path)

        # Download the file
        filepath.parent.mkdir(parents=True, exist_ok=True)
        with filepath.open('wb') as local_file, tqdm(total=file_size,
                                                     unit='B',
                                                     unit_scale=True,
                                                     desc='Downloading',
                                                     ncols=80) as pbar:

            def progress_callback(data):
                local_file.write(data)
                pbar.update(len(data))

            ftp.retrbinary('RETR ' + remote_file_path, progress_callback)
    except Exception as e:
        print("An error occurred:", e)
    finally:
        ftp.quit()


def download_file(url, filepath: Path, redownload=False):
    if filepath.is_file() and not redownload:
        return
    response = requests.get(url, stream=True)
    filepath.parent.mkdir(parents=True, exist_ok=True)

    total_size = int(response.headers.get('content-length'))
    block_size = 1024 * 1024  # 1 MB

    with filepath.open('wb') as fwriter:
        for data in tqdm(response.iter_content(block_size),
                         desc='Downloading',
                         unit='MB',
                         total=total_size // block_size):
            fwriter.write(data)


def load_jump_ids(output_path):
    ids = list(map(pd.read_csv, output_path.glob('ids/ids_*.csv')))
    if not ids:
        raise ValueError('IDs files not found')
    ids = pd.concat(ids).drop_duplicates().reset_index(drop=True)
    return ids


def load_gene_ids():
    # File gather from https://github.com/jump-cellpainting/morphmap/blob/ed89177e3d878c6c60526a1f0218acd53cdd9905/2.create-annotations/output/gene_ids_map.tsv
    fread = files('jump').joinpath('gene_ids_map.tsv.gz')
    return pd.read_csv(fread, sep='\t')
