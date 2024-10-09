"""Unit tests for `update_etags`."""

from pathlib import Path

import requests_mock

from dataset_versioner.update_etags import fetch_etag, update_etags


def test_fetch_etag_success() -> None:  # noqa: D103
    url = "http://example.com/file"
    expected_etag = "1234567890abcdef"

    with requests_mock.Mocker() as m:
        m.head(url, headers={"ETag": expected_etag})
        etag = fetch_etag(url)
        assert etag == expected_etag


def test_fetch_etag_no_etag() -> None:  # noqa: D103
    url = "http://example.com/file"

    with requests_mock.Mocker() as m:
        m.head(url)
        etag = fetch_etag(url)
        assert etag == ""


def test_fetch_etag_request_exception() -> None:  # noqa: D103
    url = "http://example.com/file"

    with requests_mock.Mocker() as m:
        m.head(url, status_code=404)
        etag = fetch_etag(url)
        assert etag == ""


def test_update_etags(tmp_path: Path) -> None:  # noqa: D103
    input_csv_content = """name,url
file1,http://example.com/file1
file2,http://example.com/file2
"""
    expected_csv_content = """name,url,etag
file1,http://example.com/file1,etag1
file2,http://example.com/file2,etag2
"""

    input_csv_path = tmp_path / "input.csv"
    output_csv_path = tmp_path / "output.csv"

    input_csv_path.write_text(input_csv_content)

    with requests_mock.Mocker() as m:
        m.head("http://example.com/file1", headers={"ETag": "etag1"})
        m.head("http://example.com/file2", headers={"ETag": "etag2"})

        update_etags(str(input_csv_path), str(output_csv_path))

        content = output_csv_path.read_text()
        assert content.strip() == expected_csv_content.strip()
