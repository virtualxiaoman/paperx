"""Isolated Marker worker. Run with .venv-marker, never in the API process."""

import argparse
import hashlib
import json
import os
import tempfile
from importlib.metadata import version
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def configure_model_cache(root=ROOT):
    """Set library caches before importing any inference dependencies."""
    cache = root / "model"
    cache.mkdir(parents=True, exist_ok=True)
    os.environ["HF_HOME"] = str(cache / "huggingface")
    os.environ["HF_HUB_CACHE"] = str(cache / "huggingface" / "hub")
    os.environ["HUGGINGFACE_HUB_CACHE"] = str(cache / "huggingface" / "hub")
    os.environ["HF_ASSETS_CACHE"] = str(cache / "huggingface" / "assets")
    os.environ["TRANSFORMERS_CACHE"] = str(cache / "huggingface" / "hub")
    os.environ["MODEL_CACHE_DIR"] = str(cache / "surya")
    os.environ["TORCH_HOME"] = str(cache / "torch")
    os.environ["HF_XET_CACHE"] = str(cache / "huggingface" / "xet")
    os.environ["TORCHINDUCTOR_CACHE_DIR"] = str(cache / "torch" / "inductor")
    os.environ["TRITON_CACHE_DIR"] = str(cache / "triton")
    os.environ["XDG_CACHE_HOME"] = str(cache / "cache")
    downloads = cache / "tmp"
    downloads.mkdir(parents=True, exist_ok=True)
    os.environ["TMP"] = os.environ["TEMP"] = str(downloads)
    tempfile.tempdir = str(downloads)
    os.environ["HF_HUB_DISABLE_TELEMETRY"] = "1"
    os.environ["PDFTEXT_CPU_WORKERS"] = "1"
    return cache


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("pdf", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--device", choices=["cuda", "cpu"], default="cuda")
    args = parser.parse_args()
    cache = configure_model_cache()
    os.environ["TORCH_DEVICE"] = args.device

    import torch
    from marker.converters.pdf import PdfConverter
    from marker.models import create_model_dict
    from marker.renderers.json import JSONRenderer
    from marker.renderers.markdown import MarkdownRenderer

    if args.device == "cuda" and not torch.cuda.is_available():
        raise RuntimeError("CUDA unavailable; install CUDA PyTorch or select --device cpu")
    if version("marker-pdf") != "1.9.3":
        raise RuntimeError("This adapter is validated against marker-pdf==1.9.3")
    config = {
        "use_llm": False,
        "disable_multiprocessing": True,
        "disable_image_extraction": True,
        "layout_batch_size": 2,
        "recognition_batch_size": 4,
        "detection_batch_size": 2,
        "table_rec_batch_size": 2,
    }
    print(f"Marker {version('marker-pdf')}; torch {torch.__version__}; {args.device}", flush=True)
    print(f"Model cache: {cache}; temporary downloads: {tempfile.gettempdir()}", flush=True)
    models = create_model_dict(device=args.device, attention_implementation="sdpa")
    converter = PdfConverter(artifact_dict=models, config=config)
    document = converter.build_document(str(args.pdf.resolve()))
    raw = JSONRenderer(config)(document).model_dump(mode="json")
    raw["paperx_provenance"] = {
        "source_sha256": hashlib.sha256(args.pdf.read_bytes()).hexdigest(),
        "marker_version": version("marker-pdf"),
        "surya_version": version("surya-ocr"),
        "torch_version": torch.__version__,
        "device": args.device,
        "config": config,
        "worker_revision": 1,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.with_suffix(".md").write_text(
        MarkdownRenderer(config)(document).markdown, encoding="utf-8"
    )
    temporary = args.output.with_suffix(".json.tmp")
    temporary.write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
    temporary.replace(args.output)
    print(f"Wrote {args.output}", flush=True)


if __name__ == "__main__":
    main()
