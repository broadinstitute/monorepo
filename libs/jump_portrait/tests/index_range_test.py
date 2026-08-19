from __future__ import annotations

import re
import threading
from collections.abc import Iterator
from contextlib import contextmanager
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import ClassVar, cast

import pyarrow as pa
import pyarrow.csv as pv
import pyarrow.parquet as pq
import pytest

import jump_portrait._index as index
import jump_portrait.fetch as fetch


@dataclass(frozen=True)
class HTTPRequest:
    method: str
    range_header: str | None


class RangeRequestHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    payload: ClassVar[bytes]
    requests: ClassVar[list[HTTPRequest]]

    def do_HEAD(self) -> None:
        self.requests.append(HTTPRequest("HEAD", self.headers.get("Range")))
        self.send_response(200)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Length", str(len(self.payload)))
        self.end_headers()

    def do_GET(self) -> None:
        range_header = self.headers.get("Range")
        self.requests.append(HTTPRequest("GET", range_header))
        if range_header is None:
            self.send_error(412, "A byte range is required")
            return

        match = re.fullmatch(r"bytes=(\d+)-(\d*)", range_header)
        if match is None:
            self.send_error(400, "Unsupported byte range")
            return

        start = int(match.group(1))
        requested_end = int(match.group(2)) if match.group(2) else len(self.payload) - 1
        end = min(requested_end, len(self.payload) - 1)
        if start > end:
            self.send_response(416)
            self.send_header("Content-Range", f"bytes */{len(self.payload)}")
            self.end_headers()
            return

        body = self.payload[start : end + 1]
        self.send_response(206)
        self.send_header("Accept-Ranges", "bytes")
        self.send_header("Content-Range", f"bytes {start}-{end}/{len(self.payload)}")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Connection", "close")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, format: str, *args: object) -> None:
        pass


@contextmanager
def serve_ranges(payload: bytes) -> Iterator[tuple[str, list[HTTPRequest]]]:
    requests: list[HTTPRequest] = []
    handler = type(
        "BoundRangeRequestHandler",
        (RangeRequestHandler,),
        {"payload": payload, "requests": requests},
    )
    server = ThreadingHTTPServer(("127.0.0.1", 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = cast("tuple[str, int]", server.server_address)
        yield f"http://{host}:{port}/jump_index.parquet", requests
    finally:
        server.shutdown()
        thread.join()
        server.server_close()


def make_image_index() -> pa.Table:
    row_count = 10_001
    rows: dict[str, list[str] | list[int]] = {
        "Metadata_Source": ["source_8"] + ["source_99"] * (row_count - 1),
        "Metadata_Batch": ["J3"] + ["other"] * (row_count - 1),
        "Metadata_Plate": ["A1166127"]
        + [f"plate_{row:05d}" for row in range(row_count - 1)],
        "Metadata_Well": ["A01"] + ["Z99"] * (row_count - 1),
        "Metadata_Site": [1] * row_count,
    }
    for channel in ("DNA", "RNA", "Mito", "AGP", "ER"):
        rows[f"URL_Orig{channel}"] = [
            f"s3://cellpainting-gallery/{row:05d}/{channel}.tif"
            for row in range(row_count)
        ]
    return pa.table(rows)


def parquet_bytes(table: pa.Table) -> bytes:
    sink = pa.BufferOutputStream()
    pq.write_table(table, sink, row_group_size=100)
    return sink.getvalue().to_pybytes()


def well_metadata_csv() -> pa.BufferReader:
    table = pa.table(
        {
            "Metadata_JCP2022": ["JCP2022_000001"],
            "Metadata_Source": ["source_8"],
            "Metadata_Plate": ["A1166127"],
            "Metadata_Well": ["A01"],
        }
    )
    sink = pa.BufferOutputStream()
    pv.write_csv(table, sink)
    return pa.BufferReader(sink.getvalue())


@pytest.mark.parametrize(
    ("item_name", "input_column"),
    [
        ("JCP2022_000001", "JCP2022"),
        ("MYT1", "standard_key"),
        ("CLETVKMYAXARPO-UHFFFAOYSA-N", "standard_key"),
    ],
)
def test_metadata_remote_range_scan_matches_local_index(
    item_name: str,
    input_column: str,
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = make_image_index()
    local_index = tmp_path / "local-index.parquet"
    pq.write_table(table, local_index, row_group_size=100)
    payload = parquet_bytes(table)

    monkeypatch.setattr(
        fetch.query,
        "run_query",
        lambda **kwargs: [("JCP2022_000001", item_name)],
    )
    monkeypatch.setattr(fetch, "get_table", lambda name: well_metadata_csv())
    monkeypatch.setattr(
        index,
        "retrieve",
        lambda *args, **kwargs: pytest.fail("range scan fell back to Pooch"),
    )
    monkeypatch.chdir(tmp_path)

    local_result = fetch.get_item_location_metadata(
        item_name,
        input_column=input_column,
        index_origin=local_index,
    )
    with serve_ranges(payload) as (remote_origin, requests):
        remote_result = fetch.get_item_location_metadata(
            item_name,
            input_column=input_column,
            index_origin=remote_origin,
        )

    assert remote_result.equals(local_result)
    assert remote_result.column("Metadata_Source").to_pylist() == ["source_8"]
    get_requests = [request for request in requests if request.method == "GET"]
    assert get_requests
    assert all(request.range_header is not None for request in get_requests)
    transferred_bytes = 0
    for request in get_requests:
        match = re.fullmatch(r"bytes=(\d+)-(\d*)", request.range_header or "")
        assert match is not None
        start = int(match.group(1))
        end = int(match.group(2)) if match.group(2) else len(payload) - 1
        assert start > 0 or end < len(payload) - 1
        transferred_bytes += end - start + 1
    assert transferred_bytes < len(payload)
    assert not (tmp_path / "jump_index.parquet").exists()


def test_default_index_identity_is_frozen() -> None:
    assert fetch.DEFAULT_INDEX_ORIGIN == (
        "https://d3dw4c1b79pj57.cloudfront.net/19373370/jump_index.parquet/content"
    )
    assert fetch.DEFAULT_INDEX_SIZE == 145_197_890
    assert fetch.DEFAULT_INDEX_HASH == (
        "sha256:f45ea1a5de091e43caf35358370abf843bd2be47b2810283fd76db472b5acc6a"
    )
