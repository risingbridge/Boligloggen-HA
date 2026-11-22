"""Boligloggen planner – pure Python, no Home Assistant imports.

Holds the domain model, catalog loading/validation, inclusion rules,
plan seeding and the scheduling engine.
"""

from .catalog import Catalog, CatalogError, load_catalog, parse_catalog
from .describe import describe_schedule
from .models import (
    LogEntry,
    MonthDay,
    Occurrence,
    PropertyAttributes,
    PropertyProfile,
    Schedule,
    Task,
    TaskTemplate,
)
from .rules import matches
from .schedule import (
    CompletionResult,
    add_months,
    complete_task,
    compute_status,
    days_until_due,
    default_due_soon_days,
    initial_next_due,
    is_early_completion_blocked,
    next_due_from_last_done,
    project_year,
    task_status,
    undo_completion,
)
from .seeding import (
    PlanDiff,
    Suggestion,
    all_suggestions,
    custom_task,
    localized,
    normalize_language,
    plan_diff,
    seed_tasks,
    suggest,
    task_from_suggestion,
)

__all__ = [
    "Catalog",
    "CatalogError",
    "CompletionResult",
    "LogEntry",
    "MonthDay",
    "Occurrence",
    "PlanDiff",
    "PropertyAttributes",
    "PropertyProfile",
    "Schedule",
    "Suggestion",
    "Task",
    "TaskTemplate",
    "add_months",
    "all_suggestions",
    "complete_task",
    "compute_status",
    "custom_task",
    "days_until_due",
    "default_due_soon_days",
    "describe_schedule",
    "initial_next_due",
    "is_early_completion_blocked",
    "load_catalog",
    "localized",
    "matches",
    "next_due_from_last_done",
    "normalize_language",
    "parse_catalog",
    "plan_diff",
    "project_year",
    "seed_tasks",
    "suggest",
    "task_from_suggestion",
    "task_status",
    "undo_completion",
]
