"""Read-only feasibility API. Import/task/settings APIs are reserved for later stages."""

import json
import logging
import re
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import FileResponse, JSONResponse
from starlette.exceptions import HTTPException

from paperx.config import Settings
from paperx.models import ApiError, Document, ErrorDetail, Sample


def create_app(samples_dir: Path | None = None) -> FastAPI:
    samples_dir = samples_dir or Settings().samples_dir
    app = FastAPI(title="Paperx", version="0.1.0", description="Stage 0 read-only feasibility API")

    def error(status, code, message, retryable=False):
        return JSONResponse(
            status_code=status,
            content=ApiError(
                error=ErrorDetail(code=code, message=message, retryable=retryable)
            ).model_dump(),
        )

    @app.exception_handler(HTTPException)
    async def http_error(request: Request, exc: HTTPException):
        codes = {404: "NOT_FOUND", 405: "METHOD_NOT_ALLOWED", 416: "INVALID_RANGE"}
        return error(exc.status_code, codes.get(exc.status_code, "REQUEST_ERROR"), str(exc.detail))

    @app.exception_handler(RequestValidationError)
    async def validation_error(request: Request, exc: RequestValidationError):
        return error(422, "VALIDATION_ERROR", "Invalid request parameters")

    @app.exception_handler(Exception)
    async def internal_error(request: Request, exc: Exception):
        logging.getLogger("paperx").error("Request failed: %s", type(exc).__name__)
        return error(500, "INTERNAL_ERROR", "Local data could not be read", True)

    def sample_folder(sample_id: str):
        if not re.fullmatch(r"[a-z0-9-]{1,80}", sample_id):
            raise HTTPException(404, "Sample not found")
        folder = samples_dir / sample_id
        if not (folder / "sample.json").is_file():
            raise HTTPException(404, "Sample not found; run the sample preparation command")
        return folder

    @app.get("/health")
    def health():
        return {"status": "ok", "stage": 0, "api_version": "1.0"}

    @app.get("/samples", response_model=list[Sample])
    def samples():
        return [
            Sample.model_validate_json(p.read_text(encoding="utf-8"))
            for p in sorted(samples_dir.glob("*/sample.json"))
        ]

    @app.get(
        "/samples/{sample_id}/document",
        response_model=Document,
        responses={404: {"model": ApiError}, 422: {"model": ApiError}},
    )
    def document(sample_id: str):
        return json.loads((sample_folder(sample_id) / "document.json").read_text(encoding="utf-8"))

    @app.get("/samples/{sample_id}/pdf", responses={404: {"model": ApiError}})
    def pdf(sample_id: str):
        pdf_path = sample_folder(sample_id) / "original.pdf"
        if not pdf_path.is_file():
            raise HTTPException(404, "Original PDF not found")
        return FileResponse(
            pdf_path,
            media_type="application/pdf",
            filename="original.pdf",
            content_disposition_type="inline",
        )

    return app


app = create_app()
