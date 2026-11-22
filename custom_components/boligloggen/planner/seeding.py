"""Generate a maintenance plan from a property profile and the catalog."""

from __future__ import annotations

import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date

from .catalog import Catalog
from .models import PropertyProfile, Schedule, Task, TaskTemplate, template_key
from .rules import matches
from .schedule import default_due_soon_days, initial_next_due

DEFAULT_LANGUAGE = "nb"

_BATHROOM_SUFFIX = {"nb": "bad {n}", "en": "bathroom {n}"}


def localized(texts: dict[str, str], lang: str) -> str:
    """Pick ``lang`` from a localized dict, falling back to nb, en, then anything."""
    for candidate in (lang, DEFAULT_LANGUAGE, "en"):
        if texts.get(candidate):
            return texts[candidate]
    return next(iter(texts.values()), "")


def normalize_language(lang: str | None) -> str:
    """Map HA language codes (``nb``, ``no``, ``nn``, ``en-GB`` …) to catalog languages."""
    if not lang:
        return DEFAULT_LANGUAGE
    base = lang.lower().replace("_", "-").split("-")[0]
    if base in ("nb", "no", "nn"):
        return "nb"
    return "en" if base == "en" else DEFAULT_LANGUAGE


@dataclass(frozen=True)
class Suggestion:
    """A template (instance) proposed for a property."""

    template: TaskTemplate
    instance: int | None = None

    @property
    def key(self) -> str:
        return template_key(self.template.id, self.instance)

    def title(self, lang: str) -> str:
        base = localized(self.template.title, lang)
        if self.instance is None:
            return base
        suffix = _BATHROOM_SUFFIX.get(lang, _BATHROOM_SUFFIX["en"]).format(n=self.instance)
        return f"{base} – {suffix}"


def expand_template(template: TaskTemplate, profile: PropertyProfile) -> list[Suggestion]:
    if not template.per_bathroom:
        return [Suggestion(template)]
    count = max(1, profile.attributes.bathroom_count)
    return [Suggestion(template, n) for n in range(1, count + 1)]


def suggest(catalog: Catalog, profile: PropertyProfile, today: date) -> list[Suggestion]:
    """All template instances whose inclusion rule matches ``profile``."""
    result: list[Suggestion] = []
    for template in catalog:
        if matches(template.include, profile, today):
            result.extend(expand_template(template, profile))
    return result


def all_suggestions(catalog: Catalog, profile: PropertyProfile) -> list[Suggestion]:
    """Every template instance, matching or not (for "show all" in the options flow)."""
    return [s for t in catalog for s in expand_template(t, profile)]


def task_from_suggestion(
    suggestion: Suggestion, *, lang: str, setup_date: date, now_iso: str
) -> Task:
    template = suggestion.template
    due_soon = (
        template.due_soon_days
        if template.due_soon_days is not None
        else default_due_soon_days(template.schedule)
    )
    return Task(
        id=uuid.uuid4().hex,
        template_id=template.id,
        instance=suggestion.instance,
        title=suggestion.title(lang),
        description=localized(template.description, lang) if template.description else "",
        category=template.category,
        schedule=template.schedule,
        due_soon_days=due_soon,
        next_due=initial_next_due(template.schedule, setup_date),
        created_at=now_iso,
        updated_at=now_iso,
    )


def seed_tasks(
    suggestions: Iterable[Suggestion], *, lang: str, setup_date: date, now_iso: str
) -> list[Task]:
    return [
        task_from_suggestion(s, lang=lang, setup_date=setup_date, now_iso=now_iso)
        for s in suggestions
    ]


def custom_task(
    *,
    title: str,
    category: str,
    schedule: Schedule,
    setup_date: date,
    now_iso: str,
    description: str = "",
    due_soon_days: int | None = None,
) -> Task:
    return Task(
        id=uuid.uuid4().hex,
        template_id=None,
        title=title,
        description=description,
        category=category,
        schedule=schedule,
        due_soon_days=due_soon_days
        if due_soon_days is not None
        else default_due_soon_days(schedule),
        next_due=initial_next_due(schedule, setup_date),
        created_at=now_iso,
        updated_at=now_iso,
    )


@dataclass(frozen=True)
class PlanDiff:
    """Changes suggested after the property profile was edited."""

    additions: tuple[Suggestion, ...]
    removals: tuple[Task, ...]


def plan_diff(
    catalog: Catalog, profile: PropertyProfile, tasks: Iterable[Task], today: date
) -> PlanDiff:
    """Suggest catalog additions and removals for an (edited) profile.

    * Additions: matching template instances with no task at all – archived
      tasks count as present, so archived templates never come back on their own.
    * Removals: active catalog tasks whose template no longer matches.
      Custom tasks are never suggested for removal.
    """
    tasks = list(tasks)
    known_keys = {t.key for t in tasks if t.key}
    matched = suggest(catalog, profile, today)
    matched_keys = {s.key for s in matched}
    additions = tuple(s for s in matched if s.key not in known_keys)
    removals = tuple(
        t
        for t in tasks
        if t.is_active and t.key and catalog.get(t.template_id or "") and t.key not in matched_keys
    )
    return PlanDiff(additions=additions, removals=removals)
