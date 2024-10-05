"""Data versioner."""

import csv
import hashlib
import logging
import os
from typing import List, Optional
from pathlib import Path

import requests

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


class ZenodoError(Exception):
    """Custom exception for Zenodo-related errors."""

    pass


class ZenodoClient:  # noqa: D101
    ZENODO_ENDPOINT = "https://zenodo.org"
    DEPOSITION_PREFIX = f"{ZENODO_ENDPOINT}/api/deposit/depositions"

    def __init__(self, token: Optional[str] = None):
        self.token = token or os.environ.get("ZENODO_TOKEN")
        if not self.token:
            logger.error("Zenodo access token not available.")
            raise ZenodoError("Zenodo access token not available.")
        logger.info("Zenodo access token found.")

    def load_manifest(self, file_path: str) -> List[dict]:
        """
        Load the CSV manifest file.

        Args:
            file_path (str): Path to the CSV manifest.

        Returns:
            List[dict]: List of records with 'url' and 'etag'.
        """
        records = []
        try:
            with Path.open(file_path, "r", newline="", encoding="utf-8") as csvfile:
                reader = csv.DictReader(csvfile)
                for row in reader:
                    records.append(
                        {
                            "url": row["URL"],  # Adjust the key based on CSV headers
                            "etag": row["ETag"],  # Adjust the key based on CSV headers
                        }
                    )
            logger.info(f"Loaded {len(records)} records from manifest.")
        except Exception as e:
            logger.error(f"Error reading CSV file {file_path}: {e}")
            raise ZenodoError(f"Error reading CSV file {file_path}: {e}")
        return records

    def fetch_remote_etags(self, urls: List[str]) -> List[str]:
        """
        Fetch ETag headers from the provided URLs.

        Args:
            urls (List[str]): List of URLs to fetch ETags from.

        Returns:
            List[str]: List of ETags.
        """
        s3_etags = []
        for url in urls:
            try:
                response = requests.head(url)
                response.raise_for_status()
                etag = response.headers.get("ETag", "").strip('"')
                s3_etags.append(etag)
                logger.debug(f"Fetched ETag for {url}: {etag}")
            except requests.RequestException as e:
                logger.error(f"Error fetching ETag for URL {url}: {e}")
                raise ZenodoError(f"Error fetching ETag for URL {url}: {e}")
        logger.info("Fetched all remote ETags successfully.")
        return s3_etags

    def compute_md5(self, values: List[str]) -> str:
        """
        Compute MD5 checksum of concatenated strings.

        Args:
            values (List[str]): List of strings to concatenate and hash.

        Returns:
            str: MD5 checksum.
        """
        concatenated = "".join(values)
        md5_hash = hashlib.md5(concatenated.encode("utf-8")).hexdigest()
        logger.debug(f"Computed MD5: {md5_hash} for concatenated values.")
        return md5_hash

    def compare_etags(self, local_etags: List[str], remote_etags: List[str]) -> bool:
        """
        Compare local and remote ETag MD5 checksums.

        Args:
            local_etags (List[str]): Local ETags.
            remote_etags (List[str]): Remote ETags.

        Returns:
            bool: True if they match, False otherwise.
        """
        local_md5 = self.compute_md5(local_etags)
        remote_md5 = self.compute_md5(remote_etags)
        logger.info(f"Remote MD5: {remote_md5} vs Local MD5: {local_md5}")
        return local_md5 == remote_md5

    def get_latest_deposition_id(self, original_id: str) -> str:
        """
        Get the latest deposition ID from an original record.

        Args:
            original_id (str): Original Zenodo record ID.

        Returns:
            str: Latest deposition ID.
        """
        latest_url = f"{self.ZENODO_ENDPOINT}/api/records/{original_id}/versions/latest"
        try:
            response = requests.get(latest_url, params={"access_token": self.token})
            response.raise_for_status()
            data = response.json()
            latest_id = str(data["id"])
            logger.info(f"Latest deposition ID: {latest_id}")
            return latest_id
        except (requests.RequestException, KeyError) as e:
            logger.error(f"Error fetching latest deposition ID: {e}")
            raise ZenodoError(f"Error fetching latest deposition ID: {e}")

    def get_remote_file_hash(self, deposition_id: str, filename: str) -> str:
        """
        Download the remote file and compute its MD5 hash.

        Args:
            deposition_id (str): Deposition ID.
            filename (str): Filename to download.

        Returns:
            str: MD5 hash of the remote file.
        """
        files_url = f"{self.DEPOSITION_PREFIX}/{deposition_id}/files"
        try:
            response = requests.get(files_url, params={"access_token": self.token})
            response.raise_for_status()
            files_data = response.json()
            remote_file_url = next(
                (
                    f["links"]["download"]
                    for f in files_data
                    if f["filename"] == filename
                ),
                None,
            )
            if not remote_file_url:
                logger.error(
                    f"File {filename} not found in deposition {deposition_id}."
                )
                raise ZenodoError(
                    f"File {filename} not found in deposition {deposition_id}."
                )

            response = requests.get(remote_file_url)
            response.raise_for_status()
            remote_content = response.content
            remote_hash = hashlib.md5(remote_content).hexdigest()
            logger.debug(f"Remote file MD5: {remote_hash}")
            return remote_hash
        except requests.RequestException as e:
            logger.error(
                f"Error fetching remote file from deposition {deposition_id}: {e}"
            )
            raise ZenodoError(
                f"Error fetching remote file from deposition {deposition_id}: {e}"
            )

    def compute_local_file_hash(self, file_path: str) -> str:
        """
        Compute the MD5 hash of a local file.

        Args:
            file_path (str): Path to the local file.

        Returns:
            str: MD5 hash of the file.
        """
        try:
            with Path.open(file_path, "rb") as f:
                content = f.read()
            local_hash = hashlib.md5(content).hexdigest()
            logger.debug(f"Local file MD5: {local_hash}")
            return local_hash
        except Exception as e:
            logger.error(f"Error computing MD5 for {file_path}: {e}")
            raise ZenodoError(f"Error computing MD5 for {file_path}: {e}")

    def create_new_deposition(self, deposition_endpoint: str) -> str:
        """
        Create a new deposition.

        Args:
            deposition_endpoint (str): Deposition API endpoint.

        Returns:
            str: New deposition ID.
        """
        try:
            headers = {"Content-Type": "application/json"}
            response = requests.post(
                f"{deposition_endpoint}?access_token={self.token}",
                headers=headers,
                json={},
            )
            response.raise_for_status()
            data = response.json()
            deposition_id = str(data["id"])
            logger.info(f"Created new deposition with ID: {deposition_id}")
            return deposition_id
        except (requests.RequestException, KeyError) as e:
            logger.error(f"Error creating new deposition: {e}")
            raise ZenodoError(f"Error creating new deposition: {e}")

    def get_bucket_url(self, deposition_id: str) -> str:
        """
        Get the bucket URL for file uploads.

        Args:
            deposition_id (str): Deposition ID.

        Returns:
            str: Bucket URL.
        """
        try:
            response = requests.get(
                f"{self.DEPOSITION_PREFIX}/{deposition_id}",
                params={"access_token": self.token},
            )
            response.raise_for_status()
            data = response.json()
            bucket_url = data["links"]["bucket"]
            if not bucket_url:
                logger.error(f"Bucket URL not found for deposition {deposition_id}.")
                raise ZenodoError(
                    f"Bucket URL not found for deposition {deposition_id}."
                )
            logger.debug(f"Bucket URL: {bucket_url}")
            return bucket_url
        except (requests.RequestException, KeyError) as e:
            logger.error(
                f"Error getting bucket URL for deposition {deposition_id}: {e}"
            )
            raise ZenodoError(
                f"Error getting bucket URL for deposition {deposition_id}: {e}"
            )

    def upload_file(self, bucket_url: str, file_path: str, filename: str) -> None:
        """
        Upload a file to the specified bucket.

        Args:
            bucket_url (str): Bucket URL.
            file_path (str): Path to the local file.
            filename (str): Filename to use in the bucket.
        """
        try:
            with Path.open(file_path, "rb") as fp:
                data = fp.read()
            headers = {"Content-Type": "application/octet-stream"}
            params = {"access_token": self.token}
            upload_url = f"{bucket_url}/{filename}"
            response = requests.put(
                upload_url, params=params, data=data, headers=headers
            )
            if response.status_code not in (200, 201):
                logger.error(
                    f"Error uploading file: {response.status_code} {response.text}"
                )
                raise ZenodoError(
                    f"Error uploading file: {response.status_code} {response.text}"
                )
            logger.info(f"Uploaded file {filename} to bucket.")
        except requests.RequestException as e:
            logger.error(f"Error uploading file {filename}: {e}")
            raise ZenodoError(f"Error uploading file {filename}: {e}")
        except Exception as e:
            logger.error(f"Error reading file {file_path}: {e}")
            raise ZenodoError(f"Error reading file {file_path}: {e}")

    def update_metadata(self, deposition_id: str, metadata: dict) -> None:
        """
        Update metadata for a deposition.

        Args:
            deposition_id (str): Deposition ID.
            metadata (dict): Metadata dictionary.
        """
        try:
            endpoint = f"{self.DEPOSITION_PREFIX}/{deposition_id}"
            headers = {"Content-Type": "application/json"}
            params = {"access_token": self.token}
            response = requests.put(
                endpoint, params=params, json=metadata, headers=headers
            )
            if response.status_code != 200:
                logger.error(
                    f"Error updating metadata: {response.status_code} {response.text}"
                )
                raise ZenodoError(
                    f"Error updating metadata: {response.status_code} {response.text}"
                )
            logger.info("Metadata updated successfully.")
        except requests.RequestException as e:
            logger.error(f"Error updating metadata: {e}")
            raise ZenodoError(f"Error updating metadata: {e}")

    def publish_deposition(self, deposition_id: str) -> None:
        """
        Publish a deposition.

        Args:
            deposition_id (str): Deposition ID.
        """
        try:
            publish_url = f"{self.DEPOSITION_PREFIX}/{deposition_id}/actions/publish"
            headers = {"Content-Type": "application/json"}
            params = {"access_token": self.token}
            response = requests.post(
                publish_url, params=params, json={}, headers=headers
            )
            if response.status_code != 202:
                logger.error(
                    f"Error publishing deposition: {response.status_code} {response.text}"
                )
                raise ZenodoError(
                    f"Error publishing deposition: {response.status_code} {response.text}"
                )
            data = response.json()
            logger.info(f"Published deposition ID: {data['id']}")
        except (requests.RequestException, KeyError) as e:
            logger.error(f"Error publishing deposition: {e}")
            raise ZenodoError(f"Error publishing deposition: {e}")

    def process_deposition(
        self,
        manifest_path: str,
        original_id: Optional[str] = None,
        metadata: Optional[dict] = None,
    ) -> None:
        """
        Process the deposition workflow.

        Args:
            manifest_path (str): Path to the CSV manifest.
            original_id (Optional[str]): Original Zenodo record ID.
            metadata (Optional[dict]): Metadata to update.
        """
        records = self.load_manifest(manifest_path)
        urls = [record["url"] for record in records]
        local_etags = [record["etag"] for record in records]

        remote_etags = self.fetch_remote_etags(urls)
        if not self.compare_etags(local_etags, remote_etags):
            logger.error("ETag mismatch detected.")
            raise ZenodoError("At least one ETag does not match its URL.")

        filename = Path.name(manifest_path)

        if original_id:
            logger.info("Original deposition ID provided. Checking for updates.")
            latest_id = self.get_latest_deposition_id(original_id)
            remote_hash = self.get_remote_file_hash(latest_id, filename)
            local_hash = self.compute_local_file_hash(manifest_path)

            logger.info(
                f"Remote file MD5: {remote_hash} vs Local file MD5: {local_hash}"
            )
            if remote_hash == local_hash:
                logger.info(
                    "No changes detected in the file. No new deposition created."
                )
                return  # No changes, exit gracefully

            deposition_endpoint = (
                f"{self.DEPOSITION_PREFIX}/{latest_id}/actions/newversion"
            )
            deposition_id = self.create_new_deposition(deposition_endpoint)
        else:
            logger.info(
                "No original deposition ID provided. Creating a new deposition."
            )
            deposition_id = self.create_new_deposition(self.DEPOSITION_PREFIX)

        bucket_url = self.get_bucket_url(deposition_id)
        self.upload_file(bucket_url, manifest_path, filename)

        if metadata:
            self.update_metadata(deposition_id, metadata)

        self.publish_deposition(deposition_id)
