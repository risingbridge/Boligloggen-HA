"""Scheduling rules: next due date, status, completion, undo and year projection.

Every function takes ``today`` (or an explicit date) as an argument – the
planner never calls ``date.today()`` itself.

Leap years: a fixed date of 29 February falls on 28 February in non-leap years.
"""

from __future__ import annotations

import calendar
import uuid
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import date, timedelta

from .models import DueStatus, LogEntry, MonthDay, Occurrence, Schedule, Task

# ---------------------------------------------------------------------------
# Date arithmetic
# ---------------------------------------------------------------------------


def add_months(value: date, months: int) -> date:
    """Add ``months`` to ``value``, clamping to the end of the target month."""
    index = value.year * 12 + (value.month - 1) + months
    year, month0 = divmod(index, 12)
    month = month0 + 1
    day = min(value.day, calendar.monthrange(year, month)[1])
    return date(year, month, day)


def add_interval(value: date, schedule: Schedule) -> date:
    if schedule.type != "interval":
        raise ValueError("add_interval requires an interval schedule")
    return add_months(value, schedule.interval_months)


def fixed_date(year: int, md: MonthDay) -> date:
    """Concrete date for a month/day in ``year`` (29 Feb → 28 Feb in non-leap years)."""
    day = min(md.day, calendar.monthrange(year, md.month)[1])
    return date(year, md.month, day)


def fixed_dates_in_year(schedule: Schedule, year: int) -> list[date]:
    return sorted({fixed_date(year, md) for md in schedule.dates})


def _fixed_dates_from(schedule: Schedule, start_year: int) -> Iterable[date]:
    year = start_year
    while True:
        yield from fixed_dates_in_year(schedule, year)
        year += 1


def first_fixed_on_or_after(schedule: Schedule, value: date) -> date:
    return next(d for d in _fixed_dates_from(schedule, value.year) if d >= value)


def first_fixed_after(schedule: Schedule, value: date) -> date:
    return next(d for d in _fixed_dates_from(schedule, value.year) if d > value)


# ---------------------------------------------------------------------------
# Periods and due-soon defaults
# ---------------------------------------------------------------------------


def _month_gap(a: MonthDay, b: MonthDay) -> float:
    """Gap from ``a`` to the next ``b`` in months (wrapping across new year)."""
    gap = (b.month - a.month) + (b.day - a.day) / 30.0
    return gap if gap > 0 else gap + 12


def period_months(schedule: Schedule) -> float:
    """Effective period in months.

    For fixed schedules it is the shortest gap between consecutive dates in
    the year, wrapping at year end; a single date per year gives 12 months.
    """
    if schedule.type == "interval":
        return float(schedule.interval_months)
    dates = sorted(set(schedule.dates), key=lambda d: (d.month, d.day))
    if len(dates) <= 1:
        return 12.0
    gaps = [_month_gap(dates[i], dates[(i + 1) % len(dates)]) for i in range(len(dates))]
    return min(gaps)


def default_due_soon_days(schedule: Schedule) -> int:
    months = period_months(schedule)
    if months <= 1:
        return 3
    if months <= 3:
        return 7
    if months <= 6:
        return 14
    if months <= 12:
        return 21
    return 60


# ---------------------------------------------------------------------------
# Status
# ---------------------------------------------------------------------------


def compute_status(next_due: date, due_soon_days: int, today: date) -> DueStatus:
    if today > next_due:
        return "overdue"
    if next_due - timedelta(days=due_soon_days) <= today:
        return "due_soon"
    return "ok"


def task_status(task: Task, today: date) -> DueStatus:
    return compute_status(task.next_due, task.due_soon_days, today)


def days_until_due(task: Task, today: date) -> int:
    return (task.next_due - today).days


# ---------------------------------------------------------------------------
# next_due calculation
# ---------------------------------------------------------------------------


def initial_next_due(schedule: Schedule, setup_date: date) -> date:
    """``next_due`` for a freshly seeded task.

    fixed: first listed date on or after setup; interval: setup + interval.
    """
    if schedule.type == "fixed":
        return first_fixed_on_or_after(schedule, setup_date)
    return add_interval(setup_date, schedule)


def next_due_after_completion(schedule: Schedule, completed_on: date, prev_next_due: date) -> date:
    if schedule.type == "interval":
        return add_interval(completed_on, schedule)
    return first_fixed_after(schedule, max(completed_on, prev_next_due))


def next_due_from_last_done(schedule: Schedule, last_done: date) -> date:
    """Recompute ``next_due`` when an admin sets "last done" manually.

    interval: last_done + interval.  fixed: the first listed date after
    ``last_done`` (which may already be in the past, i.e. overdue).
    """
    if schedule.type == "interval":
        return add_interval(last_done, schedule)
    return first_fixed_after(schedule, last_done)


def is_early_completion_blocked(task: Task, today: date) -> bool:
    """Fixed tasks may not be completed (without ``force``) before their due window."""
    return task.schedule.type == "fixed" and task_status(task, today) == "ok"


# ---------------------------------------------------------------------------
# Completion and undo
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CompletionResult:
    task: Task
    entry: LogEntry


def complete_task(
    task: Task,
    completed_on: date,
    *,
    now_iso: str,
    user_id: str | None = None,
    user_name: str = "System",
    note: str | None = None,
    forced: bool = False,
    entry_id: str | None = None,
) -> CompletionResult:
    """Complete ``task`` and return the updated task and its log entry.

    The log entry carries a snapshot (``prev_next_due``/``prev_last_completed``)
    so the completion can be undone exactly.
    """
    prev_next_due = task.next_due
    new_next_due = next_due_after_completion(task.schedule, completed_on, prev_next_due)
    entry = LogEntry(
        id=entry_id or uuid.uuid4().hex,
        task_id=task.id,
        completed_on=completed_on,
        occurrence_date=prev_next_due,
        prev_next_due=prev_next_due,
        prev_last_completed=task.last_completed,
        user_id=user_id,
        user_name=user_name,
        note=note,
        forced=forced,
        created_at=now_iso,
    )
    updated = task.evolve(
        next_due=new_next_due,
        last_completed=completed_on,
        updated_at=now_iso,
    )
    return CompletionResult(task=updated, entry=entry)


def undo_completion(task: Task, entry: LogEntry, *, now_iso: str) -> Task:
    if entry.task_id != task.id:
        raise ValueError("Log entry does not belong to task")
    return task.evolve(
        next_due=entry.prev_next_due,
        last_completed=entry.prev_last_completed,
        updated_at=now_iso,
    )


# ---------------------------------------------------------------------------
# Year projection (årshjul)
# ---------------------------------------------------------------------------


def project_year(task: Task, year: int, log: Iterable[LogEntry], today: date) -> list[Occurrence]:
    """Occurrences of ``task`` in ``year`` with status for the year-wheel.

    fixed:    every listed date in the year (plus ``next_due`` if it was moved
              off-grid). Logged occurrence → ``done``; dates before ``next_due``
              that were never logged → ``missed``; the current occurrence gets
              ``ok/due_soon/overdue`` (``ok`` reported as ``upcoming``); later
              dates already in the past → ``overdue``; future → ``upcoming``.
              Dates before the task was created are omitted.
    interval: log entries completed in the year → ``done`` (on their
              completion date); then ``next_due`` and its projections by the
              interval until year end.
    """
    entries = [e for e in log if e.task_id == task.id]
    year_start, year_end = date(year, 1, 1), date(year, 12, 31)
    current = compute_status(task.next_due, task.due_soon_days, today)
    current_status = "upcoming" if current == "ok" else current
    result: list[Occurrence] = []

    if task.schedule.type == "fixed":
        done_dates = {e.occurrence_date for e in entries}
        created = _created_date(task)
        dates = set(fixed_dates_in_year(task.schedule, year))
        if year_start <= task.next_due <= year_end:
            dates.add(task.next_due)
        for d in sorted(dates):
            if d in done_dates:
                result.append(Occurrence(d, "done"))
            elif created is not None and d < created:
                continue
            elif d < task.next_due:
                result.append(Occurrence(d, "missed"))
            elif d == task.next_due:
                result.append(Occurrence(d, current_status))
            elif d < today:
                result.append(Occurrence(d, "overdue"))
            else:
                result.append(Occurrence(d, "upcoming"))
        return result

    for e in sorted(entries, key=lambda e: e.completed_on):
        if year_start <= e.completed_on <= year_end:
            result.append(Occurrence(e.completed_on, "done"))
    due = task.next_due
    first = True
    while due <= year_end:
        if due >= year_start:
            result.append(Occurrence(due, current_status if first else "upcoming"))
        first = False
        due = add_interval(due, task.schedule)
    result.sort(key=lambda o: o.date)
    return result


def _created_date(task: Task) -> date | None:
    if not task.created_at:
        return None
    try:
        return date.fromisoformat(task.created_at[:10])
    except ValueError:
        return None
