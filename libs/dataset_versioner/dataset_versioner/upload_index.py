"""Upload the updated CSV file to Zenodo, handling versioning and publishing."""

import argparse
import csv
import hashlib
import json
import logging
import os
import sys
from pathlib import Path
from typing import Optional

import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ZenodoClient:  # noqa: D101
    def __init__(self, access_token: str, endpoint: str = "https://zenodo.org") -> None:  # noqa: D107
        self.access_token = access_token
        self.endpoint = endpoint
        self.deposition_url = f"{self.endpoint}/api/deposit/depositions"
        self.headers = {"Content-Type": "application/json"}

    def _request(
        self,
        method: str,
        url: str,
        params: Optional[dict] = None,
        **kwargs,
    ) -> dict:  # noqa: D103
        params = params or {}
        params["access_token"] = self.access_token
        try:
            response = requests.request(
                method, url, params=params, headers=self.headers, **kwargs
            )
            response.raise_for_status()
            return response.json()
        except requests.RequestException as e:
            logger.error(f"Error during {method} request to {url}: {e}")
            raise

    def get_latest_deposition_id(self, original_id: str) -> str:  # noqa: D102
        url = f"{self.endpoint}/api/records/{original_id}/latest"
        data = self._request("GET", url)
        latest_id = data["id"]
        logger.info(f"Latest deposition ID: {latest_id}")
        return str(latest_id)

    def get_file_md5sum(self, deposition_id: str) -> Optional[str]:  # noqa: D102
        url = f"{self.deposition_url}/{deposition_id}/files"
        response = self._request("GET", url)
        if not response:
            logger.warning(f"No files found in deposition {deposition_id}")
            return None
        file_info = response[0]
        download_link = file_info["links"]["download"]
        try:
            download_response = requests.get(download_link)
            download_response.raise_for_status()
            file_content = download_response.content
            md5sum = hashlib.md5(file_content).hexdigest()
            logger.info(f"MD5 checksum of remote file: {md5sum}")
            return md5sum
        except requests.RequestException as e:
            logger.error(f"Error downloading file from deposition {deposition_id}: {e}")
            return None

    def create_new_version(self, deposition_id: str) -> str:  # noqa: D102
        url = f"{self.deposition_url}/{deposition_id}/actions/newversion"
        response = self._request("POST", url, data="{}")
        latest_draft_url = response["links"]["latest_draft"]
        new_deposition_id = latest_draft_url.rstrip("/").split("/")[-1]
        logger.info(f"Created new version with deposition ID: {new_deposition_id}")
        return new_deposition_id

    def create_new_deposition(self) -> str:  # noqa: D102
        url = self.deposition_url
        response = self._request("POST", url, data="{}")
        deposition_id = response["id"]
        logger.info(f"Created new deposition with ID: {deposition_id}")
        return str(deposition_id)

    def get_bucket_url(self, deposition_id: str) -> str:  # noqa: D102
        url = f"{self.deposition_url}/{deposition_id}"
        response = self._request("GET", url)
        bucket_url = response["links"]["bucket"]
        logger.info(f"Bucket URL: {bucket_url}")
        return bucket_url

    def upload_file(self, deposition_id: str, file_path: str) -> dict:  # noqa: D102
        bucket_url = self.get_bucket_url(deposition_id)
        filename = Path.name(file_path)
        upload_url = f"{bucket_url}/{filename}"
        params = {"access_token": self.access_token}
        try:
            with Path.open(file_path, "rb") as fp:
                response = requests.put(upload_url, data=fp, params=params)
                response.raise_for_status()
                logger.info(f"Uploaded file {filename} to deposition {deposition_id}")
                return response.json()
        except requests.RequestException as e:
            logger.error(f"Error uploading file {filename}: {e}")
            raise

    def upload_metadata(self, deposition_id: str, metadata: dict) -> dict:  # noqa: D102
        url = f"{self.deposition_url}/{deposition_id}"
        data = {"metadata": metadata}
        data_json = json.dumps(data)
        response = self._request("PUT", url, data=data_json)
        logger.info(f"Uploaded metadata to deposition {deposition_id}")
        return response

    def publish_deposition(self, deposition_id: str) -> dict:  # noqa: D102
        url = f"{self.deposition_url}/{deposition_id}/actions/publish"
        response = self._request("POST", url, data="{}")
        logger.info(f"Published deposition {deposition_id}")
        return response


def compute_etags_hash_from_urls(csv_file: str) -> str:  # noqa: D103
    etag_values = ""
    try:
        with Path.open(csv_file, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                url = row["url"]
                try:
                    response = requests.head(url, allow_redirects=True, timeout=10)
                    response.raise_for_status()
                    etag = response.headers.get("ETag", "").strip('"')
                    etag_values += etag
                except requests.RequestException as e:
                    logger.error(f"Error fetching ETag for URL {url}: {e}")
                    raise
    except FileNotFoundError as e:
        logger.error(f"CSV file not found: {e}")
        raise
    md5sum = hashlib.md5(etag_values.encode("utf-8")).hexdigest()
    logger.info(f"MD5 checksum of S3 ETags: {md5sum}")
    return md5sum


def compute_local_etags_hash(csv_file: str) -> str:  # noqa: D103
    etag_values = ""
    try:
        with Path.open(csv_file, newline="") as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                etag = row.get("etag", "")
                etag_values += etag
    except FileNotFoundError as e:
        logger.error(f"CSV file not found: {e}")
        raise
    md5sum = hashlib.md5(etag_values.encode("utf-8")).hexdigest()
    logger.info(f"MD5 checksum of local ETags: {md5sum}")
    return md5sum


def compute_file_md5sum(file_path: str) -> str:  # noqa: D103
    md5_hash = hashlib.md5()
    try:
        with Path.open(file_path, "rb") as f:
            for byte_block in iter(lambda: f.read(4096), b""):
                md5_hash.update(byte_block)
    except FileNotFoundError as e:
        logger.error(f"File not found: {e}")
        raise
    md5sum = md5_hash.hexdigest()
    logger.info(f"MD5 checksum of file {file_path}: {md5sum}")
    return md5sum


def parse_arguments() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(description="Upload index to Zenodo")
    parser.add_argument(
        "--original-id", type=str, default="13146273", help="Original deposition ID"
    )
    parser.add_argument(
        "--file", type=str, default="manifests/profile_index.csv", help="File to upload"
    )
    return parser.parse_args()


def get_zenodo_token() -> str:
    """Retrieve the Zenodo access token from environment variables."""
    zenodo_token = os.getenv("ZENODO_TOKEN")
    if not zenodo_token:
        logger.error(
            "Access token not available. Set the ZENODO_TOKEN environment variable."
        )
        sys.exit(1)
    logger.info("Access token found.")
    return zenodo_token


def check_etags(file_to_version: str) -> None:
    """Check that S3 ETags match their local counterpart."""
    logger.info("Checking that S3 ETags match their local counterpart")
    try:
        s3_etags_hash = compute_etags_hash_from_urls(file_to_version)
        local_etags_hash = compute_local_etags_hash(file_to_version)
    except Exception as e:
        logger.error(f"Failed to compute ETag hashes: {e}")
        sys.exit(1)

    logger.info(f"Remote {s3_etags_hash} vs Local {local_etags_hash} values")
    if s3_etags_hash != local_etags_hash:
        logger.error("At least one ETag does not match its URL.")
        sys.exit(1)


def get_deposition_id(
    zenodo_client: ZenodoClient, original_id: Optional[str], file_to_version: str
) -> str:
    """Get the deposition ID, creating a new one if necessary."""
    if not original_id:
        logger.info("Creating new deposition")
        deposition_id = zenodo_client.create_new_deposition()
    else:
        logger.info("Previous ID Exists")
        latest_id = get_latest_deposition(zenodo_client, original_id)
        if not is_file_changed(zenodo_client, latest_id, file_to_version):
            logger.info("The URLs and md5sums have not changed. No update needed.")
            sys.exit(0)
        deposition_id = create_new_version(zenodo_client, latest_id)
    logger.info(f"New deposition ID is {deposition_id}")
    return deposition_id


def get_latest_deposition(zenodo_client: ZenodoClient, original_id: str) -> str:
    """Retrieve the latest deposition ID."""
    try:
        latest_id = zenodo_client.get_latest_deposition_id(original_id)
        return latest_id
    except Exception as e:
        logger.error(f"Error retrieving latest deposition ID: {e}")
        sys.exit(1)


def is_file_changed(
    zenodo_client: ZenodoClient, latest_id: str, file_to_version: str
) -> bool:
    """Check if the local file has changed compared to the remote file."""
    try:
        remote_hash = zenodo_client.get_file_md5sum(latest_id)
        if remote_hash is None:
            logger.warning("Remote file not found or empty deposition.")
            remote_hash = ""
    except Exception as e:
        logger.error(f"Error retrieving remote hash: {e}")
        sys.exit(1)

    try:
        local_hash = compute_file_md5sum(file_to_version)
    except Exception as e:
        logger.error(f"Error computing local file hash: {e}")
        sys.exit(1)

    logger.info(
        f"Checking for changes in file contents: Remote {remote_hash} vs Local {local_hash}"  # noqa: E501
    )
    return remote_hash != local_hash


def create_new_version(zenodo_client: ZenodoClient, latest_id: str) -> str:
    """Create a new version of the deposition."""
    logger.info("Creating new version")
    try:
        deposition_id = zenodo_client.create_new_version(latest_id)
        return deposition_id
    except Exception as e:
        logger.error(f"Error creating new version: {e}")
        sys.exit(1)


def upload_file_and_metadata(
    zenodo_client: ZenodoClient, deposition_id: str, file_to_version: str
) -> None:
    """Upload the file and metadata to Zenodo."""
    # Upload file
    logger.info("Uploading file")
    try:
        zenodo_client.upload_file(deposition_id, file_to_version)
    except Exception as e:
        logger.error(f"Error uploading file: {e}")
        sys.exit(1)

    # Upload Metadata
    metadata = {
        "title": "The Joint Undertaking for Morphological Profiling (JUMP) Consortium Datasets Index",  # noqa: E501
        "creators": [{"name": "The JUMP Cell Painting Consortium"}],
        "upload_type": "dataset",
        "access_right": "open",
    }
    logger.info("Uploading metadata")
    try:
        zenodo_client.upload_metadata(deposition_id, metadata)
    except Exception as e:
        logger.error(f"Error uploading metadata: {e}")
        sys.exit(1)


def publish_deposition(zenodo_client: ZenodoClient, deposition_id: str) -> None:
    """Publish the deposition on Zenodo."""
    logger.info("Publishing deposition")
    try:
        zenodo_client.publish_deposition(deposition_id)
        logger.info(f"Deposition {deposition_id} published successfully.")
    except Exception as e:
        logger.error(f"Error publishing deposition: {e}")
        sys.exit(1)


def main() -> None:
    """Upload index to Zenodo."""
    zenodo_token = get_zenodo_token()
    args = parse_arguments()

    zenodo_endpoint = "https://zenodo.org"
    original_id = args.original_id
    file_to_version = args.file

    check_etags(file_to_version)

    zenodo_client = ZenodoClient(zenodo_token, endpoint=zenodo_endpoint)
    deposition_id = get_deposition_id(zenodo_client, original_id, file_to_version)
    upload_file_and_metadata(zenodo_client, deposition_id, file_to_version)
    publish_deposition(zenodo_client, deposition_id)


if __name__ == "__main__":
    main()


if __name__ == "__main__":
    main()
