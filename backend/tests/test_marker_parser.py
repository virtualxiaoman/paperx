import hashlib
import json
import os
import tempfile
from pathlib import Path

import pytest
from paperx.marker_parser import BlockHTML, MarkerParser
from paperx.parser import ParseError
from pypdf import PdfWriter

from scripts.marker_worker import configure_model_cache
from scripts.prepare_samples import archive_previous


def source(tmp_path, rotation=0, crop=False):
    path = tmp_path / "source.pdf"
    writer = PdfWriter()
    page = writer.add_blank_page(width=600, height=800)
    page.rotate(rotation)
    if crop:
        page.cropbox.lower_left = (60, 80)
        page.cropbox.upper_right = (540, 720)
    writer.write(path)
    return path


def block(kind="Text", html="<p>A complete paragraph.</p>", index=0):
    return {
        "id": f"/page/0/{kind}/{index}",
        "block_type": kind,
        "bbox": [60, 160, 300, 320],
        "html": html,
        "children": None,
    }


def output(path, blocks=None):
    return {
        "paperx_provenance": {
            "source_sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            "marker_version": "1.9.3",
            "worker_revision": 1,
        },
        "children": [
            {
                "id": "/page/0/Page",
                "bbox": [0, 0, 600, 800],
                "children": blocks if blocks is not None else [block()],
            }
        ],
    }


def test_group_order_headers_formula_and_safe_text(tmp_path):
    pdf = source(tmp_path)
    nodes = [
        block("PageHeader", "arXiv:1706.03762"),
        block("SectionHeader", "<h2>Architecture &amp; attention</h2>"),
        {
            "children": [block(), block("Text", "<p>Second paragraph.</p>", 1)],
            "html": "<content-ref>duplicate group text</content-ref>",
        },
        block("Equation", r'<math display="block">\frac{QK^T}{\sqrt{d_k}}</math>'),
        block("Picture", ""),
        {
            **block("Table", "<table><tr><td>A</td><td>B</td></tr></table>"),
            "children": [block("TableCell", "<td>A</td>"), block("TableCell", "<td>B</td>", 1)],
        },
        block("PageFooter", "1"),
    ]
    parser = MarkerParser()
    document = parser.from_json(pdf, output(pdf, nodes))
    assert [b.type for b in document.blocks] == [
        "heading",
        "paragraph",
        "paragraph",
        "formula",
        "figure",
        "table",
    ]
    assert document.sections[0].level == 2
    assert document.sections[0].title == "Architecture & attention"
    formula = document.blocks[3].formula
    assert formula.latex == r"\frac{QK^T}{\sqrt{d_k}}"
    assert formula.status == "needs_review"
    assert not formula.can_copy
    assert document.blocks[-1].text == "A B"
    assert document == parser.from_json(pdf, output(pdf, nodes))
    html = BlockHTML()
    html.feed("<p>Hello <script>bad()</script>&lt;world&gt;</p>")
    assert html.text == "Hello <world>"


def test_multiple_math_elements_stay_separate(tmp_path):
    pdf = source(tmp_path)
    html = r'<math>x &lt; y</math><math>z = \sin(x)</math>'
    formula = MarkerParser().from_json(pdf, output(pdf, [block("Equation", html)])).blocks[0]
    assert formula.formula.latex == "x < y\nz = \\sin(x)"
    assert formula.text == r"x < y z = \sin(x)"
    assert not formula.formula.can_copy


def test_all_model_caches_are_project_local(tmp_path, monkeypatch):
    keys = [
        "HF_HOME", "HF_HUB_CACHE", "HUGGINGFACE_HUB_CACHE", "HF_ASSETS_CACHE",
        "TRANSFORMERS_CACHE", "MODEL_CACHE_DIR", "TORCH_HOME", "HF_XET_CACHE",
        "TORCHINDUCTOR_CACHE_DIR", "TRITON_CACHE_DIR", "XDG_CACHE_HOME", "TMP", "TEMP",
        "HF_HUB_DISABLE_TELEMETRY", "PDFTEXT_CPU_WORKERS",
    ]
    for key in keys:
        monkeypatch.setenv(key, "external-cache")
    monkeypatch.setattr(tempfile, "tempdir", None)
    cache = configure_model_cache(tmp_path)
    assert cache == tmp_path / "model"
    for key in keys[:-2]:
        assert Path(os.environ[key]).is_relative_to(cache)
    assert Path(tempfile.gettempdir()) == cache / "tmp"


@pytest.mark.parametrize(
    "rotation,expected",
    [
        (0, (0.1, 0.2, 0.4, 0.2)),
        (90, (0.2, 0.5, 0.2, 0.4)),
        (180, (0.5, 0.6, 0.4, 0.2)),
        (270, (0.6, 0.1, 0.2, 0.4)),
    ],
)
def test_display_coordinates_unrotate(tmp_path, rotation, expected):
    pdf = source(tmp_path, rotation)
    box = MarkerParser().from_json(pdf, output(pdf)).blocks[0].bbox
    assert (box.x, box.y, box.width, box.height) == pytest.approx(expected)


def test_crop_and_figure_only_page(tmp_path):
    pdf = source(tmp_path, crop=True)
    document = MarkerParser().from_json(pdf, output(pdf, [block("Picture", "")]))
    box = document.blocks[0].bbox
    assert (box.x, box.y, box.width, box.height) == pytest.approx((0.18, 0.26, 0.32, 0.16))
    assert document.pages[0].text_status == "missing"
    assert "cropbox_coordinates_mapped" in document.pages[0].warnings


@pytest.mark.parametrize(
    "field,value", [("source_sha256", "wrong"), ("marker_version", "2.0.0"), ("worker_revision", 0)]
)
def test_provenance_rejected(tmp_path, field, value):
    pdf = source(tmp_path)
    raw = output(pdf)
    raw["paperx_provenance"][field] = value
    with pytest.raises(ParseError, match="provenance"):
        MarkerParser().from_json(pdf, raw)


def test_incomplete_and_wrong_order_rejected(tmp_path):
    pdf = source(tmp_path)
    raw = output(pdf)
    raw["children"][0]["id"] = "/page/1/Page"
    with pytest.raises(ParseError, match="order"):
        MarkerParser().from_json(pdf, raw)
    raw["children"] = []
    with pytest.raises(ParseError, match="incomplete"):
        MarkerParser().from_json(pdf, raw)


def test_cache_without_ml_install_and_malformed_cache(tmp_path):
    pdf = source(tmp_path)
    parser = MarkerParser(python=tmp_path / "absent.exe", cache_dir=tmp_path / "cache")
    with pytest.raises(ParseError, match="not installed"):
        parser.parse(pdf)
    cache = parser.cache_path(pdf)
    cache.parent.mkdir(parents=True)
    cache.write_text(json.dumps(output(pdf)), encoding="utf-8")
    assert parser.parse(pdf).blocks[0].text == "A complete paragraph."
    cache.write_text("{", encoding="utf-8")
    with pytest.raises(ParseError, match="Invalid Marker cache"):
        parser.parse(pdf)


def test_encrypted_preflight_does_not_launch_worker(tmp_path):
    pdf = source(tmp_path)
    writer = PdfWriter(pdf)
    writer.encrypt("password")
    writer.write(pdf)
    with pytest.raises(ParseError, match="Encrypted"):
        MarkerParser(python=tmp_path / "absent.exe").parse(pdf)


def test_lineage_preserved_on_cached_regeneration(tmp_path):
    pdf = source(tmp_path)
    document = MarkerParser().from_json(pdf, output(pdf))
    old = document.model_copy(deep=True)
    old.parser_version = "legacy"
    old.blocks[0].id = "old-anchor"
    (tmp_path / "document.json").write_text(old.model_dump_json(), encoding="utf-8")
    archive_previous(tmp_path, document)
    assert document.previous_id_map == {"old-anchor": [document.blocks[0].id]}
    assert document.previous_parser_version == "legacy"
    (tmp_path / "document.json").write_text(document.model_dump_json(), encoding="utf-8")
    repeat = MarkerParser().from_json(pdf, output(pdf))
    archive_previous(tmp_path, repeat)
    assert repeat == document
    assert len(list((tmp_path / "history").glob("*.document.json"))) == 1


def test_degenerate_bounds_rejected(tmp_path):
    pdf = source(tmp_path)
    raw = output(pdf)
    raw["children"][0]["children"][0]["bbox"] = [0, 0, 0, 0]
    with pytest.raises(ParseError, match="Degenerate"):
        MarkerParser().from_json(pdf, raw)


def test_local_transformer_cache_regression():
    from paperx.config import ROOT

    pdf = ROOT / "paper/nlp/Attention Is All You Need.pdf"
    parser = MarkerParser()
    if not pdf.exists() or not parser.cache_path(pdf).exists():
        pytest.skip("Local Marker paper/cache not available; never download in tests")
    document = parser.parse(pdf)
    assert len(document.pages) == 15
    abstract = [
        b
        for b in document.blocks
        if b.page == 1 and b.text.startswith("The dominant sequence transduction models")
    ]
    assert len(abstract) == 1
    assert "7v26730" not in abstract[0].text
    assert "41.8" in abstract[0].text
    assert "less time to train" in abstract[0].text
    assert any(b.type == "formula" for b in document.blocks)
    assert any(b.type == "figure" for b in document.blocks)
    assert any(b.type == "table" for b in document.blocks)
    assert document == parser.parse(pdf)
