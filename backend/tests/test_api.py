import json

import pytest
from fastapi.testclient import TestClient
from paperx.api import create_app
from paperx.models import Paper, Sample
from paperx.parser import PdfPlumberParser

from scripts.generate_fixtures import generate


@pytest.fixture
def client(tmp_path):
    generate(tmp_path / "fixtures")
    doc = PdfPlumberParser().parse(tmp_path / "fixtures" / "single-column.pdf")
    folder = tmp_path / "samples" / "single-column"
    folder.mkdir(parents=True)
    (folder / "original.pdf").write_bytes((tmp_path / "fixtures/single-column.pdf").read_bytes())
    (folder / "document.json").write_text(doc.model_dump_json(), encoding="utf-8")
    sample = Sample(
        id="single-column",
        paper=Paper(
            id=doc.paper_id,
            title="Test",
            source="fixture",
            source_sha256=doc.source_sha256,
            page_count=len(doc.pages),
            parser_version=doc.parser_version,
            original_pdf_url="/samples/single-column/pdf",
        ),
        label="Test",
        synthetic=True,
    )
    (folder / "sample.json").write_text(sample.model_dump_json(), encoding="utf-8")
    return TestClient(create_app(tmp_path / "samples"))


def test_health_and_contract(client):
    assert client.get("/health").json()["stage"] == 0
    assert len(client.get("/samples").json()) == 1
    sample = client.get("/samples").json()[0]
    assert (
        sample["paper"]["id"] == client.get(f"/samples/{sample['id']}/document").json()["paper_id"]
    )
    assert client.get("/samples/single-column/document").json()["blocks"]
    schema = client.get("/openapi.json").json()
    assert "Document" in schema["components"]["schemas"]


def test_pdf_range(client):
    response = client.get("/samples/single-column/pdf", headers={"Range": "bytes=0-4"})
    assert response.status_code == 206
    assert response.content == b"%PDF-"
    assert response.headers["content-range"].startswith("bytes 0-4/")


def test_error_and_path_traversal(client):
    for route in ["/missing", "/samples/nope/document", "/samples/a%5Cb/pdf"]:
        response = client.get(route)
        assert response.status_code == 404
        assert set(response.json()) == {"error"}
        assert response.json()["error"]["code"] == "NOT_FOUND"
    assert "sk-" not in json.dumps(client.get("/openapi.json").json())


def test_empty_samples(tmp_path):
    assert TestClient(create_app(tmp_path)).get("/samples").json() == []


def test_range_suffix_and_bounds(client):
    full = client.get("/samples/single-column/pdf").content
    suffix = client.get("/samples/single-column/pdf", headers={"Range": "bytes=-10"})
    assert suffix.status_code == 206
    assert suffix.content == full[-10:]
    invalid = client.get("/samples/single-column/pdf", headers={"Range": "bytes=9999999-"})
    assert invalid.status_code == 416
    assert invalid.headers["content-range"] == f"bytes */{len(full)}"
