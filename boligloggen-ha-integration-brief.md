# Boligloggen – Home Assistant integration (MVP/demo) – agent brief

*Companion to the Boligloggen project docs: `huslogg-applikasjonsplan.md` (product plan), `huslogg-onboarding.md` (onboarding question set). This brief is self-contained; read the onboarding doc for the full question/answer tables if available.*

*The integration is **standalone**: it runs entirely inside Home Assistant and does not connect to, sync with or depend on any Boligloggen backend or Web API. Ignore the `huslogg-webapi-*` docs for this work.*

---

## 0. TL;DR for the agent

Build a **custom Home Assistant integration** (`custom_components/boligloggen`, distributable via HACS) that:

1. Runs an **onboarding config flow** for one property (house, apartment, cabin) and **generates a maintenance plan** from a bundled task catalog with inclusion rules.
2. Stores tasks and a completion log **inside the integration** (not in HA's to-do platform).
3. Exposes each task as **entities** (a sensor + a "done" button) under one **service device per property**, so users can build dashboards and later a custom årshjul (year-wheel) card.
4. Records **which HA user** completed each task, from the service-call context.
5. Lets the **admin** (HA admin user) add, edit and remove tasks so the plan fits their house.

It is **fully standalone**: no external services, no cloud, no network calls. All data stays in the HA instance.

Work in the phases in §12. **Phase 1 (pure Python planner + catalog + tests) comes first and has no HA dependency.**

> HA's APIs change monthly. Before relying on any HA API named here (config/options flow, `Store`, entity platforms, websocket API, `DeviceEntryType.SERVICE`, context on entity service calls, logbook descriptors), check it against the current HA developer docs and core source. If something has moved, adapt the approach and keep the behaviour.

---

## 1. Product context (short)

Boligloggen is an app for shared household maintenance of a home or holiday property. Its core is recurring tasks, split by type and frequency and shown on a year-wheel, which everyone in the household can see and complete. What sets it apart: a **tailored plan** generated from a few onboarding answers, plus **shared completion** with a log of who did what.

The HA integration is a **demo/MVP** used to:
- validate the onboarding question set and the task catalog (the main open question in the product: *how few questions can we ask and still seed a plan the user finds accurate?*)
- validate the scheduling model
- be useful on its own to households that run Home Assistant

Domain language is Norwegian. Catalog task titles/descriptions are written in **Norwegian Bokmål (nb)**, with English (en) as secondary. Code, identifiers and comments are in English.

---

## 2. Scope

### In scope
- Config flow onboarding (blocks A–D) + review step
- Plan generation from `catalog.json` with inclusion rules
- Per-task entities (sensor + button), aggregate sensors, optional calendar entity
- Two scheduling types: **fixed** (anchored to calendar dates) and **interval** (rolling from last completion)
- Per-task `due_soon_days`
- Completion log with HA user, date, occurrence and optional note
- Admin-only plan editing (options flow + services)
- Events for automations, logbook entries, a notification blueprint
- Websocket commands that expose year-plan and log data for a future custom card
- Translations: `nb` and `en`

### Out of scope (do not build)
- Any connection to a Boligloggen backend/Web API, cloud sync or accounts outside HA
- HA's `todo` platform as the task store or UI
- Invitations, ownership transfer, "log sanitising" (everything lives inside one HA instance)
- Photos in the log (text notes only)
- Push notification delivery and per-user notification settings (users rely on HA automations and the blueprint)
- Climate adjustment (met.no), matrikkel lookup, Boligmappa
- The custom Lovelace årshjul card (a later, separate HACS frontend repo; this integration must only **expose the data** it needs)

---

## 3. Concept mapping

| Boligloggen concept | HA implementation |
|---|---|
| Property | One **config entry** = one **device** with `entry_type: DeviceEntryType.SERVICE`. `manifest.json` `integration_type: "service"` |
| Multiple properties | Multiple config entries (run the flow again) |
| Owner (eier) | HA **admin** user |
| Member (medlem) | Any HA user |
| Task (`MaintenanceTask`) | Record in the integration's `Store` + `sensor` + `button` entity |
| Task catalog (`TaskTemplate`) | Bundled `catalog.json` |
| Log entry (`LogEntry`) | Record in `Store`, plus a `boligloggen_task_completed` event and a logbook entry |
| "Who did it" | `context.user_id` of the service call → `hass.auth.async_get_user()` |
| Notifications | Events + aggregate sensors + a shipped blueprint |
| Year-wheel data | Websocket command `boligloggen/year_plan` |

---

## 4. Repository layout

```
boligloggen-ha/
├─ custom_components/boligloggen/
│  ├─ manifest.json        # domain boligloggen, config_flow true, integration_type "service", iot_class "calculated"
│  ├─ __init__.py          # async_setup_entry/unload, device, coordinator, services, websocket, daily scan
│  ├─ const.py
│  ├─ config_flow.py       # onboarding ConfigFlow + OptionsFlow (menu)
│  ├─ catalog.json         # task templates + inclusion rules
│  ├─ planner/             # PURE PYTHON – no homeassistant imports
│  │  ├─ __init__.py
│  │  ├─ models.py         # dataclasses: PropertyProfile, Schedule, TaskTemplate, Task, LogEntry, Occurrence
│  │  ├─ catalog.py        # load + validate catalog.json
│  │  ├─ rules.py          # inclusion rule matching
│  │  ├─ seeding.py        # generate plan from profile + catalog
│  │  └─ schedule.py       # next_due, status, completion, year projection
│  ├─ store.py             # helpers.storage.Store wrapper, schema versioning/migration
│  ├─ coordinator.py       # in-memory state, mutations, persistence, listener notification
│  ├─ entity.py            # base entity (device_info, unique_id helpers)
│  ├─ sensor.py
│  ├─ button.py
│  ├─ calendar.py          # optional (phase 4)
│  ├─ services.py + services.yaml
│  ├─ websocket.py
│  ├─ logbook.py           # async_describe_events for boligloggen_task_completed
│  ├─ strings.json
│  └─ translations/nb.json, en.json
├─ blueprints/automation/boligloggen/notify_due.yaml
├─ tests/
│  ├─ planner/             # plain pytest, no HA
│  └─ integration/         # pytest-homeassistant-custom-component
├─ hacs.json
└─ README.md
```

**Hard rule:** `planner/` must not import `homeassistant`. Keeping the scheduling and rule logic free of HA makes it fast to test, easy to reason about, and keeps HA plumbing out of the business rules.

---

## 5. Property profile (onboarding answers)

Stored as `PropertyProfile`. Enum values are English identifiers; the UI labels are Norwegian, via translations.

```jsonc
{
  "name": "Enebolig Trondheim",          // device name
  "address": "Eksempelveien 1, 7000 Trondheim",  // free text; default suggestion from HA home location
  "type": "house",                        // house | townhouse | apartment | cabin
  "build_year": 1985,                     // int, or null if age_band is used
  "age_band": null,                       // "lt10" | "10to30" | "30to50" | "gt50" | null
  "attributes": {
    "heating": ["wood_stove", "heat_pump"],   // multi: wood_stove | heat_pump | hydronic | electric | district
    "ventilation": "natural",                 // balanced | exhaust | natural | unknown
    "cladding": "wood",                       // wood | render | brick | mixed   (null for apartment)
    "bathroom_count": 2,                      // 1 | 2 | 3 (3 = 3+)
    "garden": true,
    "driveway": "pavers",                     // none | asphalt | pavers | gravel | concrete
    "deck": "wood",                           // none | wood | composite_or_stone
    "garage": "garage_with_door",             // none | garage_with_door | carport
    "water": "public",                        // public | own_well
    "cabin_winter_use": null,                 // closed | year_round  (cabin only)
    "cabin_water": null                       // year_round | summer | none (cabin only)
  }
}
```

**Derived values:**
- `age_years` = current year − `build_year`; if only `age_band` is given, use the band's lower bound (`lt10` → 0, `10to30` → 10, `30to50` → 30, `gt50` → 50).
- `ventilation: unknown` → default by age: `age_years < 15` → `balanced`, otherwise `exhaust` (simple, documented heuristic).

---

## 6. Onboarding config flow

One config flow per property. Steps are conditional on `type`. Use HA selectors (select with chips/dropdown, multi-select, number). Target: under 2 minutes for a typical house, with about 6 questions for an apartment.

| Step | Shown for | Fields |
|---|---|---|
| `user` (block A) | all | `name`, `address`, `type`, `build_year` **or** `age_band` |
| `building` (block B) | all; for `apartment` only `heating`, `ventilation`, `bathroom_count` | `heating` (multi), `ventilation`, `cladding`, `bathroom_count` |
| `outdoor` (block C) | house, townhouse, cabin | `garden`, `driveway`, `deck`, `garage`, `water` – each answered individually, with "none/no" as a quick answer |
| `cabin` (block D) | cabin | `cabin_winter_use`, `cabin_water` |
| `review` | all | Multi-select of the generated tasks (all pre-selected), grouped/labelled by category. The admin unticks tasks that don't apply. |

On `review` submit: create the entry with `data = {profile, selected_template_ids, deselected_template_ids}`. On first `async_setup_entry`, if no Store exists for the entry, seed the tasks from this data. **After seeding, the Store is the single source of truth**, including the profile. Later edits go through the options flow and are written to the Store.

Record the deselected template IDs in the Store as `onboarding_feedback` (see §11, measuring catalog accuracy).

---

## 7. Catalog format (`catalog.json`)

```jsonc
{
  "version": 1,
  "templates": [
    {
      "id": "smoke_alarm_check",
      "category": "safety",                 // safety | indoor | wet_room | heating | ventilation | exterior | outdoor | cabin | seasonal
      "title": { "nb": "Test røykvarslere og bytt batteri", "en": "Test smoke alarms and replace battery" },
      "description": { "nb": "…lavterskel forklaring…", "en": "…" },
      "schedule": { "type": "fixed", "dates": [{ "month": 12, "day": 1 }] },
      "due_soon_days": 14,                  // optional override
      "per_bathroom": false,                // optional; see below
      "include": {}                         // empty = always included
    },
    {
      "id": "chimney_sweep_check",
      "category": "heating",
      "title": { "nb": "Sjekk ildsted og pipe", "en": "Inspect stove and chimney" },
      "schedule": { "type": "interval", "every": 1, "unit": "years" },
      "include": { "heating_any": ["wood_stove"] }
    },
    {
      "id": "paint_wood_cladding",
      "category": "exterior",
      "title": { "nb": "Mal/beis kledning", "en": "Paint/stain wooden cladding" },
      "schedule": { "type": "interval", "every": 7, "unit": "years" },
      "due_soon_days": 90,
      "include": { "cladding_any": ["wood", "mixed"], "types_exclude": ["apartment"] }
    }
  ]
}
```

### Schedule object
- `{"type": "interval", "every": N, "unit": "months" | "years"}` – rolling. Monthly = `every: 1, months`; quarterly = 3 months; semi-annual = 6 months; yearly = 1 year; "every N years" = N years.
- `{"type": "fixed", "dates": [{"month": M, "day": D}, ...]}` – anchored to calendar dates, repeating yearly. One or more dates (for example `[{4,1},{10,1}]`). `day` defaults to 1, which lets you express "some time in October".

### Inclusion rule (`include`)
All present keys must match (**AND**). Within a list, any value matches (**ANY**). An empty object means always included.

| Key | Matches when |
|---|---|
| `types_any` | `type` ∈ list |
| `types_exclude` | `type` ∉ list |
| `heating_any` | intersection of `heating` and list is non-empty |
| `ventilation_any` | effective `ventilation` ∈ list |
| `cladding_any` | `cladding` ∈ list |
| `driveway_any` | `driveway` ∈ list |
| `deck_any` | `deck` ∈ list |
| `garage_any` | `garage` ∈ list |
| `requires_garden` | `garden == value` |
| `requires_own_well` | `(water == own_well) == value` |
| `cabin_winter_use_any` | `cabin_winter_use` ∈ list |
| `cabin_water_any` | `cabin_water` ∈ list |
| `min_age_years` | `age_years >= value` |
| `max_age_years` | `age_years <= value` |

`per_bathroom: true` → seed one task per bathroom (`"Rens sluk – bad 1"`, `"… bad 2"`).

Validate the catalog when it loads (unknown keys, bad enums, invalid dates such as 31 Feb) and fail the tests if it's invalid. A JSON Schema (`catalog.schema.json`) is optional but helps when editing the catalog by hand.

### Initial catalog content
Write about 30–45 templates in Norwegian, covering at least the mappings in the onboarding doc:
- **Always:** smoke alarms (fixed 1 Dec), fire extinguisher check, clean drains per bathroom (interval 3 months), check sealant/joints in wet rooms (yearly), clean kitchen extractor filter, check water leak/stoptap.
- **Heating:** wood stove → chimney/stove inspection; heat pump → clean filter (interval 3 months), rinse outdoor unit (fixed, spring), check condensate drain; hydronic → bleed radiators (fixed, autumn), check distribution cabinet/pressure.
- **Ventilation:** balanced → change filter (interval 6 months); exhaust → clean fan/valves (yearly); natural → check vents (yearly).
- **Exterior:** wood cladding → paint/stain (interval 7 years, long `due_soon_days`) + yearly inspection; render → check render/joints; gutters + downpipes (fixed, October; not for apartment); roof inspection (yearly; not for apartment); drainage check (`min_age_years: 30`, not for apartment); windows/doors (seals, hinges).
- **Age:** electrical installation check (`min_age_years: 20`, interval 5 years); water heater assessment (`min_age_years: 15`).
- **Outdoor:** garden → leaf raking (fixed, October); asphalt → seal cracks (fixed, autumn); pavers → weeds in joints + refill joint sand (fixed, May); gravel → top up/level (fixed, May); concrete → check cracks; wood deck → clean + oil (fixed, June); composite/stone deck → clean (fixed, May); garage door → lubricate + photocell check (yearly).
- **Water:** own well → water sample (yearly) + well/pump check (yearly).
- **Cabin:** closed in winter → frost-proofing / shut off and drain water (fixed, October), open/fill water (fixed, May), season close/open checklists.

Choose sensible Norwegian seasonal months. The catalog is meant to be edited, so correctness of structure matters more than perfect content.

---

## 8. Scheduling model (the core logic)

Each task has a **schedule type** that comes from its template (the admin can change it):

- **fixed (anchored):** for tasks tied to the calendar or a season. Occurrences sit on the listed dates every year, whenever the task was actually done.
- **interval (rolling):** for tasks driven by wear or elapsed time. The next due date is counted from the actual completion date.

Rule of thumb for catalog authors: *is the date tied to the calendar/season (fixed) or to time since last done (interval)?*

### Task fields related to scheduling
- `schedule` (see §7)
- `next_due: date`
- `due_soon_days: int`
- `last_completed: date | null`

### Defaults for `due_soon_days` (when the template doesn't override)
| Effective period | Default |
|---|---|
| ≤ 1 month | 3 |
| ≤ 3 months | 7 |
| ≤ 6 months | 14 |
| ≤ 12 months | 21 |
| > 12 months | 60 |

For `fixed`, the effective period is the shortest gap between consecutive dates in the year (wrapping around). One date per year means 12 months.

### Status (computed for a given `today`)
- `overdue` if `today > next_due`
- `due_soon` if `next_due - due_soon_days <= today <= next_due`
- otherwise `ok`

### Month arithmetic
`add_months(date, n)` clamps to the end of the month (31 Jan + 1 month = 28/29 Feb). Interval tasks always compute from the actual completion date, so clamping doesn't build up drift.

### Initial `next_due` at seeding
- **fixed:** the first listed date on or after the setup date.
- **interval:** `setup_date + interval`. (The last completion date is unknown. The admin can set "last done" per task in the options flow, which recomputes `next_due`.)

### Completing a task (`completed_on`, default today)
- **interval:** `last_completed = completed_on`; `next_due = completed_on + interval`. Log `occurrence_date = previous next_due`.
- **fixed:** close the current occurrence and any missed ones: `next_due = first fixed date strictly after max(completed_on, previous next_due)`. Log `occurrence_date = previous next_due`.
  - Early (due 1 Dec, done 25 Nov) → next is the following listed date after 1 Dec.
  - Overdue (due 1 Oct, done 22 Nov) → next is the first listed date after 22 Nov. Missed occurrences are closed with one press.

### Guard against accidental early completion (fixed tasks only)
- If a **fixed** task's status is `ok` (not yet in its due window), a **button press** raises `ServiceValidationError` with a translated message ("Ikke aktuell før {date}").
- `boligloggen.complete_task` with `force: true` lets an admin or member complete it anyway.
- Interval tasks can always be completed. An extra press only shifts the next date to count from today.

### Undo
`boligloggen.undo_completion` removes the task's latest log entry and restores `next_due`/`last_completed` from a snapshot stored on the log entry (`prev_next_due`, `prev_last_completed`). Allowed for admins and for the user who made the completion.

### Year projection (for the årshjul)
`project_year(task, year, log) -> list[Occurrence]` returns `{date, status}` where status ∈ `done | missed | upcoming | due_soon | overdue`:
- **fixed:** each listed date in the year. A date is `done` if a log entry has that `occurrence_date`; otherwise status is relative to today.
- **interval:** past occurrences come from log entries in the year (`done`). Future occurrences are projected forward from `next_due` by the interval until the end of the year (`upcoming`, with `due_soon`/`overdue` for the current one).

### Required planner tests (minimum)
- Month-end clamping, leap years (29 Feb fixed date → treat as 28 Feb in non-leap years, documented)
- Fixed date with multiple dates per year, wrap-around at year end
- Fixed: early, on-time, overdue and multi-missed completions
- Interval: completion resets from the completion date; every-N-years
- Status boundaries (exactly at `next_due - due_soon_days`, exactly at `next_due`, one day after)
- `due_soon_days` defaults per period
- Undo restores the previous state exactly
- Inclusion rules: each key, AND/ANY semantics, apartment exclusions, cabin-only, `per_bathroom`, `ventilation: unknown` default, `age_band`
- Seeding the example profiles (house 1985 with wood stove + heat pump; new apartment; winter-closed cabin with own well) produces the expected template sets. Add these as snapshot fixtures.

---

## 9. Storage

`homeassistant.helpers.storage.Store`, key `boligloggen.<entry_id>`, with a version and a migration hook.

```jsonc
{
  "schema_version": 1,
  "catalog_version": 1,
  "profile": { /* §5 */ },
  "tasks": [
    {
      "id": "uuid",                     // stable; used in unique_id
      "template_id": "chimney_sweep_check",   // null for custom tasks
      "title": "Sjekk ildsted og pipe",
      "description": "…",
      "category": "heating",
      "schedule": { "type": "interval", "every": 1, "unit": "years" },
      "due_soon_days": 21,
      "next_due": "2027-11-22",
      "last_completed": null,
      "status": "active",               // active | archived
      "last_notified_state": "ok",      // for once-per-transition events across restarts
      "created_at": "…", "updated_at": "…"
    }
  ],
  "log": [
    {
      "id": "uuid",
      "task_id": "uuid",
      "completed_on": "2026-11-22",
      "occurrence_date": "2026-12-01",
      "user_id": "ha-user-id-or-null",
      "user_name": "Ola",               // snapshot of the name at that time; "Ukjent"/"System" if null
      "note": null,
      "forced": false,
      "prev_next_due": "2026-12-01",
      "prev_last_completed": null,
      "created_at": "…"
    }
  ],
  "onboarding_feedback": {
    "deselected_at_review": ["…template ids…"],
    "added_later": [], "removed_later": []
  }
}
```

**Removing a task archives it** (`status: archived`). Its entities are removed, but the record and log stay. When the profile is edited, the regenerated suggestions must not bring back archived templates; the admin can restore them explicitly.

---

## 10. Entities

All entities belong to the property's device: `DeviceInfo(identifiers={(DOMAIN, entry_id)}, name=profile.name, entry_type=DeviceEntryType.SERVICE, manufacturer="Boligloggen")`. Use `has_entity_name = True` and `unique_id = f"{entry_id}_{task_id}_{kind}"`.

### Per active task
- **`sensor`** – state: `next_due` (`device_class: date`). Attributes: `task_id`, `status`, `category`, `schedule_type`, `schedule` (human-readable + raw), `due_soon_days`, `days_until_due`, `last_completed`, `last_completed_by`, `description`, `template_id`. Set an icon per category.
- **`button`** – "Utført" / "Done". `async_press` completes the task with `completed_on = today`, the user from `self._context.user_id`, and no note. Applies the fixed-task guard (§8).

Create and remove entities dynamically when tasks are added, archived or restored. Remove orphaned entries from the entity registry.

### Aggregate (per property)
- `sensor.<property>_next_task` – state: title of the next due task; attributes: `task_id`, `next_due`, `status`
- `sensor.<property>_overdue` – state: count; attribute: `tasks` (a small list of `{task_id, title, next_due}`)
- `sensor.<property>_due_soon` – same shape
- `sensor.<property>_last_completed` – state: title; attributes: `user_name`, `completed_on`, `note`
- *(phase 4, optional)* `calendar.<property>` – events for occurrences from the year projection (all-day). Read-only.

Keep attributes small. Put list-type attributes in `_unrecorded_attributes` so the recorder doesn't store them.

### Who did it
Entity service calls set the call context on the entity before the method runs, so read `self._context.user_id` (button) or `call.context.user_id` (services). Look it up with `await hass.auth.async_get_user(user_id)` and store `user_id` and `user.name`. If it's missing (automation, script, some voice paths), store `user_id: null` and `user_name: "System"`. **Verify against current HA core** that the context is set on entity service calls; if not, register the button press through an entity service that receives `ServiceCall` directly.

---

## 11. Plan editing, services, events, websocket

### Options flow (admin-only by HA default) – menu
1. **Legg til fra katalog / Add from catalog** – multi-select of templates that are matched-but-not-active, plus a toggle to show all templates (including non-matching ones)
2. **Legg til egendefinert / Add custom task** – title, description, category, schedule type + fields, `due_soon_days`
3. **Endre gjøremål / Edit task** – pick a task, then edit title, description, schedule, `due_soon_days`, "last done" (recomputes `next_due`) or `next_due` directly
4. **Fjern gjøremål / Remove task** – archive (multi-select)
5. **Gjenopprett / Restore archived task**
6. **Endre boligdetaljer / Edit property details** – re-run the onboarding steps with current values, then a review showing **only the diff** (suggested additions, and suggested removals of catalog tasks that no longer match). Custom tasks are never auto-removed.

Record additions and removals in `onboarding_feedback` (template IDs only).

### Services (`services.yaml`)
| Service | Fields | Who |
|---|---|---|
| `boligloggen.complete_task` | `entity_id` (task sensor or button) **or** `task_id` + `config_entry_id`; `note?`; `completed_on?`; `force?` | any user |
| `boligloggen.undo_completion` | task target | admin, or the user who completed it |
| `boligloggen.add_task` | `config_entry_id`, `template_id` **or** custom fields | admin |
| `boligloggen.update_task` | task target + fields | admin |
| `boligloggen.remove_task` | task target | admin (archives) |
| `boligloggen.restore_task` | `config_entry_id`, `task_id` | admin |

Admin check: `user = await hass.auth.async_get_user(call.context.user_id)`. If `user is None` (automation/system), allow it; system calls are trusted. If `not user.is_admin`, raise `homeassistant.exceptions.Unauthorized`. Raise `ServiceValidationError` with translation keys for domain errors.

### Events (fire on the bus)
- `boligloggen_task_completed` – `{config_entry_id, property_name, task_id, title, user_id, user_name, completed_on, occurrence_date, note, forced}`
- `boligloggen_task_due_soon` – fired **once** when a task changes `ok → due_soon`
- `boligloggen_task_overdue` – fired **once** when a task changes to `overdue`

Transitions are detected by a **daily scan** (`async_track_time_change`, for example 00:05 local) **and** at startup, compared against the persisted `last_notified_state`, so restarts don't re-fire. Completions and edits also re-evaluate the task and update `last_notified_state` without firing due events.

### Logbook
`logbook.py` describes `boligloggen_task_completed` as "Ola fullførte «Rens sluk – bad 1»" (translated), linked to the task sensor entity.

### Websocket commands (for the future custom card)
- `boligloggen/properties` → list of `{config_entry_id, name, type}`
- `boligloggen/tasks` `{config_entry_id}` → full task list, including entity IDs for the sensor and button
- `boligloggen/year_plan` `{config_entry_id, year}` → `[{task_id, title, category, schedule_type, occurrences: [{date, status}]}]`
- `boligloggen/log` `{config_entry_id, limit?, before?}` → paginated log entries

All commands require an authenticated connection. Read-only.

### Blueprint
`blueprints/automation/boligloggen/notify_due.yaml`: inputs are a property (config entry or device), notify target(s), and which events to send (due soon, overdue, completed by someone else). It triggers on the events above and sends a message through `notify.*`.

---

## 12. Phases and acceptance criteria

**Phase 1 – Planner core (no HA)**
- `planner/` models, catalog loader + validation, rules, seeding, scheduling, projection
- Initial `catalog.json` (§7)
- ✅ All §8 tests pass; the three example profiles produce reviewed snapshot plans; the catalog validates

**Phase 2 – Minimal integration**
- Manifest, config flow (A, B, C, D, review), Store, coordinator, device, per-task sensor + button, completion with HA user, `complete_task` service
- ✅ Install in a dev HA instance, onboard a house, see entities under one service device, press "Utført" as two different users, and see the correct `last_completed_by` and log entries after a restart

**Phase 3 – Plan editing**
- Options flow menu (all six actions), archive/restore, admin services, fixed-task early guard, undo, onboarding_feedback
- ✅ A non-admin user gets `Unauthorized` on admin services; editing the profile shows a correct diff; archived tasks don't reappear

**Phase 4 – Visibility and automation**
- Aggregate sensors, daily scan + transition events, logbook, blueprint, optional calendar entity
- ✅ Events fire once per transition across restarts; the blueprint sends a notification in a test

**Phase 5 – Card-ready data and distribution**
- Websocket commands, `hacs.json`, README (install, dashboard examples using tile cards, blueprint), full `nb` + `en` translations
- ✅ `boligloggen/year_plan` returns the correct occurrences for both schedule types, and the repo installs via HACS as a custom repository

**Later (separate repo):** custom Lovelace årshjul/task card using the websocket API and the services.

---

## 13. Testing and quality

- `tests/planner/`: plain pytest, fast, no HA. Inject `today` explicitly (no hidden `date.today()` in the planner).
- `tests/integration/`: `pytest-homeassistant-custom-component` – config flow paths per property type, options flow actions, service permissions (admin vs non-admin vs system context), entity creation/removal, Store persistence/migration, event-once semantics, websocket responses.
- Lint/type: `ruff`, `mypy` (strict on `planner/`).
- Follow the HA integration quality scale where it's practical (config flow, unique IDs, translations, diagnostics optional).

---

## 14. Open questions (decide with the product owner; don't block on them – use the defaults given)

1. **Initial `next_due` for interval tasks** – default `setup + interval`. Should the review step ask "last done?" for a few high-value tasks instead?
2. **Catalog updates** – when a new integration version ships catalog changes, should existing installs be offered new matching templates (via the "Edit property details" diff)? Default: yes, as suggestions only, never automatic.
3. **Undo window** – no time limit by default. Should undo be limited to, say, 7 days?
4. **Measuring plan accuracy** – `onboarding_feedback` is stored locally. Should it be exportable (diagnostics download) so test households can share it? Default: include it in a diagnostics dump.
5. **Fixed-date flexibility** – are month-level dates (`day: 1`) enough for seasonal tasks, or do we need explicit date windows (for example 15 Sep – 31 Oct)?
