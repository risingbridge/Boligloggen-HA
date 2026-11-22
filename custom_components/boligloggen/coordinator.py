"""In-memory state for one property: tasks, log, mutations and persistence.

All business rules live in ``planner``; this module wires them to Home
Assistant (storage, users, events, entity registry).
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterable
from datetime import date
from typing import TYPE_CHECKING, Any

from homeassistant.auth.models import User
from homeassistant.core import CALLBACK_TYPE, Context, HomeAssistant, callback
from homeassistant.exceptions import ServiceValidationError, Unauthorized
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util

from .const import (
    AGGREGATE_KINDS,
    CONF_DESELECTED,
    CONF_LANGUAGE,
    CONF_PROFILE,
    CONF_SELECTED,
    DOMAIN,
    EVENT_TASK_COMPLETED,
    EVENT_TASK_DUE_SOON,
    EVENT_TASK_OVERDUE,
    KIND_BUTTON,
    KIND_SENSOR,
    SCHEMA_VERSION,
    SYSTEM_USER_NAME,
)
from .planner import (
    Catalog,
    LogEntry,
    PropertyProfile,
    Schedule,
    Suggestion,
    Task,
    complete_task,
    custom_task,
    default_due_soon_days,
    is_early_completion_blocked,
    next_due_from_last_done,
    normalize_language,
    project_year,
    seed_tasks,
    suggest,
    task_status,
    undo_completion,
)
from .planner.seeding import expand_template
from .planner.transfer import PlanSnapshot
from .store import BoligloggenStore, empty_feedback

if TYPE_CHECKING:
    from homeassistant.config_entries import ConfigEntry

_LOGGER = logging.getLogger(__name__)

UNKNOWN_USER_NAME = {"nb": "Ukjent", "en": "Unknown"}
SAVE_DELAY = 1


def _err(key: str, **placeholders: str) -> ServiceValidationError:
    return ServiceValidationError(
        translation_domain=DOMAIN,
        translation_key=key,
        translation_placeholders=placeholders or None,
    )


def unique_id_for(entry_id: str, task_id: str, kind: str) -> str:
    return f"{entry_id}_{task_id}_{kind}"


class BoligloggenCoordinator:
    """State and mutations for one property."""

    def __init__(self, hass: HomeAssistant, entry: ConfigEntry, catalog: Catalog) -> None:
        self.hass = hass
        self.entry = entry
        self.catalog = catalog
        self.store = BoligloggenStore(hass, entry.entry_id)
        self.language: str = normalize_language(
            entry.data.get(CONF_LANGUAGE) or hass.config.language
        )
        self.profile: PropertyProfile = PropertyProfile.from_dict(entry.data[CONF_PROFILE])
        self.catalog_version = catalog.version
        self.tasks: dict[str, Task] = {}
        self.log: list[LogEntry] = []
        self.feedback: dict[str, list[str]] = empty_feedback()
        self._listeners: list[CALLBACK_TYPE] = []

    # ------------------------------------------------------------------
    # Lifecycle and persistence
    # ------------------------------------------------------------------

    @property
    def entry_id(self) -> str:
        return self.entry.entry_id

    def today(self) -> date:
        return dt_util.now().date()

    def now_iso(self) -> str:
        return dt_util.utcnow().isoformat()

    async def async_load(self) -> None:
        data = await self.store.async_load()
        if data is None:
            self._seed_from_entry()
            await self.store.async_save(self.data_to_save())
            return
        self.profile = PropertyProfile.from_dict(data["profile"])
        self.language = data.get("language") or self.language
        self.catalog_version = data.get("catalog_version", self.catalog.version)
        self.tasks = {t["id"]: Task.from_dict(t) for t in data.get("tasks", [])}
        self.log = [LogEntry.from_dict(e) for e in data.get("log", [])]
        self.feedback = data.get("onboarding_feedback") or empty_feedback()

    def _seed_from_entry(self) -> None:
        today = self.today()
        selected = set(self.entry.data.get(CONF_SELECTED, []))
        suggestions = [s for s in suggest(self.catalog, self.profile, today) if s.key in selected]
        tasks = seed_tasks(
            suggestions, lang=self.language, setup_date=today, now_iso=self.now_iso()
        )
        self.tasks = {t.id: self._with_current_state(t, today) for t in tasks}
        self.feedback = empty_feedback()
        self.feedback["deselected_at_review"] = list(self.entry.data.get(CONF_DESELECTED, []))
        _LOGGER.debug("Seeded %d tasks for %s", len(self.tasks), self.profile.name)

    def data_to_save(self) -> dict[str, Any]:
        return {
            "schema_version": SCHEMA_VERSION,
            "catalog_version": self.catalog_version,
            "language": self.language,
            "profile": self.profile.to_dict(),
            "tasks": [t.to_dict() for t in self.tasks.values()],
            "log": [e.to_dict() for e in self.log],
            "onboarding_feedback": self.feedback,
        }

    @callback
    def async_add_listener(self, update_callback: CALLBACK_TYPE) -> Callable[[], None]:
        self._listeners.append(update_callback)

        @callback
        def remove() -> None:
            self._listeners.remove(update_callback)

        return remove

    @callback
    def _changed(self) -> None:
        self.store.async_delay_save(self.data_to_save, SAVE_DELAY)
        for listener in list(self._listeners):
            listener()

    # ------------------------------------------------------------------
    # Queries
    # ------------------------------------------------------------------

    @property
    def active_tasks(self) -> list[Task]:
        return [t for t in self.tasks.values() if t.is_active]

    @property
    def archived_tasks(self) -> list[Task]:
        return [t for t in self.tasks.values() if not t.is_active]

    def get_task(self, task_id: str) -> Task:
        task = self.tasks.get(task_id)
        if task is None:
            raise _err("task_not_found", task_id=task_id)
        return task

    def get_active_task(self, task_id: str) -> Task:
        task = self.get_task(task_id)
        if not task.is_active:
            raise _err("task_archived", title=task.title)
        return task

    def latest_entry(self, task_id: str | None = None) -> LogEntry | None:
        for entry in reversed(self.log):
            if task_id is None or entry.task_id == task_id:
                return entry
        return None

    def matched_suggestions(self, *, show_all: bool = False) -> list[Suggestion]:
        """Catalog suggestions without a task (active or archived) yet."""
        known = {t.key for t in self.tasks.values() if t.key}
        if show_all:
            candidates = [s for t in self.catalog for s in expand_template(t, self.profile)]
        else:
            candidates = suggest(self.catalog, self.profile, self.today())
        return [s for s in candidates if s.key not in known]

    def year_plan(self, year: int) -> list[dict[str, Any]]:
        today = self.today()
        return [
            {
                "task_id": t.id,
                "title": t.title,
                "category": t.category,
                "schedule_type": t.schedule.type,
                "occurrences": [o.to_dict() for o in project_year(t, year, self.log, today)],
            }
            for t in self.active_tasks
        ]

    def occurrences_between(self, start: date, end: date) -> list[tuple[Task, date, str]]:
        """Projected occurrences of active tasks in ``[start, end]`` (inclusive)."""
        today = self.today()
        result: list[tuple[Task, date, str]] = []
        for year in range(start.year, end.year + 1):
            for task in self.active_tasks:
                for occ in project_year(task, year, self.log, today):
                    if start <= occ.date <= end:
                        result.append((task, occ.date, occ.status))
        result.sort(key=lambda item: item[1])
        return result

    # ------------------------------------------------------------------
    # Users
    # ------------------------------------------------------------------

    async def async_get_user(self, context: Context | None) -> User | None:
        if context is None or context.user_id is None:
            return None
        return await self.hass.auth.async_get_user(context.user_id)

    async def _user_snapshot(self, context: Context | None) -> tuple[str | None, str]:
        if context is None or context.user_id is None:
            return None, SYSTEM_USER_NAME
        user = await self.hass.auth.async_get_user(context.user_id)
        if user is None:
            return context.user_id, UNKNOWN_USER_NAME.get(self.language, "Unknown")
        return user.id, user.name or UNKNOWN_USER_NAME.get(self.language, "Unknown")

    # ------------------------------------------------------------------
    # Completion
    # ------------------------------------------------------------------

    async def async_complete(
        self,
        task_id: str,
        *,
        context: Context | None,
        completed_on: date | None = None,
        note: str | None = None,
        force: bool = False,
    ) -> LogEntry:
        task = self.get_active_task(task_id)
        today = self.today()
        completed_on = completed_on or today
        if completed_on > today:
            raise _err("completed_on_in_future")
        if not force and is_early_completion_blocked(task, today):
            window_start = date.fromordinal(task.next_due.toordinal() - task.due_soon_days)
            raise _err("not_due_yet", date=window_start.isoformat(), title=task.title)

        user_id, user_name = await self._user_snapshot(context)
        result = complete_task(
            task,
            completed_on,
            now_iso=self.now_iso(),
            user_id=user_id,
            user_name=user_name,
            note=note or None,
            forced=force,
        )
        self.tasks[task.id] = self._with_current_state(result.task, today)
        self.log.append(result.entry)
        self._changed()
        self.hass.bus.async_fire(
            EVENT_TASK_COMPLETED,
            {
                "config_entry_id": self.entry_id,
                "property_name": self.profile.name,
                "task_id": task.id,
                "title": task.title,
                "user_id": user_id,
                "user_name": user_name,
                "completed_on": completed_on.isoformat(),
                "occurrence_date": result.entry.occurrence_date.isoformat(),
                "note": result.entry.note,
                "forced": force,
            },
            context=context,
        )
        return result.entry

    async def async_undo(self, task_id: str, *, context: Context | None) -> LogEntry:
        task = self.get_active_task(task_id)
        entry = self.latest_entry(task_id)
        if entry is None:
            raise _err("nothing_to_undo", title=task.title)
        user = await self.async_get_user(context)
        if user is not None and not user.is_admin and user.id != entry.user_id:
            raise Unauthorized(context=context)
        self.tasks[task.id] = self._with_current_state(
            undo_completion(task, entry, now_iso=self.now_iso()), self.today()
        )
        self.log.remove(entry)
        self._changed()
        return entry

    # ------------------------------------------------------------------
    # Plan editing
    # ------------------------------------------------------------------

    def _with_current_state(self, task: Task, today: date | None = None) -> Task:
        """Sync ``last_notified_state`` without firing events (completions/edits)."""
        return task.evolve(last_notified_state=task_status(task, today or self.today()))

    def _record_feedback(self, bucket: str, keys: Iterable[str | None]) -> None:
        """Record template keys (``id`` or ``id#n``); custom tasks have none."""
        values = self.feedback.setdefault(bucket, [])
        for key in keys:
            if key and key not in values:
                values.append(key)

    @callback
    def async_add_from_catalog(self, keys: Iterable[str]) -> list[Task]:
        keys = set(keys)
        known = {t.key for t in self.tasks.values() if t.key}
        candidates = [s for t in self.catalog for s in expand_template(t, self.profile)]
        chosen = [s for s in candidates if s.key in keys and s.key not in known]
        missing = keys - {s.key for s in candidates}
        if missing:
            raise _err("unknown_template", template_id=", ".join(sorted(missing)))
        return self._add_tasks(
            seed_tasks(chosen, lang=self.language, setup_date=self.today(), now_iso=self.now_iso())
        )

    @callback
    def async_add_custom(
        self,
        *,
        title: str,
        category: str,
        schedule: Schedule,
        description: str = "",
        due_soon_days: int | None = None,
    ) -> Task:
        task = custom_task(
            title=title,
            category=category,
            schedule=schedule,
            description=description,
            due_soon_days=due_soon_days,
            setup_date=self.today(),
            now_iso=self.now_iso(),
        )
        return self._add_tasks([task])[0]

    def _add_tasks(self, tasks: list[Task]) -> list[Task]:
        today = self.today()
        for task in tasks:
            self.tasks[task.id] = self._with_current_state(task, today)
        self._record_feedback("added_later", (t.key for t in tasks))
        self._changed()
        return tasks

    @callback
    def async_update_task(
        self,
        task_id: str,
        *,
        title: str | None = None,
        description: str | None = None,
        category: str | None = None,
        schedule: Schedule | None = None,
        due_soon_days: int | None = None,
        last_completed: date | None = None,
        next_due: date | None = None,
    ) -> Task:
        task = self.get_task(task_id)
        changes: dict[str, Any] = {}
        if title is not None:
            if not title.strip():
                raise _err("title_required")
            changes["title"] = title.strip()
        if description is not None:
            changes["description"] = description
        if category is not None:
            changes["category"] = category
        if schedule is not None and schedule != task.schedule:
            changes["schedule"] = schedule
            if due_soon_days is None and task.due_soon_days == default_due_soon_days(task.schedule):
                changes["due_soon_days"] = default_due_soon_days(schedule)
        if due_soon_days is not None:
            changes["due_soon_days"] = due_soon_days
        effective_schedule: Schedule = changes.get("schedule", task.schedule)
        if last_completed is not None:
            if last_completed > self.today():
                raise _err("completed_on_in_future")
            changes["last_completed"] = last_completed
            changes["next_due"] = next_due_from_last_done(effective_schedule, last_completed)
        if next_due is not None:
            changes["next_due"] = next_due
        if not changes:
            return task
        changes["updated_at"] = self.now_iso()
        updated = self._with_current_state(task.evolve(**changes))
        self.tasks[task.id] = updated
        self._changed()
        return updated

    @callback
    def async_archive(self, task_ids: Iterable[str]) -> list[Task]:
        archived: list[Task] = []
        now = self.now_iso()
        for task_id in task_ids:
            task = self.get_task(task_id)
            if not task.is_active:
                continue
            self.tasks[task.id] = task.evolve(status="archived", updated_at=now)
            archived.append(task)
        if archived:
            self._remove_entities(t.id for t in archived)
            self._record_feedback("removed_later", (t.key for t in archived))
            self._changed()
        return archived

    @callback
    def async_restore(self, task_ids: Iterable[str]) -> list[Task]:
        restored: list[Task] = []
        now = self.now_iso()
        for task_id in task_ids:
            task = self.get_task(task_id)
            if task.is_active:
                continue
            updated = self._with_current_state(task.evolve(status="active", updated_at=now))
            self.tasks[task.id] = updated
            restored.append(updated)
        if restored:
            removed = self.feedback.get("removed_later", [])
            for task in restored:
                if task.key in removed:
                    removed.remove(task.key)
            self._changed()
        return restored

    @callback
    def async_update_profile(
        self,
        profile: PropertyProfile,
        *,
        add_keys: Iterable[str] = (),
        remove_task_ids: Iterable[str] = (),
    ) -> None:
        old_name = self.profile.name
        self.profile = profile
        add_keys = list(add_keys)
        remove_task_ids = list(remove_task_ids)
        if add_keys:
            self.async_add_from_catalog(add_keys)
        if remove_task_ids:
            self.async_archive(remove_task_ids)
        if profile.name != old_name:
            self._rename_device(profile.name)
        self._changed()

    @callback
    def async_import(self, snapshot: PlanSnapshot, *, include_history: bool) -> None:
        """Replace profile and tasks (and optionally the log) with an import.

        Imported task ids are kept, so importing a backup into the same property
        keeps entity IDs, dashboards and automations working. Due-state is synced
        without firing events, like after an edit. Without ``include_history`` the
        current log is kept as it is.
        """
        today = self.today()
        old_active = {t.id for t in self.active_tasks}
        old_name = self.profile.name
        self.profile = snapshot.profile
        if snapshot.language:
            self.language = snapshot.language
        self.tasks = {
            t.id: self._with_current_state(t, today) if t.is_active else t for t in snapshot.tasks
        }
        if include_history:
            self.log = list(snapshot.log)
        self.feedback = {k: list(v) for k, v in snapshot.feedback.items()} or empty_feedback()
        self._remove_entities(old_active - {t.id for t in self.active_tasks})
        if self.profile.name != old_name:
            self._rename_device(self.profile.name)
        self._changed()
        _LOGGER.info(
            "Imported %d tasks (%d active)%s into %s",
            len(self.tasks),
            len(self.active_tasks),
            f" and {len(self.log)} log entries" if include_history else "",
            self.profile.name,
        )

    def _rename_device(self, name: str) -> None:
        device_registry = dr.async_get(self.hass)
        device = device_registry.async_get_device(identifiers={(DOMAIN, self.entry_id)})
        if device is not None:
            device_registry.async_update_device(device.id, name=name)
        self.hass.config_entries.async_update_entry(self.entry, title=name)

    def _remove_entities(self, task_ids: Iterable[str]) -> None:
        registry = er.async_get(self.hass)
        for task_id in task_ids:
            for domain, kind in (("sensor", KIND_SENSOR), ("button", KIND_BUTTON)):
                entity_id = registry.async_get_entity_id(
                    domain, DOMAIN, unique_id_for(self.entry_id, task_id, kind)
                )
                if entity_id:
                    registry.async_remove(entity_id)

    @callback
    def async_remove_orphaned_entities(self) -> None:
        """Remove registry entries for tasks that are no longer active."""
        registry = er.async_get(self.hass)
        valid = {f"{self.entry_id}_{kind}" for kind in AGGREGATE_KINDS}
        valid.add(f"{self.entry_id}_calendar")
        for task in self.active_tasks:
            valid.add(unique_id_for(self.entry_id, task.id, KIND_SENSOR))
            valid.add(unique_id_for(self.entry_id, task.id, KIND_BUTTON))
        for entity in er.async_entries_for_config_entry(registry, self.entry_id):
            if entity.unique_id not in valid:
                _LOGGER.debug("Removing orphaned entity %s", entity.entity_id)
                registry.async_remove(entity.entity_id)

    def entity_id_for(self, task_id: str, kind: str) -> str | None:
        domain = "sensor" if kind == KIND_SENSOR else "button"
        return er.async_get(self.hass).async_get_entity_id(
            domain, DOMAIN, unique_id_for(self.entry_id, task_id, kind)
        )

    # ------------------------------------------------------------------
    # Daily scan: fire due-soon/overdue events once per transition
    # ------------------------------------------------------------------

    @callback
    def async_scan(self) -> None:
        today = self.today()
        changed = False
        for task in self.active_tasks:
            status = task_status(task, today)
            previous = task.last_notified_state
            if status == previous:
                continue
            changed = True
            self.tasks[task.id] = task.evolve(last_notified_state=status)
            if status == "due_soon" and previous == "ok":
                self._fire_due_event(EVENT_TASK_DUE_SOON, task, status, today)
            elif status == "overdue":
                self._fire_due_event(EVENT_TASK_OVERDUE, task, status, today)
        if changed:
            self.store.async_delay_save(self.data_to_save, SAVE_DELAY)
        # Always refresh entities: days_until_due changes every day.
        for listener in list(self._listeners):
            listener()

    def _fire_due_event(self, event_type: str, task: Task, status: str, today: date) -> None:
        self.hass.bus.async_fire(
            event_type,
            {
                "config_entry_id": self.entry_id,
                "property_name": self.profile.name,
                "task_id": task.id,
                "title": task.title,
                "next_due": task.next_due.isoformat(),
                "days_until_due": (task.next_due - today).days,
                "status": status,
                "entity_id": self.entity_id_for(task.id, KIND_SENSOR),
            },
        )
