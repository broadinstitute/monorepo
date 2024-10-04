#!/usr/bin/env python3
"""Update ETags in the CSV file by fetching the ETag from each URL."""

import argparse
import csv
import logging
import pathlib
import sys

import requests

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)  # Configure as needed


def fetch_etag(url: str) -> str:
    """Fetch the ETag header from the given URL."""
    try:
        response = requests.head(url, allow_redirects=True, timeout=10)
        response.raise_for_status()
        etag = response.headers.get("ETag", "").strip('"')
        return etag
    except requests.HTTPError as http_err:
        logger.error(
            f"HTTP error fetching ETag for URL {url}: {http_err}", file=sys.stderr
        )
        return ""
    except requests.RequestException as req_err:
        logger.error(f"Error fetching ETag for URL {url}: {req_err}", file=sys.stderr)
        return ""


def update_etags(input_file: str, output_file: str) -> None:
    """Read the input CSV file, fetch ETags for each URL, and write the updated CSV."""
    with pathlib.Path.open(input_file, newline="") as csvfile_in:
        reader = csv.DictReader(csvfile_in)
        fieldnames = reader.fieldnames if reader.fieldnames else []

        # Ensure the 'etag' field exists
        if "etag" not in fieldnames:
            fieldnames.append("etag")

        rows = []
        for row in reader:
            url = row.get("url")
            if not url:
                print(f"No URL found in row: {row}", file=sys.stderr)
                row["etag"] = ""
            else:
                etag = fetch_etag(url)
                row["etag"] = etag
            rows.append(row)

    with pathlib.Path.open(output_file, "w", newline="") as csvfile_out:
        writer = csv.DictWriter(csvfile_out, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def run() -> None:
    """Update ETags in a CSV file based on URLs."""
    parser = argparse.ArgumentParser(
        description="Update ETags in CSV file based on URLs"
    )
    parser.add_argument("input_file", help="Input CSV file")
    parser.add_argument("output_file", nargs="?", help="Output CSV file")
    args = parser.parse_args()

    # Determine the output file name if not provided
    if not args.output_file:
        input_path = pathlib.Path(args.input_file)
        output_file = f"{input_path.stem}_etagged.csv"
    else:
        output_file = args.output_file

    update_etags(args.input_file, output_file)


if __name__ == "__main__":
    run()
