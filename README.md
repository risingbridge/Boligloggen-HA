# Boligloggen for Home Assistant

A tailored, shared maintenance plan for your home, apartment or cabin, inside Home Assistant.

Answer a few questions about the property and Boligloggen suggests a plan from a bundled
catalog of 48 Norwegian maintenance tasks: smoke alarms, drains, heat pump filters,
gutters, decking oil, cabin winterising and more. Everyone in the household can see the plan
and mark tasks as done, and the log records who did what.

**Fully standalone.** There is no cloud, no account and no network traffic. All data stays in
your Home Assistant instance.

> Build brief: [`boligloggen-ha-integration-brief.md`](boligloggen-ha-integration-brief.md).
> Background docs (Norwegian) and the original agent handoff are in [`docs/`](docs/).

## Installation

### HACS (custom repository)

1. HACS → ⋮ → *Custom repositories* → add `https://github.com/risingbridge/Boligloggen-HA`,
   category **Integration**.
2. Install **Boligloggen** and restart Home Assistant.
3. *Settings → Devices & services → Add integration → Boligloggen*.

### Manual

Copy `custom_components/boligloggen` into your `config/custom_components/` folder and restart.

Requires Home Assistant **2026.2** or newer (the version it is tested against).

## Onboarding

One config entry = one property. Run the flow again to add a cabin, for example.

| Step | Shown for | Questions |
|---|---|---|
| Basics | all | name, address, type, year built *or* age band |
| Building | all (apartments: heating, ventilation, bathrooms only) | heating, ventilation, cladding, bathrooms |
| Outdoor | house, townhouse, cabin | garden, driveway, deck, garage, water, each answered individually |
| Cabin | cabin | winter use, water |
| Review | all | every suggested task, pre-ticked; untick what doesn't apply |

What you untick is stored as *onboarding feedback*, which measures how accurate the catalog is.
It is included in the diagnostics download.

## Editing the plan (admins)

### Boligloggen panel

Admins get a **Boligloggen** entry in the sidebar. It is hidden from other users. The panel
has four tabs:

- **Plan**: every task grouped by category, with its status, schedule, next due date and who
  last did it. From here you can **edit** a task (title, description, category, schedule,
  warning days, *last done*, next due date), **undo** its latest completion, or **remove** it.
  A filter box narrows the list.
- **Add tasks**: tick catalog tasks that match the property (or *show the whole catalog*) and
  add them in one go, or create a **custom task** with its own schedule.
- **Removed**: restore tasks that were removed earlier.
- **History**: every completion, newest first, with who did it and any note.

*Edit property details* opens the integration page, where *Configure → Edit property details*
re-runs the property questions. The panel works on phones and in the companion app, and
follows the user's language (nb/en) and theme. It uses the same services as automations, so
the same validation and admin checks apply.

### Integration options

*Settings → Devices & services → Boligloggen → Configure* opens a menu with the same actions:

- **Legg til fra katalog / Add from catalog**: matching templates not in the plan yet. Tick
  *show all* to list the whole catalog.
- **Legg til egendefinert / Add custom task**: your own task with a fixed or interval schedule.
- **Endre gjøremål / Edit task**: title, description, schedule, warning days, *last done*
  (recomputes the next due date) or the next due date directly.
- **Fjern gjøremål / Remove task**: archives the task. Its history is kept.
- **Gjenopprett / Restore archived task**
- **Endre boligdetaljer / Edit property details**: re-run the questions. You then see only the
  diff: suggested additions, and catalog tasks that no longer fit. Archived tasks never come
  back on their own, and custom tasks are never removed.

## Scheduling

- **Fixed** tasks are tied to the calendar or season, e.g. smoke alarms on 1 December, or
  windows on 15 April and 15 September. They recur on the same dates whenever you do them.
  Completing late closes every missed occurrence in one go. Pressing *Done* before the
  due-soon window opens is refused ("Ikke aktuell før …"); use `complete_task` with
  `force: true` to complete one anyway.
- **Interval** tasks are driven by wear or elapsed time, e.g. every 3 months or every
  7 years. The next due date counts from when the task was actually done.

A task's status is `ok`, `due_soon` (within `due_soon_days` of the due date) or `overdue`.
A fixed date of 29 February falls on 28 February in non-leap years.

## Entities

All entities belong to one *service* device per property. For full attribute details and
dashboard recipes, see [`docs/entities-and-dashboards.md`](docs/entities-and-dashboards.md). To build
your own year-wheel card, see [`docs/year-wheel-card.md`](docs/year-wheel-card.md).

| Entity | State | Notes |
|---|---|---|
| `sensor.<property>_<task>` | next due date | attributes: `status`, `days_until_due`, `schedule`, `last_completed`, `last_completed_by`, … |
| `button.<property>_<task>_utfort` | — | press = done today, as you |
| `sensor.<property>_next_task` | title | `task_id`, `next_due`, `status` |
| `sensor.<property>_overdue` / `_due_soon` | count | `tasks` list (not recorded) |
| `sensor.<property>_last_completed` | title | `user_name`, `completed_on`, `note` |
| `calendar.<property>_maintenance_plan` | — | all-day events for every occurrence |

### Dashboard example (tile cards)

```yaml
type: vertical-stack
cards:
  - type: glance
    entities:
      - sensor.enebolig_overdue
      - sensor.enebolig_due_soon
      - sensor.enebolig_next_task
  - type: tile
    entity: sensor.enebolig_rens_filter_i_varmepumpe
    state_content: [state, status]
    tap_action:
      action: perform-action
      perform_action: boligloggen.complete_task
      target: {}
      data:
        entity_id: sensor.enebolig_rens_filter_i_varmepumpe
  - type: tile
    entity: button.enebolig_rens_sluk_bad_1_utfort
  - type: calendar
    entities: [calendar.enebolig_maintenance_plan]
    initial_view: listWeek
```

Overdue tasks only, using the `status` attribute:

```yaml
type: entity-filter
entities: []   # list your task sensors here
state_filter:
  - attribute: status
    value: overdue
```

## Services

| Service | Who | Fields |
|---|---|---|
| `boligloggen.complete_task` | anyone | `entity_id` (task sensor/button) **or** `config_entry_id` + `task_id`; `note`, `completed_on`, `force` |
| `boligloggen.undo_completion` | admin, or whoever completed it | task target |
| `boligloggen.add_task` | admin | `config_entry_id` + `template_id` **or** `title`, `category`, `schedule_type`, `every`/`unit` or `dates` (`"04-01, 10-01"`), `due_soon_days` |
| `boligloggen.update_task` | admin | task target + any task field, `last_completed`, `next_due` |
| `boligloggen.remove_task` | admin | task target (archives) |
| `boligloggen.restore_task` | admin | `config_entry_id`, `task_id` |

Calls with no user, such as automations and scripts, are trusted. Non-admin users get
`Unauthorized` on the admin services.

## Events and automations

| Event | When | Data |
|---|---|---|
| `boligloggen_task_completed` | a task is completed | `config_entry_id`, `property_name`, `task_id`, `title`, `user_id`, `user_name`, `completed_on`, `occurrence_date`, `note`, `forced` |
| `boligloggen_task_due_soon` | once, on `ok → due_soon` | `config_entry_id`, `property_name`, `task_id`, `title`, `next_due`, `days_until_due`, `entity_id` |
| `boligloggen_task_overdue` | once, on becoming overdue | same as above |

Due events come from a daily scan at 00:05 and a scan at startup. Both compare against the
state stored with each task, so a restart never fires an event twice.

### Blueprint

Import [`blueprints/automation/boligloggen/notify_due.yaml`](blueprints/automation/boligloggen/notify_due.yaml)
(*Settings → Automations → Blueprints → Import*, URL:
`https://github.com/risingbridge/Boligloggen-HA/blob/main/blueprints/automation/boligloggen/notify_due.yaml`). Choose a property, a notify action
(e.g. `notify.mobile_app_phone`) and which events to send: due soon, overdue, or completed by
someone else.

## Websocket API (for custom cards)

Read-only, and requires an authenticated connection:

- `boligloggen/properties` → `[{config_entry_id, name, type}]`
- `boligloggen/tasks` `{config_entry_id, include_archived?}` → tasks with `due_status`,
  `sensor_entity_id`, `button_entity_id`, …
- `boligloggen/year_plan` `{config_entry_id, year}` →
  `[{task_id, title, category, schedule_type, occurrences: [{date, status}]}]`, where status is
  `done | missed | upcoming | due_soon | overdue`
- `boligloggen/log` `{config_entry_id, limit?, before?, task_id?}` → `{entries, next_before}`,
  newest first. Pass `next_before` back as `before` to get the next page.
- `boligloggen/catalog` `{config_entry_id, show_all?}` (**admins only**) → catalog tasks not
  in the plan yet: `[{key, template_id, title, description, category, schedule,
  schedule_text, matches}]`. Pass `key` as `template_id` to `boligloggen.add_task`.

## Development

```bash
python -m venv .venv
.venv/bin/pip install pytest ruff mypy pytest-homeassistant-custom-component
.venv/bin/pytest                       # planner + integration tests
.venv/bin/ruff check . && .venv/bin/ruff format --check .
.venv/bin/mypy custom_components/boligloggen
.venv/bin/mypy --strict custom_components/boligloggen/planner
python script/gen_translations.py      # regenerate strings.json + translations/*.json
UPDATE_SNAPSHOTS=1 .venv/bin/pytest tests/planner   # after a reviewed catalog change
```

- `custom_components/boligloggen/planner/` is pure Python and **must not import
  `homeassistant`**. All scheduling and rule logic lives there and is tested without HA.
- `catalog.json` is validated on load; `catalog.schema.json` helps when editing it by hand.
- UI text lives in `script/gen_translations.py` as `(en, nb)` pairs; don't edit the generated
  JSON by hand.
