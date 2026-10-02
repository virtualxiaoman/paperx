"""Export deterministic local samples, contracts and parser-comparison evidence."""

import argparse
import json
import shutil
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT))

from paperx.api import create_app  # noqa: E402
from paperx.config import Settings  # noqa: E402
from paperx.marker_parser import MarkerParser  # noqa: E402
from paperx.models import Document, Paper, Sample, Task  # noqa: E402
from paperx.parser import PdfPlumberParser  # noqa: E402
from pypdf import PdfReader  # noqa: E402

from scripts.generate_fixtures import generate  # noqa: E402


def archive_previous(folder, document):
    """Keep old anchors; only exact unique text/type matches are mapped automatically."""
    previous = folder / "document.json"
    if not previous.exists():
        return
    old = Document.model_validate_json(previous.read_text(encoding="utf-8"))
    if (
        old.parser_version == document.parser_version
        and old.source_sha256 == document.source_sha256
        and old.blocks == document.blocks
    ):
        document.previous_parser_version = old.previous_parser_version
        document.previous_id_map = old.previous_id_map.copy()
        document.warnings = list(dict.fromkeys(document.warnings + old.warnings))
        return
    if old == document:
        return
    archive = folder / "history"
    archive.mkdir(exist_ok=True)
    import hashlib

    snapshot = hashlib.sha256(previous.read_bytes()).hexdigest()[:16]
    (archive / f"{snapshot}.document.json").write_bytes(previous.read_bytes())
    sample = folder / "sample.json"
    if sample.exists():
        (archive / f"{snapshot}.sample.json").write_bytes(sample.read_bytes())
    if old.source_sha256 != document.source_sha256:
        return
    index = {}
    for block in document.blocks:
        index.setdefault((block.page, block.type, block.text), []).append(block.id)
    mapping = {
        block.id: index.get((block.page, block.type, block.text), [])
        if len(index.get((block.page, block.type, block.text), [])) == 1
        else []
        for block in old.blocks
    }
    if old.parser_version == document.parser_version and old.previous_parser_version:
        document.previous_parser_version = old.previous_parser_version
        document.previous_id_map = {
            anchor: list(dict.fromkeys(new for b in ids for new in mapping.get(b, [])))
            for anchor, ids in old.previous_id_map.items()
        }
    else:
        document.previous_parser_version = old.parser_version
        document.previous_id_map = mapping
    document.warnings.append("unmatched_previous_anchors_require_review")


def main():
    cli = argparse.ArgumentParser()
    cli.add_argument(
        "--parser",
        choices=["marker", "pdfplumber"],
        default="marker",
        help="Parser for the real paper; synthetic baseline fixtures remain legacy",
    )
    args = cli.parse_args()
    fixtures = ROOT / "tests/fixtures"
    generate(fixtures)
    baseline = PdfPlumberParser()
    real_parser = MarkerParser() if args.parser == "marker" else baseline
    sources = [(p.stem, p, True) for p in sorted(fixtures.glob("*.pdf"))]
    transformer = ROOT / "paper/nlp/Attention Is All You Need.pdf"
    if transformer.exists():
        sources.append(("transformer", transformer, False))
    report = []
    for sample_id, source, synthetic in sources:
        parser = baseline if synthetic else real_parser
        print(f"Parsing {sample_id} with {parser.version} ...", flush=True)
        started = time.perf_counter()
        document = parser.parse(source)
        elapsed = time.perf_counter() - started
        folder = Settings().samples_dir / sample_id
        folder.mkdir(parents=True, exist_ok=True)
        archive_previous(folder, document)
        shutil.copyfile(source, folder / "original.pdf")
        (folder / "document.json").write_text(document.model_dump_json(indent=2), encoding="utf-8")
        title = "Attention Is All You Need" if not synthetic else sample_id
        sample = Sample(
            id=sample_id,
            paper=Paper(
                id=document.paper_id,
                title=title,
                source="fixture" if synthetic else "local",
                source_sha256=document.source_sha256,
                page_count=len(document.pages),
                parser_version=document.parser_version,
                original_pdf_url=f"/samples/{sample_id}/pdf",
            ),
            label="合成验收样本" if synthetic else "用户提供的本地论文",
            synthetic=synthetic,
        )
        (folder / "sample.json").write_text(sample.model_dump_json(indent=2), encoding="utf-8")
        started = time.perf_counter()
        alternate = [p.extract_text() or "" for p in PdfReader(source).pages]
        report.append(
            {
                "sample": sample_id,
                "sha256": document.source_sha256,
                "pages": len(document.pages),
                "blocks": len(document.blocks),
                "sections": len(document.sections),
                "formula_candidates": sum(b.type == "formula" for b in document.blocks),
                "copyable_formulas": sum(
                    bool(b.formula and b.formula.can_copy) for b in document.blocks
                ),
                "missing_text_pages": [
                    p.number for p in document.pages if p.text_status == "missing"
                ],
                "parser_version": parser.version,
                "parser_seconds": round(elapsed, 3),
                "pypdf_seconds": round(time.perf_counter() - started, 3),
                "pypdf_text_chars": sum(map(len, alternate)),
                "stable_block_repeat": parser.parse(source).blocks == document.blocks,
            }
        )
        print(f"{sample_id}: pages={len(document.pages)}, blocks={len(document.blocks)}")
    (Settings().samples_dir.parent / "parser-comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    for name, value in [
        ("document.schema.json", Document.model_json_schema()),
        ("task.schema.json", Task.model_json_schema()),
        ("openapi.json", create_app().openapi()),
    ]:
        (ROOT / "docs/engineering" / name).write_text(
            json.dumps(value, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
        )
    print("Exported schemas and parser comparison; no external AI was called.")


if __name__ == "__main__":
    main()
