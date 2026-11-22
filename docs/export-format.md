# Export file format (editing and re-importing a plan)

The **Export / import** tab in the Boligloggen admin panel downloads a property's whole plan as
one JSON file. You can edit that file in any text editor and import it again, for example to:

- fix many titles, descriptions or categories at once
- add a batch of your own tasks
- adjust dates or warning days across the plan
- correct the history (a completion logged on the wrong day, a note with a typo)
- copy a plan from one property or Home Assistant to another

This document describes every field, what the app does with it, and the rules an import
checks. It applies to **`format_version` 1**, which is what Boligloggen 0.3 writes.

> **Export first, and keep the original file.** An import *replaces* the property's plan and
> can't be undone. If an edit goes wrong, import the untouched original to get back.

---

## The safe editing workflow

1. **Export.** Open *Boligloggen → Export / import → Download JSON*. You get a file such as
   `boligloggen-enebolig-2026-11-22.json`.
2. **Make a copy** and edit the copy. Use an editor that understands JSON, such as VS Code or
   the File editor / Studio Code Server add-on. It will point out a missing comma or quote at
   once.
3. **Keep the file valid JSON.** That means:
   - no comments
   - no trailing commas
   - double quotes everywhere
   - the file saved as UTF-8, so æ, ø and å work
4. **Import.** Choose the edited file and check the summary (property name, number of tasks,
   number of completions).
   - Tick **include history** if you edited the `log`, or if you're moving the plan to a new
     property.
   - Leave it unticked to keep the current history and ignore the file's `log`.
5. **Check the result** on the Plan tab. If the import is refused, nothing has changed. The
   message says what's wrong and where, for example
   `invalid_content (property.tasks[12].category 'garden')`.

---

## Top level

```json
{
  "format": "boligloggen-export",
  "format_version": 1,
  "exported_at": "2026-11-22T18:40:12.345678+00:00",
  "integration_version": "0.3.0",
  "property": { … }
}
```

| Field | Required | Meaning |
|---|---|---|
| `format` | yes | Must be exactly `"boligloggen-export"`. Anything else is refused as *not a Boligloggen export file*. |
| `format_version` | yes | `1`. Files from a newer Boligloggen are refused until you update the integration. |
| `exported_at` | no | When the file was made (UTC). Only shown in the import summary. |
| `integration_version` | no | The Boligloggen version that made the file. Informational. |
| `property` | yes | The property itself, described below. |

## `property`

```json
"property": {
  "schema_version": 1,
  "catalog_version": 1,
  "language": "nb",
  "profile": { … },
  "tasks": [ … ],
  "log": [ … ],
  "onboarding_feedback": { … }
}
```

| Field | Required | Meaning |
|---|---|---|
| `schema_version` | no (default 1) | Storage layout version. Leave it as it is. |
| `catalog_version` | no | Ignored on import. The installed catalog is always used. |
| `language` | no | `"nb"` or `"en"`. This is the language of generated text such as schedule descriptions ("Hvert kvartal" / "Every quarter") and logbook entries. Other values are ignored, and the property keeps its current language. Task titles are *not* translated: they stay as written. |
| `profile` | yes | The answers from onboarding. |
| `tasks` | yes | The plan: every task, active and removed. |
| `log` | no | The completion history. Only imported when *include history* is ticked. |
| `onboarding_feedback` | no | Statistics about how well the catalog fitted. Safe to leave alone. |

---

## `profile`

```json
"profile": {
  "name": "Enebolig",
  "address": "Eksempelveien 1",
  "type": "house",
  "build_year": 1985,
  "age_band": null,
  "attributes": {
    "heating": ["wood_stove", "heat_pump"],
    "ventilation": "natural",
    "cladding": "wood",
    "bathroom_count": 2,
    "garden": true,
    "driveway": "pavers",
    "deck": "wood",
    "garage": "garage_with_door",
    "water": "public",
    "cabin_winter_use": null,
    "cabin_water": null
  }
}
```

The profile describes the property. It decides which catalog tasks are **suggested** on
*Add tasks* and under *Edit property details*. It does **not** add or remove tasks by itself: an
import uses exactly the tasks in `tasks`.

- **`name`** is required and must not be empty. Importing a new name renames the property, its
  device and the integration entry. Existing entity IDs are kept.
- **`address`** is optional free text.

Every other field must use one of the values listed here. Anything else is refused, so a typo
can't silently stop suggestions from working.

| Field | Allowed values |
|---|---|
| `type` | `house` (house) · `townhouse` (townhouse / semi-detached) · `apartment` · `cabin` |
| `build_year` | a year (1000–2200) or `null`. If set, it wins over `age_band`. |
| `age_band` | `lt10` (under 10 years) · `10to30` · `30to50` · `gt50` (over 50) · `null` |
| `attributes.heating` | a list of any of: `wood_stove` (wood stove/fireplace with chimney) · `heat_pump` · `hydronic` (radiators/underfloor) · `electric` · `district` (district heating). Can be empty `[]`. |
| `attributes.ventilation` | `balanced` (with heat recovery) · `exhaust` (mechanical exhaust) · `natural` · `unknown` |
| `attributes.cladding` | `wood` · `render` (masonry/render) · `brick` · `mixed` · `null` |
| `attributes.bathroom_count` | `1` · `2` · `3` (3 means "3 or more") |
| `attributes.garden` | `true` or `false` |
| `attributes.driveway` | `none` · `asphalt` · `pavers` · `gravel` · `concrete` |
| `attributes.deck` | `none` · `wood` · `composite_or_stone` |
| `attributes.garage` | `none` · `garage_with_door` · `carport` |
| `attributes.water` | `public` · `own_well` (own well/borehole) |
| `attributes.cabin_winter_use` | `closed` (closed/unheated in winter) · `year_round` · `null` (not a cabin) |
| `attributes.cabin_water` | `year_round` · `summer` · `none` · `null` (not a cabin) |

Attributes you leave out get these defaults:
- `heating` → `[]`
- `ventilation` → `"unknown"`
- `bathroom_count` → `1`
- `garden` → `false`
- `driveway`, `deck` and `garage` → `"none"`
- `water` → `"public"`
- `cladding`, `cabin_winter_use` and `cabin_water` → `null`

---

## `tasks`

Each task is one object. Here is a fixed-date task followed by an interval task:

```json
"tasks": [
  {
    "id": "5c1f0e3a9b2d4f8e8a7b6c5d4e3f2a1b",
    "template_id": "smoke_alarm_check",
    "instance": null,
    "title": "Test røykvarslere og bytt batteri",
    "description": "Trykk på testknappen på alle røykvarslere …",
    "category": "safety",
    "schedule": { "type": "fixed", "dates": [{ "month": 12, "day": 1 }] },
    "due_soon_days": 21,
    "next_due": "2026-12-01",
    "last_completed": null,
    "status": "active",
    "last_notified_state": "due_soon",
    "created_at": "2026-11-22T11:00:00+00:00",
    "updated_at": "2026-11-22T11:00:00+00:00"
  },
  {
    "id": "a9e2…",
    "template_id": "clean_drains",
    "instance": 2,
    "title": "Rens sluk – bad 2",
    "description": "",
    "category": "wet_room",
    "schedule": { "type": "interval", "every": 3, "unit": "months" },
    "due_soon_days": 7,
    "next_due": "2027-02-22",
    "last_completed": "2026-11-22",
    "status": "active",
    "last_notified_state": "ok",
    "created_at": "2026-11-22T11:00:00+00:00",
    "updated_at": "2026-11-22T11:00:00+00:00"
  }
]
```

| Field | Required | Meaning and rules |
|---|---|---|
| `id` | yes | Unique within the file; any non-empty string. Entity IDs and the history are linked to it. **Don't change the `id` of an existing task**: it would become a new task with new sensors and buttons, and its history would no longer be attached. For new tasks, pick any unique text, e.g. `"my-boat-service"`. |
| `template_id` | no | The catalog task this came from, or `null` for your own tasks. Use `null` for new tasks you add by hand. The catalog uses this to know a task is already in the plan, so it isn't suggested again. |
| `instance` | no | Bathroom number (1, 2, 3) for per-bathroom catalog tasks, otherwise `null`. |
| `title` | yes | Shown everywhere. It also becomes the entity name: a new task called "Service på båten" gets `sensor.<property>_service_pa_baten`. Renaming an existing task keeps its entity ID. |
| `description` | no | Free text, `""` for none. |
| `category` | yes | One of `safety`, `indoor`, `wet_room`, `heating`, `ventilation`, `exterior`, `outdoor`, `cabin`, `seasonal`. |
| `schedule` | yes | When the task recurs. See [Schedules](#schedules). |
| `due_soon_days` | yes | Whole number ≥ 0. The status becomes *due soon* this many days before `next_due`. For fixed tasks, it also sets how early *Done* is accepted. |
| `next_due` | yes | The next due date, `"YYYY-MM-DD"`. **This is what the plan runs on.** See the warning below. |
| `last_completed` | no | `"YYYY-MM-DD"` or `null`. Shown as "last done". Changing it does *not* move `next_due`. |
| `status` | no (default `"active"`) | `"active"` or `"archived"`. Archived tasks are shown under *Removed* and have no entities. |
| `last_notified_state` | no | Internal bookkeeping for due notifications. On import it's recalculated for active tasks, so you never need to edit it. |
| `created_at` | no | ISO timestamp. For fixed tasks, the year view doesn't show dates before this as *missed*. For a new task, set it to today's date (e.g. `"2026-11-22"`). Without it, earlier fixed dates this year show as *missed* in the year view. |
| `updated_at` | no | ISO timestamp, informational. |

> ⚠️ **`next_due` is never recalculated on import.** When you change a task's `schedule` in
> the file, also set `next_due` to the date it should next be done. In the panel's edit dialog
> this happens for you; in the file it doesn't. Likewise, changing `last_completed` alone
> doesn't move `next_due`.

### Schedules

**Fixed dates.** The task belongs to the calendar or a season and recurs on the same dates
every year:

```json
"schedule": { "type": "fixed", "dates": [{ "month": 4, "day": 15 }, { "month": 9, "day": 15 }] }
```

- `dates` needs at least one date.
- Each date is `{"month": 1–12, "day": 1–31}`, and the day must exist in that month.
- `29 February` is allowed. In non-leap years it falls on 28 February.
- Order doesn't matter; dates are sorted on import.
- `next_due` should normally be one of these dates. If you set another date, it's used once,
  and the task then returns to the listed dates.

**Interval.** The task depends on wear or elapsed time, and the next date counts from when it
was actually done:

```json
"schedule": { "type": "interval", "every": 3, "unit": "months" }
```

- `every` is a whole number ≥ 1.
- `unit` is `"months"` or `"years"`.
- When the task is completed, `next_due` becomes the completion date plus the interval. Month
  ends are clamped, so 31 Jan + 1 month = 28/29 Feb.

**A sensible `due_soon_days`** follows the shortest gap between occurrences. These are the
defaults Boligloggen uses:

| Period | Default |
|---|---|
| up to 1 month | 3 |
| up to 3 months | 7 |
| up to 6 months | 14 |
| up to 12 months | 21 |
| longer | 60 |

### Removing vs. archiving

- **`"status": "archived"`** is the same as *Remove* in the panel. The task disappears from the
  plan and loses its sensor and button. It can be restored later, and its history stays
  attached.
- **Deleting the object from the file** removes the task completely. Its sensor and button are
  removed. If you import the history, its log entries stay, shown as "(removed task)" on the
  History tab.

---

## `log` (history)

Only imported when **include history** is ticked, in which case it replaces the current history
completely.

```json
"log": [
  {
    "id": "0b7d…",
    "task_id": "5c1f0e3a9b2d4f8e8a7b6c5d4e3f2a1b",
    "completed_on": "2025-12-03",
    "occurrence_date": "2025-12-01",
    "user_id": "8f0e…",
    "user_name": "Kari",
    "note": "Byttet batteri i gangen",
    "forced": false,
    "prev_next_due": "2025-12-01",
    "prev_last_completed": null,
    "created_at": "2025-12-03T17:02:11+00:00"
  }
]
```

| Field | Required | Meaning |
|---|---|---|
| `id` | yes | Unique within the file; any non-empty string. |
| `task_id` | yes | The `id` of the task that was completed. |
| `completed_on` | yes | The day the work was done, `"YYYY-MM-DD"`. |
| `occurrence_date` | yes | The due date this completion covered. For fixed tasks, the year view marks this date *done*. Normally the task's `next_due` at the time. |
| `prev_next_due` | yes | The task's `next_due` *before* this completion. *Undo* uses it to put the task back. |
| `prev_last_completed` | no | The task's `last_completed` before this completion, or `null`. Also used by *Undo*. |
| `user_id` | no | The Home Assistant user ID, or `null`. IDs are specific to one Home Assistant, so when moving a plan to another installation set them to `null`. The name below is still shown, but *Undo* is then only available to admins. |
| `user_name` | no | The name shown in the history and logbook. Default `"System"`. |
| `note` | no | Free text or `null`. |
| `forced` | no | `true` if it was completed before its due-soon window. |
| `created_at` | no | When the entry was recorded. Informational. |

The **order of the list matters.** It's the order the completions were recorded, oldest first.
*Undo* always removes a task's **last** entry in the list, so add new entries at the end.

Editing the history doesn't change the tasks. If you add a completion by hand, also update the
task's `last_completed` and `next_due` to match.

---

## `onboarding_feedback`

```json
"onboarding_feedback": {
  "deselected_at_review": ["leaf_raking"],
  "added_later": ["bleed_radiators"],
  "removed_later": []
}
```

These are lists of catalog task keys (`template_id`, or `template_id#n` for per-bathroom
tasks). They record how well the suggested plan fitted, and appear in the diagnostics
download. They don't affect the plan. Leave them as they are, or empty them.

---

## Recipes

### Add your own task

Add an object to `tasks`. Use a new unique `id`, `"template_id": null`, and set `next_due`
yourself:

```json
{
  "id": "boat-service",
  "template_id": null,
  "title": "Service på båtmotoren",
  "description": "Bytt olje, impeller og tennplugger.",
  "category": "outdoor",
  "schedule": { "type": "fixed", "dates": [{ "month": 4, "day": 1 }] },
  "due_soon_days": 21,
  "next_due": "2027-04-01",
  "last_completed": null,
  "status": "active",
  "created_at": "2026-11-22"
}
```

### Move all gutter and roof tasks to May

Change their `schedule.dates` and `next_due` together:

```json
"schedule": { "type": "fixed", "dates": [{ "month": 5, "day": 10 }] },
"next_due": "2027-05-10"
```

### Copy a plan to a new cabin

1. Add the new property in Home Assistant, untick everything on the review step, and export
   the original property.
2. In the copy of the file, change `profile.name` (and the other profile fields that differ),
   and delete the tasks that don't apply.
3. Set `"log": []`, or leave *include history* unticked.
4. Open the panel, switch to the new property, and import.

Task `id`s only need to be unique within one property, so the copied IDs are fine.

### Fix a completion logged on the wrong day

Find the entry in `log` and change `completed_on` (and `occurrence_date` if it's a fixed task).
If it's the task's latest completion, also fix the task's `last_completed`. For interval tasks,
also fix `next_due` (= the new `completed_on` + the interval). Then import **with history**.

---

## What an import checks

The whole file is checked before anything is replaced. On any error, the property is
unchanged.

| Error | Meaning |
|---|---|
| *Not a Boligloggen export file* (`not_boligloggen_file`) | `format` is missing or wrong, or the file isn't a JSON object. |
| *Made by a newer version* (`unsupported_version`) | `format_version` or `schema_version` is newer than this Boligloggen understands. |
| *Damaged or edited incorrectly* (`invalid_content`) | A field is missing, has the wrong type, or has a value that isn't allowed. The message gives the path, e.g. `property.tasks[3].schedule: invalid day 31 for month 4` or `property.profile.attributes.heating 'heat-pump'`. |
| *Not valid JSON* | Syntax error: usually a missing comma, a trailing comma, or a stray quote. Your editor will show where. |

Other limits:
- at most 2000 tasks and 50 000 log entries
- in the panel, files up to 3.5 MB (years of history fit easily)
- duplicate task `id`s or log `id`s are refused

## What happens on import

1. The profile, language, tasks and feedback are replaced. The history is replaced only with
   *include history*.
2. The due status of every active task is recalculated quietly. Importing tasks that are
   already overdue doesn't send *due soon* or *overdue* notifications.
3. Sensors and buttons are created for new active tasks and removed for tasks that are archived
   or gone. Tasks whose `id` is unchanged keep their entity IDs, so dashboards and automations
   keep working.
4. If `profile.name` changed, the property's device and integration entry are renamed.
5. The new plan is saved.

Developers can do the same without the panel through the admin-only websocket commands
`boligloggen/export` and `boligloggen/import` (see the README).
