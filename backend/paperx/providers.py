"""Business-facing ports; no front-end dependency on AI or parser implementations."""

from pathlib import Path
from typing import Protocol

from paperx.models import Block, Document, Formula, TranslationBlock


class ParserProvider(Protocol):
    version: str

    def parse(self, pdf_path: Path) -> Document: ...


class FormulaProvider(Protocol):
    async def recognize(self, image: bytes, source_block: Block) -> Formula: ...


class TranslationProvider(Protocol):
    async def list_models(self) -> list[str]: ...

    async def translate(
        self, blocks: list[Block], *, model: str, glossary: dict[str, str]
    ) -> list[TranslationBlock]: ...


class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
