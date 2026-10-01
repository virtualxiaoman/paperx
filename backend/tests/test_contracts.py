import pytest
from paperx.coordinates import unrotate_bbox
from paperx.models import BBox, Document, Formula, TaskStatus
from pydantic import ValidationError


def test_bbox_rejects_pixels_and_outside_bounds():
    for box in [dict(x=120, y=300, width=10, height=40), dict(x=0.9, y=0, width=0.2, height=0.1)]:
        with pytest.raises(ValidationError):
            BBox(**box)


@pytest.mark.parametrize(
    "rotation,display",
    [
        (0, (0.1, 0.2, 0.3, 0.4)),
        (90, (0.6, 0.1, 0.8, 0.3)),
        (180, (0.7, 0.6, 0.9, 0.8)),
        (270, (0.2, 0.7, 0.4, 0.9)),
    ],
)
def test_rotation_contract(rotation, display):
    result = unrotate_bbox(display, rotation)
    assert list(result.model_dump().values()) == pytest.approx([0.1, 0.2, 0.2, 0.2])


def test_formula_copy_requires_review():
    assert not Formula(source="pdf-text", confidence=1, latex="x=1").can_copy
    assert not Formula(source="pdf-text", confidence=0).can_copy
    with pytest.raises(ValidationError):
        Formula(source="pdf-text", confidence=1, status="verified", latex="x=1")
    assert Formula(
        source="manual", confidence=1, status="verified", latex="x=1", verified_by="fixture-author"
    ).can_copy


def test_empty_document_contract_and_task_states():
    document = Document(paper_id="x", source_sha256="a", parser_version="v1", pages=[], blocks=[])
    assert document.schema_version == "1.0"
    assert {s.value for s in TaskStatus} == {
        "queued",
        "running",
        "succeeded",
        "failed",
        "cancelled",
    }
