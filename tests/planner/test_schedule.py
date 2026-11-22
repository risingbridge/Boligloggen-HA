"""Scheduling engine tests (brief §8)."""

from __future__ import annotations

from datetime import date

import pytest
from planner import (
    Schedule,
    add_months,
    complete_task,
    compute_status,
    default_due_soon_days,
    describe_schedule,
    initial_next_due,
    is_early_completion_blocked,
    next_due_from_last_done,
    project_year,
    undo_completion,
)
from planner.schedule import fixed_dates_in_year, period_months

from .helpers import NOW, make_task

D = date
QUARTERLY = Schedule.interval(3, "months")
YEARLY = Schedule.interval(1, "years")
DEC_1 = Schedule.fixed((12, 1))
SPRING_AUTUMN = Schedule.fixed((4, 1), (10, 1))


# --- month arithmetic ---------------------------------------------------------


@pytest.mark.parametrize(
    ("start", "months", "expected"),
    [
        (D(2026, 1, 31), 1, D(2026, 2, 28)),
        (D(2028, 1, 31), 1, D(2028, 2, 29)),  # leap year
        (D(2026, 3, 31), 1, D(2026, 4, 30)),
        (D(2026, 11, 30), 3, D(2027, 2, 28)),
        (D(2026, 12, 15), 1, D(2027, 1, 15)),
        (D(2028, 2, 29), 12, D(2029, 2, 28)),
        (D(2026, 5, 10), 84, D(2033, 5, 10)),
        (D(2026, 3, 31), -1, D(2026, 2, 28)),
    ],
)
def test_add_months_clamps_to_month_end(start: date, months: int, expected: date) -> None:
    assert add_months(start, months) == expected


def test_interval_does_not_accumulate_clamping_drift() -> None:
    # Completed on the 31st every time: next due is computed from the actual
    # completion date, so a short month in between doesn't drift the schedule.
    task = make_task(Schedule.interval(1, "months"), D(2026, 1, 31))
    r1 = complete_task(task, D(2026, 1, 31), now_iso=NOW)
    assert r1.task.next_due == D(2026, 2, 28)
    r2 = complete_task(r1.task, D(2026, 3, 31), now_iso=NOW)
    assert r2.task.next_due == D(2026, 4, 30)


# --- fixed dates ----------------------------------------------------------------


def test_leap_day_fixed_date_falls_on_feb_28_in_non_leap_years() -> None:
    sched = Schedule.fixed((2, 29))
    assert fixed_dates_in_year(sched, 2027) == [D(2027, 2, 28)]
    assert fixed_dates_in_year(sched, 2028) == [D(2028, 2, 29)]
    assert initial_next_due(sched, D(2027, 1, 1)) == D(2027, 2, 28)


def test_fixed_dates_are_sorted_regardless_of_input_order() -> None:
    sched = Schedule.fixed((10, 1), (4, 1))
    assert fixed_dates_in_year(sched, 2026) == [D(2026, 4, 1), D(2026, 10, 1)]


@pytest.mark.parametrize(
    ("setup", "expected"),
    [
        (D(2026, 1, 1), D(2026, 4, 1)),
        (D(2026, 4, 1), D(2026, 4, 1)),  # on the date itself
        (D(2026, 4, 2), D(2026, 10, 1)),
        (D(2026, 11, 22), D(2027, 4, 1)),  # wraps around the year end
    ],
)
def test_initial_next_due_fixed_multiple_dates(setup: date, expected: date) -> None:
    assert initial_next_due(SPRING_AUTUMN, setup) == expected


def test_initial_next_due_interval() -> None:
    assert initial_next_due(QUARTERLY, D(2026, 11, 22)) == D(2027, 2, 22)
    assert initial_next_due(Schedule.interval(7, "years"), D(2026, 11, 22)) == D(2033, 11, 22)


# --- fixed completion -------------------------------------------------------------


def test_fixed_completion_early() -> None:
    task = make_task(DEC_1, D(2026, 12, 1))
    r = complete_task(task, D(2026, 11, 25), now_iso=NOW)
    assert r.task.next_due == D(2027, 12, 1)
    assert r.task.last_completed == D(2026, 11, 25)
    assert r.entry.occurrence_date == D(2026, 12, 1)
    assert r.entry.completed_on == D(2026, 11, 25)


def test_fixed_completion_on_time() -> None:
    task = make_task(SPRING_AUTUMN, D(2026, 4, 1))
    r = complete_task(task, D(2026, 4, 1), now_iso=NOW)
    assert r.task.next_due == D(2026, 10, 1)
    assert r.entry.occurrence_date == D(2026, 4, 1)


def test_fixed_completion_overdue() -> None:
    task = make_task(Schedule.fixed((10, 1)), D(2026, 10, 1))
    r = complete_task(task, D(2026, 11, 22), now_iso=NOW)
    assert r.task.next_due == D(2027, 10, 1)
    assert r.entry.occurrence_date == D(2026, 10, 1)


def test_fixed_completion_closes_multiple_missed_occurrences() -> None:
    # Due 1 Apr 2026, never done; completed 22 Nov 2026 → 1 Oct is also closed.
    task = make_task(SPRING_AUTUMN, D(2026, 4, 1))
    r = complete_task(task, D(2026, 11, 22), now_iso=NOW)
    assert r.task.next_due == D(2027, 4, 1)
    assert r.entry.occurrence_date == D(2026, 4, 1)


def test_fixed_completion_years_overdue() -> None:
    task = make_task(DEC_1, D(2023, 12, 1))
    r = complete_task(task, D(2026, 6, 1), now_iso=NOW)
    assert r.task.next_due == D(2026, 12, 1)


# --- interval completion ---------------------------------------------------------------


def test_interval_completion_resets_from_completion_date() -> None:
    task = make_task(QUARTERLY, D(2026, 3, 1))
    early = complete_task(task, D(2026, 2, 10), now_iso=NOW)
    assert early.task.next_due == D(2026, 5, 10)
    late = complete_task(task, D(2026, 4, 20), now_iso=NOW)
    assert late.task.next_due == D(2026, 7, 20)
    assert late.entry.occurrence_date == D(2026, 3, 1)
    assert late.task.last_completed == D(2026, 4, 20)


def test_interval_every_n_years() -> None:
    task = make_task(Schedule.interval(7, "years"), D(2030, 1, 1))
    r = complete_task(task, D(2026, 6, 15), now_iso=NOW)
    assert r.task.next_due == D(2033, 6, 15)


def test_completion_records_user_note_and_snapshot() -> None:
    task = make_task(YEARLY, D(2026, 6, 1), last_completed=D(2025, 6, 1))
    r = complete_task(
        task, D(2026, 6, 2), now_iso=NOW, user_id="u1", user_name="Ola", note="Ok", forced=True
    )
    e = r.entry
    assert (e.user_id, e.user_name, e.note, e.forced) == ("u1", "Ola", "Ok", True)
    assert e.prev_next_due == D(2026, 6, 1)
    assert e.prev_last_completed == D(2025, 6, 1)
    assert e.task_id == task.id


# --- undo ------------------------------------------------------------------------


@pytest.mark.parametrize("schedule", [QUARTERLY, SPRING_AUTUMN])
def test_undo_restores_previous_state_exactly(schedule: Schedule) -> None:
    task = make_task(schedule, D(2026, 4, 1), last_completed=D(2025, 10, 3))
    r = complete_task(task, D(2026, 11, 22), now_iso="2026-11-22T10:00:00+00:00")
    restored = undo_completion(r.task, r.entry, now_iso=NOW)
    assert restored.next_due == task.next_due
    assert restored.last_completed == task.last_completed
    assert restored.evolve(updated_at="") == task.evolve(updated_at="")


def test_undo_rejects_foreign_entry() -> None:
    task = make_task(QUARTERLY, D(2026, 4, 1))
    r = complete_task(task, D(2026, 4, 1), now_iso=NOW)
    with pytest.raises(ValueError):
        undo_completion(task.evolve(id="other"), r.entry, now_iso=NOW)


# --- status ------------------------------------------------------------------------


@pytest.mark.parametrize(
    ("today", "expected"),
    [
        (D(2026, 11, 16), "ok"),  # one day before the window
        (D(2026, 11, 17), "due_soon"),  # exactly next_due - due_soon_days
        (D(2026, 12, 1), "due_soon"),  # exactly next_due
        (D(2026, 12, 2), "overdue"),  # one day after
    ],
)
def test_status_boundaries(today: date, expected: str) -> None:
    assert compute_status(D(2026, 12, 1), 14, today) == expected


def test_status_with_zero_due_soon_days() -> None:
    assert compute_status(D(2026, 12, 1), 0, D(2026, 11, 30)) == "ok"
    assert compute_status(D(2026, 12, 1), 0, D(2026, 12, 1)) == "due_soon"


# --- due_soon_days defaults ------------------------------------------------------------


@pytest.mark.parametrize(
    ("schedule", "expected"),
    [
        (Schedule.interval(1, "months"), 3),
        (Schedule.interval(2, "months"), 7),
        (Schedule.interval(3, "months"), 7),
        (Schedule.interval(6, "months"), 14),
        (Schedule.interval(1, "years"), 21),
        (Schedule.interval(12, "months"), 21),
        (Schedule.interval(2, "years"), 60),
        (Schedule.interval(7, "years"), 60),
        (Schedule.fixed((12, 1)), 21),  # one date per year = 12 months
        (Schedule.fixed((4, 1), (10, 1)), 14),  # 6 months apart
        (Schedule.fixed((1, 1), (4, 1), (7, 1), (10, 1)), 7),  # quarterly
        (Schedule.fixed((1, 15), (3, 1)), 7),  # 1.5 months
        (Schedule.fixed((12, 20), (1, 5)), 3),  # wrap-around gap is the shortest
        (Schedule.fixed((3, 1), (10, 1)), 14),  # gaps 7 and 5 months; shortest counts
    ],
)
def test_default_due_soon_days(schedule: Schedule, expected: int) -> None:
    assert default_due_soon_days(schedule) == expected


def test_period_months_wraps_at_year_end() -> None:
    assert period_months(Schedule.fixed((11, 1), (2, 1))) == pytest.approx(3.0)


# --- early-completion guard -------------------------------------------------------


def test_early_completion_guard_only_blocks_fixed_tasks_outside_window() -> None:
    fixed = make_task(DEC_1, D(2026, 12, 1), due_soon_days=14)
    assert is_early_completion_blocked(fixed, D(2026, 11, 1))
    assert not is_early_completion_blocked(fixed, D(2026, 11, 17))
    assert not is_early_completion_blocked(fixed, D(2026, 12, 5))
    interval = make_task(QUARTERLY, D(2026, 12, 1))
    assert not is_early_completion_blocked(interval, D(2026, 1, 1))


# --- last done -----------------------------------------------------------------------


def test_next_due_from_last_done() -> None:
    assert next_due_from_last_done(QUARTERLY, D(2026, 8, 31)) == D(2026, 11, 30)
    assert next_due_from_last_done(SPRING_AUTUMN, D(2026, 4, 1)) == D(2026, 10, 1)
    assert next_due_from_last_done(SPRING_AUTUMN, D(2026, 5, 3)) == D(2026, 10, 1)


# --- year projection ---------------------------------------------------------------


def test_project_year_fixed() -> None:
    task = make_task(SPRING_AUTUMN, D(2026, 4, 1))
    # Done on time in spring.
    r = complete_task(task, D(2026, 4, 3), now_iso=NOW)
    occ = project_year(r.task, 2026, [r.entry], today=D(2026, 9, 20))
    assert [(o.date, o.status) for o in occ] == [
        (D(2026, 4, 1), "done"),
        (D(2026, 10, 1), "due_soon"),
    ]
    # Next year: both upcoming relative to an early "today".
    occ = project_year(r.task, 2027, [r.entry], today=D(2026, 9, 1))
    assert [o.status for o in occ] == ["upcoming", "upcoming"]


def test_project_year_fixed_missed_after_multi_close() -> None:
    task = make_task(SPRING_AUTUMN, D(2026, 4, 1))
    r = complete_task(task, D(2026, 11, 22), now_iso=NOW)
    occ = project_year(r.task, 2026, [r.entry], today=D(2026, 11, 22))
    assert [(o.date, o.status) for o in occ] == [
        (D(2026, 4, 1), "done"),
        (D(2026, 10, 1), "missed"),
    ]


def test_project_year_fixed_overdue_and_later_past_dates() -> None:
    task = make_task(SPRING_AUTUMN, D(2026, 4, 1))
    occ = project_year(task, 2026, [], today=D(2026, 11, 22))
    assert [o.status for o in occ] == ["overdue", "overdue"]


def test_project_year_fixed_skips_dates_before_creation() -> None:
    task = make_task(SPRING_AUTUMN, D(2026, 10, 1), created_at="2026-06-01T12:00:00+00:00")
    occ = project_year(task, 2026, [], today=D(2026, 6, 1))
    assert [(o.date, o.status) for o in occ] == [(D(2026, 10, 1), "upcoming")]


def test_project_year_interval() -> None:
    task = make_task(QUARTERLY, D(2026, 3, 1), due_soon_days=7)
    r1 = complete_task(task, D(2026, 3, 2), now_iso=NOW)  # next 2 Jun
    r2 = complete_task(r1.task, D(2026, 6, 5), now_iso=NOW)  # next 5 Sep
    occ = project_year(r2.task, 2026, [r1.entry, r2.entry], today=D(2026, 9, 1))
    assert [(o.date, o.status) for o in occ] == [
        (D(2026, 3, 2), "done"),
        (D(2026, 6, 5), "done"),
        (D(2026, 9, 5), "due_soon"),
        (D(2026, 12, 5), "upcoming"),
    ]


def test_project_year_interval_overdue_and_multi_year() -> None:
    task = make_task(QUARTERLY, D(2026, 2, 1))
    occ = project_year(task, 2026, [], today=D(2026, 3, 1))
    assert occ[0].status == "overdue"
    assert [o.date for o in occ] == [D(2026, 2, 1), D(2026, 5, 1), D(2026, 8, 1), D(2026, 11, 1)]
    long = make_task(Schedule.interval(7, "years"), D(2033, 5, 1))
    assert project_year(long, 2027, [], today=D(2026, 1, 1)) == []
    assert [o.date for o in project_year(long, 2033, [], today=D(2026, 1, 1))] == [D(2033, 5, 1)]


def test_project_year_ignores_other_tasks_log() -> None:
    task = make_task(QUARTERLY, D(2026, 3, 1))
    other = complete_task(task.evolve(id="other"), D(2026, 1, 5), now_iso=NOW).entry
    occ = project_year(task, 2026, [other], today=D(2026, 1, 1))
    assert all(o.status != "done" for o in occ)


# --- descriptions --------------------------------------------------------------------


def test_describe_schedule() -> None:
    assert describe_schedule(QUARTERLY, "nb") == "Hvert kvartal"
    assert describe_schedule(Schedule.interval(7, "years"), "nb") == "Hvert 7. år"
    assert describe_schedule(SPRING_AUTUMN, "nb") == "Årlig 1. apr, 1. okt"
    assert describe_schedule(SPRING_AUTUMN, "en") == "Yearly on Apr 1, Oct 1"
    assert describe_schedule(YEARLY, "en") == "Yearly"
