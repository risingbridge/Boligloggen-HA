"""Export document round trip and strict import validation."""

from __future__ import annotations

import copy
from datetime import date
from typing import Any

import pytest
from planner import LogEntry, Schedule
from planner.transfer import (
    EXPORT_FORMAT_VERSION,
    TransferError,
    build_export,
    parse_export,
)

from .helpers import NOW, make_task, profile


def _document() -> dict[str, Any]:
    fixed = make_task(Schedule.fixed((12, 1)), date(2026, 12, 1))
    interval = make_task(Schedule.interval(3, "months"), date(2027, 2, 22)).evolve(
        id="t2", title="Filter", status="archived"
    )
    entry = LogEntry(
        id="l1",
        task_id="t1",
        completed_on=date(2025, 12, 3),
        occurrence_date=date(2025, 12, 1),
        prev_next_due=date(2025, 12, 1),
        user_name="Kari",
        note="Byttet batteri",
    )
    data = {
        "schema_version": 1,
        "catalog_version": 1,
        "language": "nb",
        "profile": profile().to_dict(),
        "tasks": [fixed.to_dict(), interval.to_dict()],
        "log": [entry.to_dict()],
        "onboarding_feedback": {"deselected_at_review": ["leaf_raking"], "added_later": []},
    }
    return build_export(data, exported_at=NOW, integration_version="0.3.0")


def test_round_trip() -> None:
    doc = _document()
    snapshot = parse_export(doc)
    assert snapshot.profile.name == "Test"
    assert snapshot.language == "nb"
    assert [t.id for t in snapshot.tasks] == ["t1", "t2"]
    assert snapshot.active_count == 1
    assert snapshot.tasks[0].schedule == Schedule.fixed((12, 1))
    assert snapshot.log[0].note == "Byttet batteri"
    assert snapshot.feedback == {
        "deselected_at_review": ["leaf_raking"],
        "added_later": [],
        "removed_later": [],
    }
    assert snapshot.exported_at == NOW
    assert snapshot.integration_version == "0.3.0"
    # Re-exporting the parsed data gives the same tasks and log.
    assert [t.to_dict() for t in snapshot.tasks] == doc["property"]["tasks"]
    assert [e.to_dict() for e in snapshot.log] == doc["property"]["log"]


@pytest.mark.parametrize(
    ("mutate", "key"),
    [
        (lambda d: d.update(format="something-else"), "not_boligloggen_file"),
        (lambda d: d.update(format_version=EXPORT_FORMAT_VERSION + 1), "unsupported_version"),
        (lambda d: d["property"].update(schema_version=99), "unsupported_version"),
        (lambda d: d["property"].update(profile="nope"), "invalid_content"),
        (lambda d: d["property"]["profile"].update(type="castle"), "invalid_content"),
        (lambda d: d["property"]["profile"].update(name=" "), "invalid_content"),
        (lambda d: d["property"]["profile"].update(age_band="old"), "invalid_content"),
        (lambda d: d["property"]["profile"].update(build_year=85), "invalid_content"),
        (
            lambda d: d["property"]["profile"]["attributes"].update(heating=["heat-pump"]),
            "invalid_content",
        ),
        (
            lambda d: d["property"]["profile"]["attributes"].update(ventilation="good"),
            "invalid_content",
        ),
        (
            lambda d: d["property"]["profile"]["attributes"].update(bathroom_count=4),
            "invalid_content",
        ),
        (lambda d: d["property"]["profile"]["attributes"].update(garden="yes"), "invalid_content"),
        (lambda d: d["property"].update(tasks={}), "invalid_content"),
        (lambda d: d["property"]["tasks"][0].update(category="garden"), "invalid_content"),
        (lambda d: d["property"]["tasks"][0].update(next_due="1. desember"), "invalid_content"),
        (lambda d: d["property"]["tasks"][0].update(status="deleted"), "invalid_content"),
        (lambda d: d["property"]["tasks"][0].update(title=""), "invalid_content"),
        (lambda d: d["property"]["tasks"][0].pop("id"), "invalid_content"),
        (
            lambda d: d["property"]["tasks"][0].update(
                schedule={"type": "fixed", "dates": [{"month": 2, "day": 30}]}
            ),
            "invalid_content",
        ),
        (
            lambda d: d["property"]["tasks"][1].update(
                schedule={"type": "interval", "every": 0, "unit": "months"}
            ),
            "invalid_content",
        ),
        (lambda d: d["property"]["tasks"][1].update(id="t1"), "invalid_content"),
        (lambda d: d["property"]["log"][0].update(completed_on=None), "invalid_content"),
        (lambda d: d["property"]["log"].append(d["property"]["log"][0]), "invalid_content"),
    ],
)
def test_rejects_invalid_documents(mutate: Any, key: str) -> None:
    doc = copy.deepcopy(_document())
    mutate(doc)
    with pytest.raises(TransferError) as err:
        parse_export(doc)
    assert err.value.key == key


def test_rejects_non_objects() -> None:
    for payload in (None, [], "text", 3):
        with pytest.raises(TransferError) as err:
            parse_export(payload)
        assert err.value.key == "not_boligloggen_file"


def test_tolerates_missing_optional_parts() -> None:
    doc = _document()
    prop = doc["property"]
    del prop["log"], prop["onboarding_feedback"], prop["schema_version"]
    prop["language"] = "de"
    snapshot = parse_export(doc)
    assert snapshot.log == ()
    assert snapshot.language is None  # unknown language → keep the property's own
    assert snapshot.feedback == {"deselected_at_review": [], "added_later": [], "removed_later": []}
