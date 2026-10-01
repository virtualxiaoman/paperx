"""Conservative text-layer parser prototype; never claims to recognize LaTeX."""

import hashlib
import re
from importlib.metadata import version
from pathlib import Path

import pdfplumber

from paperx.coordinates import unrotate_bbox
from paperx.models import Block, Document, Formula, Page, Section


class ParseError(Exception):
    pass


def is_horizontal_word(word):
    """Keep normal reading-direction text, excluding marginal vertical labels."""
    direction = word.get("direction", "ltr")
    return bool(word.get("upright", True)) and direction in {"ltr", "rtl"}


def normalize_text(text):
    """Turn PDF line wrapping into copyable paragraph text without inventing content."""
    text = re.sub(r"\s+", " ", text).strip()
    text = re.sub(r"(?<=\w)-\s+(?=\w)", "-", text)
    text = re.sub(r"\s+([,.;:!?])", r"\1", text)
    text = re.sub(r"([\(\[])\s+", r"\1", text)
    text = re.sub(r"\s+([\)\]])", r"\1", text)
    return text


def line_text(line):
    return normalize_text(" ".join(w["text"] for w in sorted(line, key=lambda w: w["x0"])))


def join_lines(lines):
    return normalize_text(" ".join(lines))


def line_groups(words):
    lines = []
    for word in sorted(words, key=lambda w: (round(w["top"] / 3), w["x0"])):
        if not lines or abs(word["top"] - lines[-1][0]["top"]) > 3:
            lines.append([word])
        else:
            lines[-1].append(word)
    return [sorted(line, key=lambda w: w["x0"]) for line in lines]


def regions(words, width):
    """Detect only an obvious central gutter; spanning lines divide vertical bands."""
    lines = line_groups(words)
    split_lines = 0
    for line in lines:
        if any(
            a["x1"] < width * 0.52
            and b["x0"] > width * 0.48
            and b["x0"] - a["x1"] > width * 0.07
            for a, b in zip(line, line[1:])
        ):
            split_lines += 1
    if split_lines < 3:
        return [words], False
    spanning = [
        line
        for line in lines
        if any(w["x0"] < width * 0.49 and w["x1"] > width * 0.51 for w in line)
    ]
    result, top = [], float("-inf")
    for full in [*spanning, None]:
        bottom = full[0]["top"] - 2 if full else float("inf")
        band = [w for w in words if top < w["top"] < bottom]
        result.extend(
            [
                [w for w in band if (w["x0"] + w["x1"]) / 2 < width / 2],
                [w for w in band if (w["x0"] + w["x1"]) / 2 >= width / 2],
            ]
        )
        if full:
            result.append(full)
            top = max(w["top"] for w in full) + 2
    return [r for r in result if r], True


def classify(text, bold):
    if re.fullmatch(r"(?:Abstract|References|Acknowledgments|Acknowledgements)", text, re.I):
        return "heading", 1
    heading = re.match(r"^(\d+(?:\.\d+)*)\s+([A-Z][A-Za-z ,:–-]+)$", text)
    if heading and len(text) < 120 and bold:
        return "heading", min(6, heading[1].count(".") + 1)
    if re.search(r"\([0-9]+\)\s*$", text) and ("=" in text or "∑" in text):
        return "formula", None
    if re.match(r"^\[\d+\]", text):
        return "citation", None
    return "paragraph", None


class PdfPlumberParser:
    version = f"pdfplumber-{version('pdfplumber')}-paperx-v0.4"

    def parse(self, pdf_path: Path) -> Document:
        try:
            if pdf_path.stat().st_size > 50 * 1024 * 1024:
                raise ParseError("PDF exceeds the 50 MiB prototype limit")
            data = pdf_path.read_bytes()
            if not data.startswith(b"%PDF-"):
                raise ParseError("File is not a PDF")
            digest = hashlib.sha256(data).hexdigest()
            pages, blocks, sections = [], [], []
            with pdfplumber.open(pdf_path, unicode_norm="NFC") as pdf:
                if not pdf.pages or len(pdf.pages) > 300:
                    raise ParseError("PDF must contain 1 to 300 pages")
                for page in pdf.pages:
                    raw_words = page.extract_words(
                        x_tolerance=1,
                        y_tolerance=3,
                        extra_attrs=["fontname", "size"],
                    )
                    words = [word for word in raw_words if is_horizontal_word(word)]
                    width, height = page.width, page.height
                    rotation = page.rotation % 360
                    original_w, original_h = (height, width) if rotation % 180 else (width, height)
                    page_warnings = [] if words else ["text_layer_missing", "ocr_not_implemented"]
                    if raw_words and len(words) < len(raw_words):
                        page_warnings.append("vertical_text_excluded")
                    page_regions, columns = regions(words, width)
                    if columns:
                        page_warnings.append("reading_order_heuristic")
                    if rotation:
                        page_warnings.append("rotated_text_order_needs_review")
                    pages.append(
                        Page(
                            number=page.page_number,
                            width=original_w,
                            height=original_h,
                            rotation=rotation,
                            text_status="available" if words else "missing",
                            warnings=page_warnings,
                        )
                    )
                    page_x0, page_y0 = page.bbox[:2]
                    for region in page_regions:
                        groups = []
                        for line in line_groups(region):
                            text = line_text(line)
                            if not text:
                                continue
                            bold = any(
                                any(weight in w["fontname"].lower() for weight in ("bold", "-medi"))
                                for w in line
                            )
                            kind, level = classify(text, bold)
                            top = min(w["top"] for w in line)
                            bottom = max(w["bottom"] for w in line)
                            size = max(w["size"] for w in line)
                            if (
                                kind == "paragraph"
                                and groups
                                and groups[-1]["kind"] == "paragraph"
                                and top - groups[-1]["bottom"] < size * 0.65
                                and abs(size - groups[-1]["size"]) < 1
                            ):
                                groups[-1]["words"].extend(line)
                                groups[-1]["lines"].append(text)
                                groups[-1]["bottom"] = bottom
                            else:
                                groups.append(
                                    dict(
                                        words=list(line),
                                        lines=[text],
                                        kind=kind,
                                        level=level,
                                        bottom=bottom,
                                        size=size,
                                    )
                                )
                        for group in groups:
                            ws, kind = group["words"], group["kind"]
                            text = join_lines(group["lines"])
                            raw_box = (
                                (min(w["x0"] for w in ws) - page_x0) / width,
                                (min(w["top"] for w in ws) - page_y0) / height,
                                (max(w["x1"] for w in ws) - page_x0) / width,
                                (max(w["bottom"] for w in ws) - page_y0) / height,
                            )
                            bbox = unrotate_bbox(raw_box, rotation)
                            fingerprint = (
                                f"{digest}:{self.version}:{page.page_number}:"
                                f"{len(blocks)}:{bbox.model_dump_json()}:{text}"
                            )
                            block_id = "b-" + hashlib.sha256(fingerprint.encode()).hexdigest()[:20]
                            formula = None
                            if kind == "formula":
                                number = re.search(r"\((\d+)\)\s*$", text)
                                formula = Formula(
                                    source="pdf-text-heuristic",
                                    confidence=0,
                                    number=number[0] if number else None,
                                )
                            block = Block(
                                id=block_id,
                                type=kind,
                                page=page.page_number,
                                order=len(blocks),
                                bbox=bbox,
                                text=text,
                                source=self.version,
                                confidence=0.65 if columns else 0.8,
                                heading_level=group["level"],
                                formula=formula,
                                warnings=["latex_unrecognized"] if formula else [],
                            )
                            blocks.append(block)
                            if kind == "heading":
                                section = Section(
                                    id="s-" + block_id,
                                    title=text,
                                    block_id=block_id,
                                    level=group["level"],
                                )
                                parent = sections
                                while parent and parent[-1].level < section.level:
                                    parent = parent[-1].children
                                parent.append(section)
            return Document(
                paper_id="p-" + digest[:20],
                source_sha256=digest,
                parser_version=self.version,
                pages=pages,
                blocks=blocks,
                sections=sections,
                warnings=[
                    "prototype_structure_needs_review",
                    "formula_recognition_not_implemented",
                    "figures_tables_not_extracted",
                ],
            )
        except ParseError:
            raise
        except Exception as exc:
            # Do not expose local paths, PDF internals or potential credentials to callers.
            raise ParseError("PDF could not be parsed; malformed or encrypted input") from exc
