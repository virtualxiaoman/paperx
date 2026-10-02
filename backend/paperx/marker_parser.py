"""Marker JSON -> Paperx contracts. Marker itself runs in an isolated process."""

import hashlib
import json
import math
import os
import re
import subprocess
from html.parser import HTMLParser
from pathlib import Path

from pypdf import PdfReader

from paperx.config import ROOT
from paperx.coordinates import unrotate_bbox
from paperx.models import BBox, Block, Document, Formula, Page, Section
from paperx.parser import ParseError


class BlockHTML(HTMLParser):
    """Plain text only: never forward arbitrary PDF-derived HTML to the browser."""

    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.math = []
        self.math_parts = []
        self.in_math = False
        self.skip = 0
        self.level = None

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.skip += 1
        if tag == "math":
            self.in_math = True
            self.math_parts = []
            self.parts.append(" ")
        if re.fullmatch(r"h[1-6]", tag):
            self.level = int(tag[1])
        if tag in {"br", "p", "li", "tr", "td", "th"}:
            self.parts.append(" ")

    def handle_endtag(self, tag):
        if tag in {"script", "style"}:
            self.skip = max(0, self.skip - 1)
        if tag == "math":
            self.math.append("".join(self.math_parts).strip())
            self.in_math = False
            self.parts.append(" ")
        if tag in {"p", "li", "tr", "td", "th"}:
            self.parts.append(" ")

    def handle_data(self, data):
        if not self.skip:
            self.parts.append(data)
            if self.in_math:
                self.math_parts.append(data)

    @property
    def text(self):
        return re.sub(r"\s+", " ", "".join(self.parts)).strip()


def leaf_blocks(node):
    # Tables already expand their cells in HTML; only descend through containers.
    atomic = {
        "Text",
        "TextInlineMath",
        "SectionHeader",
        "Equation",
        "Table",
        "TableOfContents",
        "Figure",
        "Picture",
        "ListItem",
        "Code",
        "Caption",
        "Footnote",
        "PageHeader",
        "PageFooter",
    }
    if node.get("children") and node.get("block_type", "").split(".")[-1] not in atomic:
        for child in node["children"]:
            yield from leaf_blocks(child)
    else:
        yield node


class MarkerParser:
    version = "marker-1.9.3-paperx-v1"

    def __init__(self, python=None, cache_dir=None, device=None):
        self.python = Path(python or ROOT / ".venv-marker/Scripts/python.exe")
        self.cache_dir = Path(cache_dir or ROOT / "data/marker")
        self.device = device or os.environ.get("PAPERX_MARKER_DEVICE", "cuda")
        if self.device not in {"cuda", "cpu"}:
            raise ValueError("PAPERX_MARKER_DEVICE must be cuda or cpu")

    def cache_path(self, pdf_path):
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        return self.cache_dir / self.version / digest / "blocks.json"

    def parse(self, pdf_path: Path) -> Document:
        if pdf_path.stat().st_size > 50 * 1024 * 1024:
            raise ParseError("PDF exceeds the 50 MiB limit")
        if not pdf_path.read_bytes().startswith(b"%PDF-"):
            raise ParseError("File is not a PDF")
        self.read_pdf(pdf_path)
        raw_path = self.cache_path(pdf_path)
        if not raw_path.exists():
            if not self.python.exists():
                raise ParseError("Marker is not installed. Run scripts\\install-marker.bat first.")
            raw_path.parent.mkdir(parents=True, exist_ok=True)
            log_path = raw_path.parent / "worker.log"
            with log_path.open("w", encoding="utf-8") as log:
                try:
                    subprocess.run(
                        [
                            str(self.python),
                            str(ROOT / "scripts/marker_worker.py"),
                            str(pdf_path.resolve()),
                            str(raw_path.resolve()),
                            "--device",
                            self.device,
                        ],
                        cwd=ROOT,
                        stdout=log,
                        stderr=subprocess.STDOUT,
                        env={**os.environ, "PYTHONUTF8": "1", "PYTHONUNBUFFERED": "1"},
                        check=True,
                        timeout=3600,
                    )
                except (subprocess.SubprocessError, OSError) as exc:
                    raise ParseError(
                        "Marker failed; inspect data/marker worker.log. No legacy fallback used."
                    ) from exc
        try:
            return self.from_json(pdf_path, json.loads(raw_path.read_text(encoding="utf-8")))
        except (ValueError, TypeError, KeyError) as exc:
            raise ParseError(f"Invalid Marker cache: {raw_path}; regenerate it") from exc

    @staticmethod
    def read_pdf(pdf_path):
        try:
            reader = PdfReader(pdf_path)
            if reader.is_encrypted or not 1 <= len(reader.pages) <= 300:
                raise ParseError("Encrypted PDF or unsupported page count")
            return reader
        except ParseError:
            raise
        except Exception as exc:
            raise ParseError("Cannot read PDF") from exc

    def from_json(self, pdf_path: Path, raw: dict) -> Document:
        digest = hashlib.sha256(pdf_path.read_bytes()).hexdigest()
        provenance = raw.get("paperx_provenance", {})
        if (
            provenance.get("source_sha256") != digest
            or provenance.get("marker_version") != "1.9.3"
            or provenance.get("worker_revision") != 1
        ):
            raise ParseError("Marker cache provenance mismatch; regenerate the cache")
        reader = self.read_pdf(pdf_path)
        raw_pages = raw.get("children", [])
        if len(raw_pages) != len(reader.pages):
            raise ParseError("Marker output is incomplete: page count mismatch")
        pages, blocks, sections = [], [], []
        types = {
            "SectionHeader": "heading",
            "Text": "paragraph",
            "TextInlineMath": "paragraph",
            "Equation": "formula",
            "Table": "table",
            "TableOfContents": "table",
            "Figure": "figure",
            "Picture": "figure",
            "ListItem": "list",
            "Code": "code",
        }
        for number, (pdf_page, raw_page) in enumerate(zip(reader.pages, raw_pages), 1):
            if not re.fullmatch(rf"/page/{number - 1}/Page(?:/\d+)?", raw_page.get("id", "")):
                raise ParseError("Marker page order mismatch")
            rotation = pdf_page.rotation % 360
            media, crop = pdf_page.mediabox, pdf_page.cropbox
            width, height = float(media.width), float(media.height)
            page_warnings = []
            if list(media) != list(crop):
                page_warnings.append("cropbox_coordinates_mapped")
            px0, py0, px1, py1 = raw_page["bbox"]
            if not all(math.isfinite(v) for v in (px0, py0, px1, py1)) or (
                px1 <= px0 or py1 <= py0
            ):
                raise ParseError("Invalid Marker page bounds")
            first = len(blocks)
            for node in leaf_blocks(raw_page):
                kind = node["block_type"].split(".")[-1]
                if kind in {"Page", "PageHeader", "PageFooter", "Reference"}:
                    continue
                html = BlockHTML()
                html.feed(node.get("html", ""))
                block_type = types.get(kind, "paragraph")
                if not html.text and block_type not in {"figure", "table"}:
                    continue
                x0, y0, x1, y1 = node["bbox"]
                if not all(math.isfinite(v) for v in (x0, y0, x1, y1)):
                    raise ParseError("Non-finite Marker block bounds")
                normalized = (
                    (x0 - px0) / (px1 - px0),
                    (y0 - py0) / (py1 - py0),
                    (x1 - px0) / (px1 - px0),
                    (y1 - py0) / (py1 - py0),
                )
                normalized = tuple(min(1, max(0, v)) for v in normalized)
                if normalized[2] <= normalized[0] or normalized[3] <= normalized[1]:
                    raise ParseError("Degenerate Marker block bounds")
                box = unrotate_bbox(normalized, rotation)
                # PDFium renders CropBox; contracts refer to unrotated MediaBox.
                box = BBox(
                    x=(float(crop.left - media.left) + box.x * float(crop.width)) / width,
                    y=(float(media.top - crop.top) + box.y * float(crop.height)) / height,
                    width=box.width * float(crop.width) / width,
                    height=box.height * float(crop.height) / height,
                )
                fingerprint = f"{digest}:{self.version}:{node['id']}:{box}:{html.text}"
                block_id = "b-" + hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
                formula = None
                warnings = ["marker_confidence_not_calibrated"]
                if block_type == "formula":
                    latex = "\n".join(html.math).strip() or None
                    formula = Formula(
                        latex=latex,
                        source=self.version,
                        confidence=0,
                        status="needs_review" if latex else "unrecognized",
                    )
                    warnings.append("formula_needs_review")
                level = (html.level or 1) if block_type == "heading" else None
                blocks.append(
                    Block(
                        id=block_id,
                        type=block_type,
                        page=number,
                        order=len(blocks),
                        bbox=box,
                        text=html.text,
                        source=self.version,
                        confidence=0,
                        heading_level=level,
                        formula=formula,
                        warnings=warnings,
                    )
                )
                if block_type == "heading":
                    section = Section(
                        id="s-" + block_id, title=html.text, block_id=block_id, level=level
                    )
                    parent = sections
                    while parent and parent[-1].level < level:
                        parent = parent[-1].children
                    parent.append(section)
            pages.append(
                Page(
                    number=number,
                    width=width,
                    height=height,
                    rotation=rotation,
                    text_status="available" if any(b.text for b in blocks[first:]) else "missing",
                    warnings=page_warnings,
                )
            )
        return Document(
            paper_id="p-" + digest[:20],
            source_sha256=digest,
            parser_version=self.version,
            pages=pages,
            blocks=blocks,
            sections=sections,
            warnings=[
                "marker_local_models",
                "formula_review_required",
                "images_retained_in_original_pdf",
            ],
        )
