# Entities and dashboards

This guide lists every entity Boligloggen creates, what its state and attributes mean, and
how to build dashboards from them, both with built-in cards only and with a couple of
popular custom cards.

The examples use a property named **Enebolig** (a house set up in Norwegian). Your entity IDs
start with the name you gave the property in onboarding.

---

## 1. How entities are organised

- **One device per property.** Each property you onboard (house, cabin, …) becomes a
  *service* device, made by "Boligloggen", with the property type (`house`, `townhouse`,
  `apartment`, `cabin`) as its model. All of the property's entities belong to that device.
  Find it under *Settings → Devices & services → Boligloggen*.
- **Two entities per task.** Every active task in the plan gets a **sensor** (when it is
  due) and a **button** (mark it done).
- **Five summary entities per property.** Four sensors (next task, overdue count, due-soon
  count, last completed) and one calendar.
- **The entities follow the plan.** Adding or restoring a task creates its sensor and button
  straight away. Removing (archiving) a task deletes them, but its history is kept and comes
  back if you restore it.

### Entity IDs

Home Assistant builds entity IDs from the device name and the entity name:

| Entity | ID pattern | Example |
|---|---|---|
| Task sensor | `sensor.<property>_<task title>` | `sensor.enebolig_rens_filter_i_varmepumpe` |
| Task button | `button.<property>_<task title>_utfort` (`…_done` for English plans) | `button.enebolig_rens_sluk_bad_1_utfort` |
| Next task | `sensor.<property>_next_task` | `sensor.enebolig_next_task` |
| Overdue | `sensor.<property>_overdue` | `sensor.enebolig_overdue` |
| Due soon | `sensor.<property>_due_soon` | `sensor.enebolig_due_soon` |
| Last completed | `sensor.<property>_last_completed` | `sensor.enebolig_last_completed` |
| Calendar | `calendar.<property>_maintenance_plan` | `calendar.enebolig_maintenance_plan` |

Some things to know about IDs:

- Norwegian letters become ASCII (`ø → o`, `å → a`, `æ → ae`), and punctuation becomes
  `_`. "Rens sluk – bad 1" becomes `rens_sluk_bad_1`.
- The summary entities always get **English** IDs (`_next_task`, `_overdue`, …). Their
  *display names* follow your language ("Neste gjøremål", "Forfalt", …).
- An ID is fixed when the entity is created. Renaming a task later changes its display
  name but not its ID. You can always rename IDs yourself in the entity settings.
- The task language (Norwegian or English) is chosen once, from your Home Assistant language
  when you onboard the property.

---

## 2. Entity reference

### 2.1 Task sensor (`sensor`, device class `date`)

**State:** the task's next due date, e.g. `2026-12-01`. With device class `date`, the
frontend shows it as a date and the tile card can show it as relative time.

**Icon:** depends on the task's category.

| Category | Icon |
|---|---|
| `safety` | `mdi:shield-check` |
| `indoor` | `mdi:sofa` |
| `wet_room` | `mdi:shower` |
| `heating` | `mdi:fire` |
| `ventilation` | `mdi:fan` |
| `exterior` | `mdi:home-roof` |
| `outdoor` | `mdi:pine-tree` |
| `cabin` | `mdi:home-variant` |
| `seasonal` | `mdi:calendar-sync` |

**Attributes:**

| Attribute | Type | Meaning |
|---|---|---|
| `status` | `ok` \| `due_soon` \| `overdue` | `due_soon` = within `due_soon_days` of the due date; `overdue` = past it. **This is the main attribute for dashboards.** |
| `days_until_due` | int | Days until `next_due`; negative when overdue. Good for sorting. |
| `task_id` | string | Stable ID, used by the services. |
| `category` | string | One of the categories above. |
| `schedule_type` | `fixed` \| `interval` | Fixed = calendar/season dates; interval = counted from last done. |
| `schedule` | object | `{text, type, …}`. `text` is human readable ("Hvert kvartal", "Årlig 1. des"); the rest is the raw schedule (`every`/`unit` or `dates`). *Not recorded.* |
| `due_soon_days` | int | Size of the warning window. |
| `last_completed` | date \| null | When it was last done. |
| `last_completed_by` | string \| null | Who did it: the HA user's name, or `System` for automations. |
| `description` | string | Explanation of the task. *Not recorded.* |
| `template_id` | string \| null | Catalog template; `null` for custom tasks. |

Attributes marked *not recorded* are kept out of the recorder database to keep it small.

### 2.2 Task button (`button`)

Pressing it marks the task as **done today**, as the logged-in user. That adds a log entry,
moves `next_due`, fires `boligloggen_task_completed` and shows up in the logbook.

- **Fixed-date tasks can't be completed early.** Outside their due-soon window the press is
  refused ("Ikke aktuell før …"). To complete one anyway, use the `boligloggen.complete_task`
  service with `force: true`.
- **Interval tasks can always be pressed.** The next due date is then counted from today.
- **Attributes:** `task_id`.
- **State:** like all buttons, the timestamp of the last press. It's the *sensor* you want to
  show, not the button's state.

To add a note or a different date, call `boligloggen.complete_task` instead (see §4.3).

### 2.3 Next task (`sensor.<property>_next_task`)

| | |
|---|---|
| State | Title of the task with the earliest `next_due` (ties broken by title); `unknown` if the plan is empty |
| Attributes | `task_id`, `next_due`, `status` |

### 2.4 Overdue / due soon (`sensor.<property>_overdue`, `sensor.<property>_due_soon`)

| | |
|---|---|
| State | Number of tasks with that status |
| Attributes | `tasks`: up to 10 tasks, earliest first, as `{task_id, title, next_due}`. *Not recorded.* |

These are the obvious triggers for badges, conditional cards and automations.

### 2.5 Last completed (`sensor.<property>_last_completed`)

| | |
|---|---|
| State | Title of the most recently completed task |
| Attributes | `task_id`, `user_name`, `completed_on`, `note` |

### 2.6 Maintenance plan calendar (`calendar.<property>_maintenance_plan`)

A read-only calendar with an **all-day event for every occurrence** of every active task,
past and future:

- Completed occurrences are prefixed with `✓ `.
- Fixed tasks appear on each of their dates every year. Interval tasks appear at the next due
  date and then every interval after it.
- The entity's state is `on` while the current event is happening. Its attributes (`message`,
  `start_time`, …) describe the next upcoming occurrence. While any task is overdue, the
  current event is the oldest overdue task, shown on today's date.

Use it in the calendar card, or as a calendar trigger in automations.

### 2.7 Events (for automations and custom cards)

These are not entities, but they're useful next to a dashboard:

| Event | When |
|---|---|
| `boligloggen_task_completed` | A task is completed (includes `user_name`, `note`, `occurrence_date`) |
| `boligloggen_task_due_soon` | Once, when a task enters its due-soon window |
| `boligloggen_task_overdue` | Once, when a task becomes overdue |

The shipped blueprint (`blueprints/automation/boligloggen/notify_due.yaml`) turns these into
phone notifications. See the README.

---

## 3. Planning a dashboard

A plan often has 30+ tasks, so don't put every task on the main view. A layout that works
well:

1. **Overview** (the top of the main dashboard, or your home view): overdue and due-soon
   counts, the next task, and a "done" button for whatever is due.
2. **"Due now" list**: only tasks whose `status` is `overdue` or `due_soon`, earliest
   first, each with a one-tap "done".
3. **Year plan**: the calendar card in list or month view.
4. **Full plan**: every task, grouped by category, on its own view. Use it for checking and
   occasional manual completion.
5. **History**: a logbook card showing who did what.

Sections 4.1–4.5 build these with **built-in cards only**. Section 5 shows a more dynamic
version with custom cards from HACS.

---

## 4. Dashboards with built-in cards

### 4.1 Overview with badges and a tile

```yaml
type: sections
title: Boligloggen
sections:
  - type: grid
    cards:
      - type: heading
        heading: Vedlikehold
        badges:
          - type: entity
            entity: sensor.enebolig_overdue
            color: red
            visibility:
              - condition: numeric_state
                entity: sensor.enebolig_overdue
                above: 0
          - type: entity
            entity: sensor.enebolig_due_soon
            color: amber
      - type: tile
        entity: sensor.enebolig_next_task
        name: Neste gjøremål
        icon: mdi:calendar-check
        state_content: [state, next_due]
        grid_options:
          columns: full
```

### 4.2 One tile per important task, with one-tap "done"

The task sensor shows the due date and status. Tapping the tile presses the task's button,
with a confirmation so nobody completes something by accident:

```yaml
type: tile
entity: sensor.enebolig_rens_filter_i_varmepumpe
state_content: [state, status, last_completed_by]
tap_action:
  action: perform-action
  perform_action: button.press
  target:
    entity_id: button.enebolig_rens_filter_i_varmepumpe_utfort
  confirmation:
    text: Merke «Rens filter i varmepumpe» som utført?
hold_action:
  action: more-info
```

To put the button itself on the dashboard instead:

```yaml
type: tile
entity: button.enebolig_rens_sluk_bad_1_utfort
name: Rens sluk – bad 1
icon: mdi:check
tap_action:
  action: perform-action
  perform_action: button.press
  target:
    entity_id: button.enebolig_rens_sluk_bad_1_utfort
  confirmation: true
```

### 4.3 "Done, with a note" via a script

Buttons can't take a note. Add a script that calls the service and opens a field:

```yaml
# scripts.yaml
boligloggen_complete_with_note:
  alias: Fullfør gjøremål med notat
  fields:
    task:
      name: Gjøremål
      required: true
      selector:
        entity:
          integration: boligloggen
          domain: sensor
    note:
      name: Notat
      selector:
        text:
          multiline: true
  sequence:
    - action: boligloggen.complete_task
      data:
        entity_id: "{{ task }}"
        note: "{{ note }}"
```

Run it from a tile (`tap_action: more-info` on `script.boligloggen_complete_with_note`) and
fill in the fields in the dialog. The action runs as the user who started the script, so
`last_completed_by` is still correct.

### 4.4 Lists that update themselves, with a Markdown card

The built-in `entity-filter` card needs a hand-written list of entities. A **Markdown card**
can find every task by itself. This one lists overdue and due-soon tasks, earliest first:

```yaml
type: markdown
title: Må gjøres
content: >-
  {%- set tasks = integration_entities('boligloggen')
       | select('match', 'sensor')
       | expand
       | selectattr('attributes.days_until_due', 'defined')
       | selectattr('attributes.status', 'in', ['overdue', 'due_soon'])
       | sort(attribute='attributes.days_until_due') | list -%}
  {%- if tasks | count == 0 -%}
  ✅ Ingenting å gjøre akkurat nå.
  {%- else -%}
  {%- for t in tasks %}
  {{ '🔴' if t.attributes.status == 'overdue' else '🟡' }} **{{ t.name }}**
  — {{ t.state }} ({{ t.attributes.days_until_due }} dager){% if t.attributes.last_completed_by %}
  · sist: {{ t.attributes.last_completed_by }}{% endif %}
  {%- endfor %}
  {%- endif -%}
```

Notes:

- `selectattr('attributes.days_until_due', 'defined')` keeps the **task** sensors only. The
  summary sensors don't have that attribute.
- With several properties, replace `integration_entities('boligloggen')` with the entities of
  one property's device, e.g.
  `device_entities(device_id('sensor.enebolig_next_task'))`.
- Markdown cards can't press buttons, so pair this list with tiles (4.2) or the script (4.3).

The whole plan grouped by category, as a read-only overview:

```yaml
type: markdown
title: Hele planen
content: >-
  {%- set tasks = integration_entities('boligloggen')
       | select('match', 'sensor')
       | expand
       | selectattr('attributes.days_until_due', 'defined')
       | sort(attribute='attributes.days_until_due') | list -%}
  {%- for cat, items in tasks | groupby('attributes.category') %}
  ### {{ cat | replace('_', ' ') | capitalize }}
  {%- for t in items %}
  - {{ t.name }} — {{ t.state }} · {{ t.attributes.schedule.text }}
  {%- endfor %}
  {%- endfor %}
```

### 4.5 Calendar, history and an alert

```yaml
- type: calendar
  entities:
    - calendar.enebolig_maintenance_plan
  initial_view: listWeek       # or dayGridMonth for a month grid

- type: logbook
  title: Hvem gjorde hva
  target:
    device_id: <your Boligloggen device id>   # pick the device in the card editor
  hours_to_show: 720

- type: conditional
  conditions:
    - condition: numeric_state
      entity: sensor.enebolig_overdue
      above: 0
  card:
    type: markdown
    content: >-
      ⚠️ **{{ states('sensor.enebolig_overdue') }} forfalte gjøremål:**
      {% for t in state_attr('sensor.enebolig_overdue', 'tasks') %}
      {{ t.title }} ({{ t.next_due }}){{ ', ' if not loop.last }}
      {%- endfor %}
```

The logbook card shows lines like "Kari fullførte «Rens sluk – bad 1»".

---

## 5. Dynamic dashboards with custom cards (HACS)

These cards aren't part of Home Assistant; install them from HACS → *Frontend*.

### 5.1 auto-entities: a "due now" list with buttons, no hand-written list

[auto-entities](https://github.com/thomasloven/lovelace-auto-entities) fills any card with
entities that match a filter. This one shows every overdue or due-soon task as a tile,
sorted by due date. Tapping a tile asks for confirmation and then completes the task:

```yaml
type: custom:auto-entities
show_empty: false
card:
  type: grid
  columns: 1
  square: false
card_param: cards
filter:
  include:
    - integration: boligloggen
      domain: sensor
      attributes:
        status: overdue
      options: &task_tile
        type: tile
        state_content: [state, status]
        tap_action:
          action: perform-action
          perform_action: boligloggen.complete_task
          data:
            entity_id: this.entity_id
          confirmation: true
    - integration: boligloggen
      domain: sensor
      attributes:
        status: due_soon
      options: *task_tile
sort:
  method: attribute
  attribute: days_until_due
  numeric: true
```

- auto-entities replaces `this.entity_id` with each matching entity. The service accepts the
  task **sensor**, so you don't need the button's ID.
- The service refuses early completion of fixed-date tasks. A task that is only due soon is
  inside its window, so it completes normally.
- For the full plan, drop the `attributes` filter and add one auto-entities card per category
  (`attributes: {category: heating}` and so on).

### 5.2 Colour tiles by status with card-mod

Paired with [card-mod](https://github.com/thomasloven/lovelace-card-mod), add this to the tile
`options` above:

```yaml
card_mod:
  style: |
    ha-card {
      --tile-color: {{ {'overdue': 'var(--red-color)',
                        'due_soon': 'var(--amber-color)'}
                       .get(state_attr(config.entity, 'status'), 'var(--green-color)') }};
    }
```

---

## 6. Using the data in your own card

A planned custom year-wheel (årshjul) card will read the integration's read-only websocket API
rather than entities:

- `boligloggen/properties`: list of properties
- `boligloggen/tasks`: every task, including its sensor and button entity IDs
- `boligloggen/year_plan`: every occurrence in a year with `done | missed | upcoming |
  due_soon | overdue`
- `boligloggen/log`: the completion log, newest first, paginated

See the README for the parameters. For your own cards, prefer these over scraping entity
attributes: they also cover archived tasks, full history and next year's plan.

---

## 7. Troubleshooting

| Symptom | Cause / fix |
|---|---|
| A task's entities disappeared | The task was removed (archived). Restore it under *Configure → Gjenopprett*. |
| Pressing "done" shows "Ikke aktuell før …" | Fixed-date task outside its window. Wait, or use `complete_task` with `force: true`. |
| `last_completed_by` is `System` | Completed by an automation or script with no user. |
| Entity ID still has the old task name | IDs don't change on rename. Rename the ID in the entity settings if you like. |
| Counts don't change at midnight | Statuses are recalculated at 00:05 and at every change. |
