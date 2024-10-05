"""Handles the uploading of dataset indices."""

import argparse
import sys

from .zenodo_client import ZenodoClient, ZenodoError
import logging

# Configure logging for the script
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def main() -> None:  # noqa: D103
    parser = argparse.ArgumentParser(description="Upload a dataset index to Zenodo.")
    parser.add_argument(
        "manifest_path", type=str, help="Path to the CSV manifest file."
    )
    parser.add_argument(
        "--original_id",
        type=str,
        default=None,
        help="Original Zenodo record ID for updating an existing deposition.",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="The Joint Undertaking for Morphological Profiling (JUMP) Consortium Datasets Index",  # noqa: E501
        help="Title for the Zenodo deposition.",
    )
    parser.add_argument(
        "--creators",
        type=str,
        default="The JUMP Cell Painting Consortium",
        help="Creators of the dataset.",
    )
    parser.add_argument(
        "--upload_type",
        type=str,
        default="dataset",
        help="Upload type for the deposition.",
    )
    parser.add_argument(
        "--access_right",
        type=str,
        default="open",
        help="Access rights for the deposition.",
    )

    args = parser.parse_args()

    # Prepare metadata
    metadata = {
        "metadata": {
            "title": args.title,
            "creators": [
                {"name": creator.strip()} for creator in args.creators.split(",")
            ],
            "upload_type": args.upload_type,
            "access_right": args.access_right,
        }
    }

    try:
        client = ZenodoClient()  # Ensure ZENODO_TOKEN is set in environment variables
        client.process_deposition(
            manifest_path=args.manifest_path,
            original_id=args.original_id,
            metadata=metadata,
        )
    except ZenodoError as e:
        logger.error(f"An error occurred: {e}")
        sys.exit(1)
