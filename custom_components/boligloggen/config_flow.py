"""Onboarding config flow (blocks A–D + review) and plan-editing options flow."""

from __future__ import annotations

from collections.abc import Callable
from datetime import date
from typing import TYPE_CHECKING, Any

import voluptuous as vol
from homeassistant.config_entries import (
    ConfigEntry,
    ConfigFlow,
    ConfigFlowResult,
    OptionsFlow,
)
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import selector as sel
from homeassistant.util import dt as dt_util

from .catalog_loader import async_get_catalog
from .const import (
    CATEGORY_LABELS,
    CONF_DESELECTED,
    CONF_LANGUAGE,
    CONF_PROFILE,
    CONF_SELECTED,
    DOMAIN,
)
from .planner import (
    PropertyProfile,
    Suggestion,
    Task,
    normalize_language,
    plan_diff,
    suggest,
)
from .planner import models as m
from .schedule_input import ScheduleInputError, build_schedule, format_dates

if TYPE_CHECKING:
    from .coordinator import BoligloggenCoordinator

OUTDOOR_TYPES = ("house", "townhouse", "cabin")


# ---------------------------------------------------------------------------
# Selector helpers
# ---------------------------------------------------------------------------


def _select(
    options: tuple[Any, ...] | list[str],
    key: str,
    *,
    multiple: bool = False,
    mode: sel.SelectSelectorMode = sel.SelectSelectorMode.LIST,
) -> sel.SelectSelector:
    return sel.SelectSelector(
        sel.SelectSelectorConfig(
            options=[str(o) for o in options],
            translation_key=key,
            multiple=multiple,
            mode=mode,
        )
    )


def _labelled_select(
    options: list[sel.SelectOptionDict], *, multiple: bool = True
) -> sel.SelectSelector:
    return sel.SelectSelector(
        sel.SelectSelectorConfig(
            options=options, multiple=multiple, mode=sel.SelectSelectorMode.LIST
        )
    )


def _category_label(category: str, lang: str) -> str:
    return CATEGORY_LABELS.get(lang, CATEGORY_LABELS["en"]).get(category, category)


def _suggestion_options(suggestions: list[Suggestion], lang: str) -> list[sel.SelectOptionDict]:
    ordered = sorted(suggestions, key=lambda s: (m.CATEGORIES.index(s.template.category), s.key))
    return [
        sel.SelectOptionDict(
            value=s.key, label=f"{_category_label(s.template.category, lang)} · {s.title(lang)}"
        )
        for s in ordered
    ]


def _task_options(tasks: list[Task], lang: str) -> list[sel.SelectOptionDict]:
    ordered = sorted(tasks, key=lambda t: (m.CATEGORIES.index(t.category), t.title))
    return [
        sel.SelectOptionDict(value=t.id, label=f"{_category_label(t.category, lang)} · {t.title}")
        for t in ordered
    ]


# ---------------------------------------------------------------------------
# Shared profile steps (blocks A–D)
# ---------------------------------------------------------------------------


class ProfileStepsMixin:
    """Collects a ``PropertyProfile`` across conditional steps.

    ``self._answers`` accumulates the raw profile dict; ``self._defaults``
    pre-fills the forms (current profile when editing).
    """

    _answers: dict[str, Any]
    _defaults: dict[str, Any]

    # Provided by the flow base classes
    async_show_form: Callable[..., ConfigFlowResult]
    hass: HomeAssistant

    def _attr_default(self, key: str, fallback: Any) -> Any:
        return (self._defaults.get("attributes") or {}).get(key, fallback)

    def _basic_schema(self) -> vol.Schema:
        d = self._defaults
        current_year = dt_util.now().year
        schema: dict[Any, Any] = {
            vol.Required("name", default=d.get("name") or self.hass.config.location_name): str,
            vol.Optional("address", default=d.get("address") or ""): str,
            vol.Required("type", default=d.get("type", "house")): _select(
                m.PROPERTY_TYPES, "property_type"
            ),
        }
        build_year = d.get("build_year")
        schema[vol.Optional("build_year", description={"suggested_value": build_year})] = (
            sel.NumberSelector(
                sel.NumberSelectorConfig(
                    min=1700, max=current_year + 1, step=1, mode=sel.NumberSelectorMode.BOX
                )
            )
        )
        schema[vol.Optional("age_band", description={"suggested_value": d.get("age_band")})] = (
            _select(tuple(m.AGE_BANDS), "age_band")
        )
        return vol.Schema(schema)

    def _handle_basic(self, user_input: dict[str, Any]) -> dict[str, str]:
        errors: dict[str, str] = {}
        build_year = user_input.get("build_year")
        age_band = user_input.get("age_band") or None
        if build_year is None and age_band is None:
            errors["base"] = "age_required"
        if not str(user_input.get("name", "")).strip():
            errors["name"] = "name_required"
        if errors:
            return errors
        self._answers = {
            "name": user_input["name"].strip(),
            "address": user_input.get("address", "").strip(),
            "type": user_input["type"],
            "build_year": int(build_year) if build_year is not None else None,
            "age_band": age_band if build_year is None else None,
            "attributes": {},
        }
        return {}

    async def async_step_building(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        is_apartment = self._answers["type"] == "apartment"
        if user_input is not None:
            attrs = self._answers["attributes"]
            attrs["heating"] = list(user_input.get("heating") or [])
            attrs["ventilation"] = user_input["ventilation"]
            attrs["cladding"] = None if is_apartment else user_input.get("cladding")
            attrs["bathroom_count"] = int(user_input["bathroom_count"])
            if self._answers["type"] in OUTDOOR_TYPES:
                return await self.async_step_outdoor()
            return await self._async_profile_done()

        schema: dict[Any, Any] = {
            vol.Optional("heating", default=self._attr_default("heating", [])): _select(
                m.HEATING, "heating", multiple=True
            ),
            vol.Required(
                "ventilation", default=self._attr_default("ventilation", "unknown")
            ): _select(m.VENTILATION, "ventilation"),
        }
        if not is_apartment:
            schema[
                vol.Required("cladding", default=self._attr_default("cladding", None) or "wood")
            ] = _select(m.CLADDING, "cladding")
        schema[
            vol.Required(
                "bathroom_count", default=str(min(3, self._attr_default("bathroom_count", 1)))
            )
        ] = _select(m.BATHROOM_COUNTS, "bathroom_count")
        return self.async_show_form(step_id="building", data_schema=vol.Schema(schema))

    async def async_step_outdoor(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            attrs = self._answers["attributes"]
            attrs["garden"] = user_input["garden"] == "yes"
            for key in ("driveway", "deck", "garage", "water"):
                attrs[key] = user_input[key]
            if self._answers["type"] == "cabin":
                return await self.async_step_cabin()
            return await self._async_profile_done()

        garden_default = "yes" if self._attr_default("garden", False) else "no"
        schema = vol.Schema(
            {
                vol.Required("garden", default=garden_default): _select(("no", "yes"), "yes_no"),
                vol.Required("driveway", default=self._attr_default("driveway", "none")): _select(
                    m.DRIVEWAY, "driveway"
                ),
                vol.Required("deck", default=self._attr_default("deck", "none")): _select(
                    m.DECK, "deck"
                ),
                vol.Required("garage", default=self._attr_default("garage", "none")): _select(
                    m.GARAGE, "garage"
                ),
                vol.Required("water", default=self._attr_default("water", "public")): _select(
                    m.WATER, "water"
                ),
            }
        )
        return self.async_show_form(step_id="outdoor", data_schema=schema)

    async def async_step_cabin(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        if user_input is not None:
            attrs = self._answers["attributes"]
            attrs["cabin_winter_use"] = user_input["cabin_winter_use"]
            attrs["cabin_water"] = user_input["cabin_water"]
            return await self._async_profile_done()
        schema = vol.Schema(
            {
                vol.Required(
                    "cabin_winter_use",
                    default=self._attr_default("cabin_winter_use", None) or "closed",
                ): _select(m.CABIN_WINTER_USE, "cabin_winter_use"),
                vol.Required(
                    "cabin_water", default=self._attr_default("cabin_water", None) or "summer"
                ): _select(m.CABIN_WATER, "cabin_water"),
            }
        )
        return self.async_show_form(step_id="cabin", data_schema=schema)

    async def _async_profile_done(self) -> ConfigFlowResult:
        raise NotImplementedError

    def _profile(self) -> PropertyProfile:
        return PropertyProfile.from_dict(self._answers)


# ---------------------------------------------------------------------------
# Config flow (onboarding)
# ---------------------------------------------------------------------------


class BoligloggenConfigFlow(ProfileStepsMixin, ConfigFlow, domain=DOMAIN):
    """One flow per property."""

    VERSION = 1

    def __init__(self) -> None:
        self._answers = {}
        self._defaults = {}
        self._suggestions: list[Suggestion] = []

    @staticmethod
    @callback
    def async_get_options_flow(config_entry: ConfigEntry) -> BoligloggenOptionsFlow:
        return BoligloggenOptionsFlow()

    @property
    def _lang(self) -> str:
        return normalize_language(self.hass.config.language)

    async def async_step_user(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._handle_basic(user_input)
            if not errors:
                return await self.async_step_building()
            self._defaults = dict(user_input)
        return self.async_show_form(step_id="user", data_schema=self._basic_schema(), errors=errors)

    async def _async_profile_done(self) -> ConfigFlowResult:
        catalog = await async_get_catalog(self.hass)
        self._suggestions = suggest(catalog, self._profile(), dt_util.now().date())
        return await self.async_step_review()

    async def async_step_review(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        all_keys = [s.key for s in self._suggestions]
        if user_input is not None:
            selected = [k for k in all_keys if k in set(user_input.get("tasks", []))]
            deselected = [k for k in all_keys if k not in selected]
            return self.async_create_entry(
                title=self._answers["name"],
                data={
                    CONF_PROFILE: self._profile().to_dict(),
                    CONF_SELECTED: selected,
                    CONF_DESELECTED: deselected,
                    CONF_LANGUAGE: self._lang,
                },
            )
        schema = vol.Schema(
            {
                vol.Optional("tasks", default=all_keys): _labelled_select(
                    _suggestion_options(self._suggestions, self._lang)
                )
            }
        )
        return self.async_show_form(
            step_id="review",
            data_schema=schema,
            description_placeholders={
                "count": str(len(all_keys)),
                "name": self._answers["name"],
            },
        )


# ---------------------------------------------------------------------------
# Options flow (admin-only plan editing)
# ---------------------------------------------------------------------------

_MENU = ["add_catalog", "add_custom", "edit_task", "remove_task", "restore_task", "profile"]


class BoligloggenOptionsFlow(ProfileStepsMixin, OptionsFlow):
    def __init__(self) -> None:
        self._answers = {}
        self._defaults = {}
        self._show_all = False
        self._task_id: str | None = None
        self._diff_add: list[Suggestion] = []
        self._diff_remove: list[Task] = []

    @property
    def coordinator(self) -> BoligloggenCoordinator:
        coordinator: BoligloggenCoordinator = self.config_entry.runtime_data
        return coordinator

    @property
    def _lang(self) -> str:
        return str(self.coordinator.language)

    def _done(self) -> ConfigFlowResult:
        return self.async_create_entry(data={})

    async def async_step_init(self, user_input: dict[str, Any] | None = None) -> ConfigFlowResult:
        return self.async_show_menu(step_id="init", menu_options=_MENU)

    # --- add from catalog ----------------------------------------------------

    async def async_step_add_catalog(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            show_all = bool(user_input.get("show_all"))
            chosen = list(user_input.get("templates") or [])
            if show_all != self._show_all and not chosen:
                self._show_all = show_all
            else:
                if chosen:
                    self.coordinator.async_add_from_catalog(chosen)
                return self._done()

        candidates = self.coordinator.matched_suggestions(show_all=self._show_all)
        schema: dict[Any, Any] = {}
        if candidates:
            schema[vol.Optional("templates", default=[])] = _labelled_select(
                _suggestion_options(candidates, self._lang)
            )
        schema[vol.Optional("show_all", default=self._show_all)] = sel.BooleanSelector()
        return self.async_show_form(
            step_id="add_catalog",
            data_schema=vol.Schema(schema),
            description_placeholders={"count": str(len(candidates))},
        )

    # --- custom task / edit task ------------------------------------------------

    def _task_schema(self, task: Task | None) -> vol.Schema:
        schedule = task.schedule if task else None
        schema: dict[Any, Any] = {
            vol.Required("title", default=task.title if task else ""): str,
            vol.Optional("description", default=task.description if task else ""): (
                sel.TextSelector(sel.TextSelectorConfig(multiline=True))
            ),
            vol.Required("category", default=task.category if task else "indoor"): _select(
                m.CATEGORIES, "category", mode=sel.SelectSelectorMode.DROPDOWN
            ),
            vol.Required(
                "schedule_type", default=schedule.type if schedule else "interval"
            ): _select(("interval", "fixed"), "schedule_type"),
            vol.Optional(
                "every",
                default=schedule.every if schedule and schedule.type == "interval" else 1,
            ): sel.NumberSelector(
                sel.NumberSelectorConfig(min=1, max=50, step=1, mode=sel.NumberSelectorMode.BOX)
            ),
            vol.Optional(
                "unit",
                default=schedule.unit if schedule and schedule.type == "interval" else "years",
            ): _select(("months", "years"), "unit"),
            vol.Optional(
                "dates",
                default=format_dates(schedule) if schedule and schedule.type == "fixed" else "",
            ): str,
            vol.Optional(
                "due_soon_days",
                description={"suggested_value": task.due_soon_days if task else None},
            ): sel.NumberSelector(
                sel.NumberSelectorConfig(min=0, max=3650, step=1, mode=sel.NumberSelectorMode.BOX)
            ),
        }
        if task is not None:
            schema[
                vol.Optional(
                    "last_completed",
                    description={
                        "suggested_value": task.last_completed.isoformat()
                        if task.last_completed
                        else None
                    },
                )
            ] = sel.DateSelector()
            schema[vol.Required("next_due", default=task.next_due.isoformat())] = sel.DateSelector()
        return vol.Schema(schema)

    @staticmethod
    def _parse_task_input(user_input: dict[str, Any]) -> tuple[Any, dict[str, str]]:
        try:
            schedule = build_schedule(
                user_input["schedule_type"],
                every=int(user_input["every"]) if user_input.get("every") else None,
                unit=user_input.get("unit"),
                dates=user_input.get("dates"),
            )
        except ScheduleInputError as err:
            field = "dates" if user_input["schedule_type"] == "fixed" else "every"
            return None, {field: err.key}
        if not user_input.get("title", "").strip():
            return None, {"title": "title_required"}
        return schedule, {}

    async def async_step_add_custom(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        errors: dict[str, str] = {}
        if user_input is not None:
            schedule, errors = self._parse_task_input(user_input)
            if not errors:
                dsd = user_input.get("due_soon_days")
                self.coordinator.async_add_custom(
                    title=user_input["title"].strip(),
                    description=user_input.get("description", ""),
                    category=user_input["category"],
                    schedule=schedule,
                    due_soon_days=int(dsd) if dsd is not None else None,
                )
                return self._done()
        schema = self._task_schema(None)
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(step_id="add_custom", data_schema=schema, errors=errors)

    async def async_step_edit_task(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        tasks = self.coordinator.active_tasks
        if not tasks:
            return self.async_abort(reason="no_tasks")
        if user_input is not None:
            self._task_id = user_input["task_id"]
            return await self.async_step_edit_task_fields()
        schema = vol.Schema(
            {
                vol.Required("task_id"): _labelled_select(
                    _task_options(tasks, self._lang), multiple=False
                )
            }
        )
        return self.async_show_form(step_id="edit_task", data_schema=schema)

    async def async_step_edit_task_fields(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        assert self._task_id is not None
        task: Task = self.coordinator.get_task(self._task_id)
        errors: dict[str, str] = {}
        if user_input is not None:
            schedule, errors = self._parse_task_input(user_input)
            if not errors:
                last = user_input.get("last_completed")
                last_date = date.fromisoformat(last) if last else None
                next_due = date.fromisoformat(user_input["next_due"])
                today = dt_util.now().date()
                if last_date is not None and last_date > today:
                    errors["last_completed"] = "completed_on_in_future"
                else:
                    dsd = user_input.get("due_soon_days")
                    self.coordinator.async_update_task(
                        task.id,
                        title=user_input["title"],
                        description=user_input.get("description", ""),
                        category=user_input["category"],
                        schedule=schedule,
                        due_soon_days=int(dsd) if dsd is not None else None,
                        last_completed=last_date if last_date != task.last_completed else None,
                        next_due=next_due if next_due != task.next_due else None,
                    )
                    return self._done()
        schema = self._task_schema(task)
        if user_input is not None:
            schema = self.add_suggested_values_to_schema(schema, user_input)
        return self.async_show_form(
            step_id="edit_task_fields",
            data_schema=schema,
            errors=errors,
            description_placeholders={"title": task.title},
        )

    # --- remove / restore ----------------------------------------------------------

    async def async_step_remove_task(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        tasks = self.coordinator.active_tasks
        if not tasks:
            return self.async_abort(reason="no_tasks")
        if user_input is not None:
            self.coordinator.async_archive(user_input.get("task_ids") or [])
            return self._done()
        schema = vol.Schema(
            {
                vol.Optional("task_ids", default=[]): _labelled_select(
                    _task_options(tasks, self._lang)
                )
            }
        )
        return self.async_show_form(step_id="remove_task", data_schema=schema)

    async def async_step_restore_task(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        tasks = self.coordinator.archived_tasks
        if not tasks:
            return self.async_abort(reason="no_archived")
        if user_input is not None:
            self.coordinator.async_restore(user_input.get("task_ids") or [])
            return self._done()
        schema = vol.Schema(
            {
                vol.Optional("task_ids", default=[]): _labelled_select(
                    _task_options(tasks, self._lang)
                )
            }
        )
        return self.async_show_form(step_id="restore_task", data_schema=schema)

    # --- edit property details -------------------------------------------------------

    async def async_step_profile(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if not self._defaults:
            self._defaults = self.coordinator.profile.to_dict()
        errors: dict[str, str] = {}
        if user_input is not None:
            errors = self._handle_basic(user_input)
            if not errors:
                return await self.async_step_building()
        return self.async_show_form(
            step_id="profile", data_schema=self._basic_schema(), errors=errors
        )

    async def _async_profile_done(self) -> ConfigFlowResult:
        coordinator = self.coordinator
        diff = plan_diff(
            coordinator.catalog,
            self._profile(),
            coordinator.tasks.values(),
            dt_util.now().date(),
        )
        self._diff_add = list(diff.additions)
        self._diff_remove = list(diff.removals)
        return await self.async_step_profile_review()

    async def async_step_profile_review(
        self, user_input: dict[str, Any] | None = None
    ) -> ConfigFlowResult:
        if user_input is not None:
            self.coordinator.async_update_profile(
                self._profile(),
                add_keys=user_input.get("add") or [],
                remove_task_ids=user_input.get("remove") or [],
            )
            return self._done()
        schema: dict[Any, Any] = {}
        if self._diff_add:
            schema[vol.Optional("add", default=[s.key for s in self._diff_add])] = _labelled_select(
                _suggestion_options(self._diff_add, self._lang)
            )
        if self._diff_remove:
            schema[vol.Optional("remove", default=[t.id for t in self._diff_remove])] = (
                _labelled_select(_task_options(self._diff_remove, self._lang))
            )
        return self.async_show_form(
            step_id="profile_review",
            data_schema=vol.Schema(schema),
            description_placeholders={
                "add_count": str(len(self._diff_add)),
                "remove_count": str(len(self._diff_remove)),
            },
        )
