import requests
from tqdm.auto import tqdm


def download_file(url, filepath, redownload=False):
    response = requests.get(url, stream=True)
    if filepath.is_file() and not redownload:
        return
    filepath.parent.mkdir(parents=True, exist_ok=True)

    total_size = int(response.headers.get('content-length'))
    block_size = 1024 * 1024  # 1 MB

    with filepath.open('wb') as fwriter:
        for data in tqdm(response.iter_content(block_size),
                         desc='Downloading',
                         unit='MB',
                         total=total_size // block_size):
            fwriter.write(data)
