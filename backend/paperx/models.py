"""Versioned public contracts. All positions use unrotated MediaBox coordinates."""

from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class Contract(BaseModel):
    model_config = ConfigDict(extra="forbid")


class BBox(Contract):
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    width: float = Field(gt=0, le=1)
    height: float = Field(gt=0, le=1)

    @model_validator(mode="after")
    def inside_page(self):
        if self.x + self.width > 1.000001 or self.y + self.height > 1.000001:
            raise ValueError("bbox extends outside page")
        return self


class Location(Contract):
    page: int = Field(ge=1)
    bbox: BBox


class Page(Contract):
    number: int = Field(ge=1)
    width: float = Field(gt=0)
    height: float = Field(gt=0)
    rotation: Literal[0, 90, 180, 270] = 0
    text_status: Literal["available", "missing"]
    warnings: list[str] = Field(default_factory=list)


class Formula(Contract):
    latex: str | None = None
    number: str | None = None
    source: str
    confidence: float = Field(ge=0, le=1)
    status: Literal["unrecognized", "needs_review", "verified"] = "unrecognized"
    revision: int = Field(default=0, ge=0)
    verified_by: str | None = None

    @model_validator(mode="after")
    def verified_requires_evidence(self):
        if self.status == "verified" and (not self.latex or not self.verified_by):
            raise ValueError("verified formulas require LaTeX and reviewer provenance")
        return self

    @property
    def can_copy(self) -> bool:
        return self.status == "verified" and bool(self.latex and self.verified_by)


class Block(Contract):
    id: str
    type: Literal["heading", "paragraph", "formula", "figure", "table", "citation", "list", "code"]
    page: int = Field(ge=1)
    order: int = Field(ge=0)
    bbox: BBox
    locations: list[Location] = Field(default_factory=list)
    text: str = ""
    source: str
    confidence: float = Field(ge=0, le=1)
    heading_level: int | None = Field(default=None, ge=1, le=6)
    formula: Formula | None = None
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def formula_is_first_class(self):
        if self.type == "formula" and self.formula is None:
            raise ValueError("formula blocks require recognition metadata")
        if self.formula is not None and self.type != "formula":
            raise ValueError("formula metadata belongs to formula blocks")
        return self


class Section(Contract):
    id: str
    title: str
    block_id: str
    level: int = Field(ge=1, le=6)
    children: list["Section"] = Field(default_factory=list)


class TranslationBlock(Contract):
    id: str
    source_block_ids: list[str] = Field(min_length=1)
    text: str
    status: Literal["translated", "preserved", "failed", "unmapped"]


class Document(Contract):
    schema_version: Literal["1.0"] = "1.0"
    paper_id: str
    source_sha256: str
    parser_version: str
    coordinate_system: Literal["normalized-unrotated-mediabox-top-left"] = (
        "normalized-unrotated-mediabox-top-left"
    )
    pages: list[Page]
    blocks: list[Block]
    sections: list[Section] = Field(default_factory=list)
    translations: list[TranslationBlock] = Field(default_factory=list)
    translation_version: str | None = None
    previous_parser_version: str | None = None
    previous_id_map: dict[str, list[str]] = Field(default_factory=dict)
    warnings: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def references_are_valid(self):
        pages = {p.number for p in self.pages}
        if pages != set(range(1, len(self.pages) + 1)) or len(pages) != len(self.pages):
            raise ValueError("pages must be consecutive and unique")
        ids = {b.id for b in self.blocks}
        if len(ids) != len(self.blocks):
            raise ValueError("duplicate block ID")
        if [b.order for b in self.blocks] != list(range(len(self.blocks))):
            raise ValueError("block order must be consecutive")
        for block in self.blocks:
            if block.page not in pages or any(p.page not in pages for p in block.locations):
                raise ValueError("block points to missing page")

        def check_sections(sections):
            for section in sections:
                if section.block_id not in ids:
                    raise ValueError("section points to missing block")
                check_sections(section.children)

        check_sections(self.sections)
        for translation in self.translations:
            if translation.status != "unmapped" and not set(translation.source_block_ids) <= ids:
                raise ValueError("translation points to missing block")
        return self


class TaskStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    CANCELLED = "cancelled"


class ErrorDetail(Contract):
    code: str
    message: str
    retryable: bool = False


class ApiError(Contract):
    error: ErrorDetail


class Task(Contract):
    id: str
    paper_id: str
    status: TaskStatus
    stage: str
    progress: float = Field(ge=0, le=1)
    retries: int = Field(default=0, ge=0)
    error: ErrorDetail | None = None


class Paper(Contract):
    id: str
    title: str
    source: Literal["upload", "arxiv", "local", "fixture"]
    source_sha256: str
    page_count: int = Field(ge=1)
    parser_version: str
    original_pdf_url: str
    translated_pdf_url: str | None = None
    task_id: str | None = None


class Sample(Contract):
    id: str
    paper: Paper
    label: str
    synthetic: bool
