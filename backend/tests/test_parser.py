import hashlib
from pathlib import Path

import pytest
from paperx.models import Document
from paperx.parser import ParseError, PdfPlumberParser
from pydantic import ValidationError

from scripts.generate_fixtures import generate


@pytest.fixture(scope="module")
def fixtures(tmp_path_factory):
    directory = tmp_path_factory.mktemp("pdfs")
    generate(directory)
    return directory


def test_stable_ids_and_normalized_locations(fixtures):
    parser = PdfPlumberParser()
    first = parser.parse(fixtures / "single-column.pdf")
    second = parser.parse(fixtures / "single-column.pdf")
    assert first == second
    assert len({b.id for b in first.blocks}) == len(first.blocks)
    assert (
        first.source_sha256
        == hashlib.sha256((fixtures / "single-column.pdf").read_bytes()).hexdigest()
    )
    assert [p.number for p in first.pages] == [1, 2]
    assert [s.title for s in first.sections] == ["Abstract", "1 Introduction", "2 Conclusion"]
    assert first.blocks[0].bbox.x == pytest.approx(54 / 612, abs=0.001)
    assert first.blocks[0].bbox.y == pytest.approx(0.054, abs=0.012)
    assert any("continues" in b.text and "Paragraph alpha" in b.text for b in first.blocks)


def test_obvious_two_column_order(fixtures):
    doc = PdfPlumberParser().parse(fixtures / "multi-column.pdf")
    text = "\n".join(b.text for b in doc.blocks)
    for i in range(1, 8):
        assert text.index(f"LEFT_{i}") < text.index(f"LEFT_{i + 1}")
        assert text.index(f"RIGHT_{i}") < text.index(f"RIGHT_{i + 1}")
    assert text.index("LEFT_8") < text.index("RIGHT_1")


def test_scan_is_explicit_degradation(fixtures):
    doc = PdfPlumberParser().parse(fixtures / "scan-like.pdf")
    assert not doc.blocks
    assert doc.pages[0].text_status == "missing"
    assert "ocr_not_implemented" in doc.pages[0].warnings


def test_formulas_never_fabricate_latex(fixtures):
    doc = PdfPlumberParser().parse(fixtures / "formula-dense.pdf")
    formulas = [b for b in doc.blocks if b.type == "formula"]
    assert len(formulas) == 3
    assert all(b.formula.latex is None and not b.formula.can_copy for b in formulas)
    assert [b.formula.number for b in formulas] == ["(1)", "(2)", "(3)"]


def test_rotations_preserve_unrotated_size(fixtures):
    doc = PdfPlumberParser().parse(fixtures / "rotated.pdf")
    assert [p.rotation for p in doc.pages] == [0, 90, 180, 270]
    assert all(p.width == 612 and p.height == 792 for p in doc.pages)


def test_chinese_text_layer(fixtures):
    doc = PdfPlumberParser().parse(fixtures / "paired-zh.pdf")
    assert "合成测试文档" in "".join(b.text for b in doc.blocks)


def test_malformed_and_encrypted_pdf(tmp_path, fixtures):
    from pypdf import PdfReader, PdfWriter

    for name, body in [("bad.pdf", b"not pdf"), ("truncated.pdf", b"%PDF-1.7\nnot valid")]:
        file = tmp_path / name
        file.write_bytes(body)
        with pytest.raises(ParseError):
            PdfPlumberParser().parse(file)
    writer = PdfWriter()
    writer.add_page(PdfReader(fixtures / "single-column.pdf").pages[0])
    writer.encrypt("private-test-password")
    encrypted = tmp_path / "encrypted.pdf"
    writer.write(encrypted)
    with pytest.raises(ParseError):
        PdfPlumberParser().parse(encrypted)


def test_dangling_references_rejected(fixtures):
    value = PdfPlumberParser().parse(fixtures / "single-column.pdf").model_dump()
    value["sections"][0]["block_id"] = "absent"
    with pytest.raises(ValidationError):
        Document.model_validate(value)


def test_user_transformer_if_available():
    source = Path(__file__).resolve().parents[2] / "paper/nlp/Attention Is All You Need.pdf"
    if not source.exists():
        pytest.skip("User PDF is intentionally not redistributed")
    doc = PdfPlumberParser().parse(source)
    assert len(doc.pages) == 15
    page_one = "\n".join(b.text for b in doc.blocks if b.page == 1)
    assert "Attention Is All You Need" in page_one
    assert "The dominant sequence transduction models" in page_one
    assert "Transformer, based solely on attention mechanisms" in page_one
    assert "English-to-German" in page_one
    assert "7v26730" not in page_one
    assert "6071" not in page_one
    assert "Transformer, . based" not in page_one
    assert any("vertical_text_excluded" in p.warnings for p in doc.pages)
    assert any(s.title == "Abstract" for s in doc.sections)

    headings = []

    def collect(sections):
        for section in sections:
            headings.append(section.title)
            collect(section.children)

    collect(doc.sections)
    assert "1 Introduction" in headings
    assert "3 Model Architecture" in headings
