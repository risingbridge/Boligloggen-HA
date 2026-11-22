# Building your own year-wheel (årshjul) card

Boligloggen deliberately ships **no** custom Lovelace card. Instead it exposes everything a card
needs through a small, read-only websocket API plus the normal services, so you can draw the
year your way: a classic round årshjul, a horizontal timeline, a month grid, whatever fits your
dashboard and theme.

This guide covers:

1. [What data is available](#1-data-sources) and which source to use for what
2. [The websocket API](#2-websocket-api-reference) with example payloads
3. [Turning dates into a wheel](#3-from-dates-to-a-wheel) (angles, months, today marker)
4. [Keeping the card up to date](#4-keeping-the-card-fresh) (including for non-admin users)
5. [Acting from the card](#5-acting-from-the-card): opening a task and marking it done
6. [A complete, dependency-free example card](#6-a-complete-minimal-card)
7. [Theming, translations and packaging](#7-theming-translations-and-packaging)
8. [Gotchas](#8-gotchas)

If you only want a dashboard built from standard cards, see
[`entities-and-dashboards.md`](entities-and-dashboards.md) instead.

---

## 1. Data sources

| You want… | Use | Why |
|---|---|---|
| List of properties (house, cabin…) | `boligloggen/properties` | gives the `config_entry_id` every other call needs |
| Every occurrence of every task in a given year, with status | `boligloggen/year_plan` | this *is* the wheel data; projection is done server-side |
| Task details (description, schedule text, entity IDs, next due) | `boligloggen/tasks` | for tooltips, detail popups and linking to entities |
| Who did what, when | `boligloggen/log` | paginated history, newest first |
| "Something changed, redraw" | entity state changes in `hass.states` | works for all users (see §4) |
| Mark done / undo | services `boligloggen.complete_task` / `undo_completion` | records the user who clicked |

Do **not** re-implement the scheduling rules in the card. `year_plan` already handles fixed vs.
interval schedules, month-end clamping, 29 February, missed occurrences and the
`due_soon` window. Your card only has to draw.

---

## 2. Websocket API reference

All commands are read-only, require an authenticated connection and are allowed for **every**
logged-in user (admin or not). From a card you call them with `hass.callWS(...)`.

An unknown, unloaded or non-Boligloggen `config_entry_id` returns an error with code
`not_found`.

### `boligloggen/properties`

```js
await hass.callWS({ type: "boligloggen/properties" });
```

```json
[
  { "config_entry_id": "01JD…", "name": "Enebolig", "type": "house" },
  { "config_entry_id": "01JE…", "name": "Hytta",    "type": "cabin" }
]
```

`type` is one of `house`, `townhouse`, `apartment`, `cabin`.

### `boligloggen/year_plan`

```js
await hass.callWS({ type: "boligloggen/year_plan", config_entry_id, year: 2027 });
```

```json
[
  {
    "task_id": "a1b2c3",
    "title": "Vask vinduer",
    "category": "exterior",
    "schedule_type": "fixed",
    "occurrences": [
      { "date": "2027-04-15", "status": "upcoming" },
      { "date": "2027-09-15", "status": "upcoming" }
    ]
  },
  {
    "task_id": "d4e5f6",
    "title": "Rens filter i varmepumpe",
    "category": "heating",
    "schedule_type": "interval",
    "occurrences": [
      { "date": "2027-02-22", "status": "done" },
      { "date": "2027-05-22", "status": "due_soon" },
      { "date": "2027-08-22", "status": "upcoming" },
      { "date": "2027-11-22", "status": "upcoming" }
    ]
  }
]
```

- Only **active** tasks are included; archived ones are left out.
- `year` must be between 2000 and 2200.
- `occurrences` is sorted by date and may be empty, e.g. for a 7-year task that isn't due this
  year.
- `status` is one of:

| Status | Meaning |
|---|---|
| `done` | completed: a log entry exists for this occurrence |
| `missed` | a fixed date that was skipped: the task was completed later, closing it |
| `overdue` | the current occurrence is past due, or a later fixed date is already in the past |
| `due_soon` | the current occurrence is inside its warning window (`due_soon_days`) |
| `upcoming` | in the future and not yet in the warning window |

How occurrences are produced:

- **fixed** tasks have one occurrence per configured date in the year. Dates before the task
  was created are omitted.
- **interval** tasks have past occurrences equal to the actual completion dates (`done`),
  followed by `next_due` and projections from it (`next_due + interval`, …) until 31 December.
  So for interval tasks a `done` dot sits on the day the job was actually done, not on the day
  it was planned.

`category` is one of `safety`, `indoor`, `wet_room`, `heating`, `ventilation`, `exterior`,
`outdoor`, `cabin`, `seasonal`. Custom tasks use the same set. Categories make good rings or
colour groups.

### `boligloggen/tasks`

```js
await hass.callWS({ type: "boligloggen/tasks", config_entry_id, include_archived: false });
```

```json
[
  {
    "id": "d4e5f6",
    "template_id": "heat_pump_filter",
    "instance": null,
    "title": "Rens filter i varmepumpe",
    "description": "Støvsug eller skyll innefilteret …",
    "category": "heating",
    "schedule": { "type": "interval", "every": 3, "unit": "months" },
    "schedule_text": "Hvert kvartal",
    "due_soon_days": 7,
    "next_due": "2027-05-22",
    "days_until_due": 181,
    "due_status": "ok",
    "last_completed": "2027-02-22",
    "last_completed_by": "Kari",
    "status": "active",
    "sensor_entity_id": "sensor.enebolig_rens_filter_i_varmepumpe",
    "button_entity_id": "button.enebolig_rens_filter_i_varmepumpe_utfort",
    "created_at": "2026-11-22T10:15:00+01:00",
    "updated_at": "2027-02-22T18:02:11+01:00"
  }
]
```

- Fixed schedules look like `{"type": "fixed", "dates": [{"month": 4, "day": 15}, …]}`.
- `due_status` is `ok`, `due_soon` or `overdue`. This is the task-level status; it differs from
  the per-occurrence `status` above, which uses `upcoming` instead of `ok`.
- `status` is `active` or `archived`.
- `schedule_text` is already translated into the property's language.
- `sensor_entity_id` and `button_entity_id` can be `null` while entities are being created or
  if a user has deleted them.
- Join with `year_plan` on `year_plan[].task_id == tasks[].id`.

### `boligloggen/log`

```js
await hass.callWS({
  type: "boligloggen/log",
  config_entry_id,
  limit: 20,          // 1–500, default 50
  task_id: "d4e5f6",  // optional filter
  before: undefined,  // cursor: a log entry id (next_before) or an ISO date
});
```

```json
{
  "entries": [
    {
      "id": "l9…",
      "task_id": "d4e5f6",
      "title": "Rens filter i varmepumpe",
      "completed_on": "2027-02-22",
      "occurrence_date": "2027-02-22",
      "user_id": "abc…",
      "user_name": "Kari",
      "note": "Byttet filter",
      "forced": false,
      "prev_next_due": "2027-02-22",
      "prev_last_completed": "2026-11-22",
      "created_at": "2027-02-22T18:02:11+01:00"
    }
  ],
  "next_before": "l8…"
}
```

Entries are newest first. To get the next page, pass `next_before` back as `before`; it is
`null` on the last page. Passing an ISO date (`"2027-01-01"`) as `before` returns entries
completed before that date, which is handy for "show last year".

`user_id` is `null` and `user_name` is `"System"` for completions made by automations.

---

## 3. From dates to a wheel

A year-wheel maps each date to an angle. Put 1 January at 12 o'clock and go clockwise:

```js
const isLeap = (y) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;

/** Day of year, 0-based, from "YYYY-MM-DD" – no time zones involved. */
function dayOfYear(iso) {
  const [y, m, d] = iso.split("-").map(Number);
  return (Date.UTC(y, m - 1, d) - Date.UTC(y, 0, 1)) / 86_400_000;
}

/** Angle in radians; 0 = 12 o'clock, clockwise. Centred on the day. */
function angleFor(iso, year) {
  const days = isLeap(year) ? 366 : 365;
  return ((dayOfYear(iso) + 0.5) / days) * 2 * Math.PI;
}

/** Point on a circle around (cx, cy) – SVG y grows downwards. */
const polar = (cx, cy, r, a) => [cx + r * Math.sin(a), cy - r * Math.cos(a)];
```

Useful building blocks:

- **Month sectors.** The boundary of month `m` is the angle of `YYYY-MM-01` minus half a day,
  i.e. `dayOfYear(...) / days * 2π`. Put a label at the angle of the 15th.
- **Rings.** Use one ring per category, or per task if the plan is short. Radius =
  `inner + index * step`.
- **Today marker.** Draw a line from the centre at `angleFor(todayIso, year)`, and only when
  `year` is the current year.
- **Seasons.** Optionally shade the background by season: Dec–Feb, Mar–May, Jun–Aug, Sep–Nov.
- **Interval tasks with short periods.** A monthly task produces 12 dots per year. Consider
  drawing interval tasks as thin arcs between occurrences, or limit them to their own ring.

A linear timeline is the same maths with `x = dayOfYear / days * width` instead of an angle.

---

## 4. Keeping the card fresh

The websocket commands are one-shot requests; nothing is pushed. Refetch when something
changes.

You might be tempted to subscribe to the integration's events (`boligloggen_task_completed`
etc.) from the card. **Don't:** Home Assistant only lets **admin** users subscribe to custom
events, so the card would silently stop updating for everyone else in the household.

Instead, use what every card already gets: Lovelace calls your card's `set hass(hass)` setter
on every state change. Every Boligloggen change touches at least one Boligloggen entity:

| Change | Visible as |
|---|---|
| Completion or undo | task sensor state and attributes change, and so does `sensor.<property>_last_completed` |
| Daily status change (`ok` → `due_soon` → `overdue`) | task sensor `status` / `days_until_due` attributes |
| Task added, edited, archived or restored | entities appear or disappear, or the sensor's name, state or attributes change |

So fingerprint the Boligloggen entities and refetch only when the fingerprint changes:

```js
function fingerprint(hass) {
  return Object.values(hass.entities)          // frontend's entity registry
    .filter((e) => e.platform === "boligloggen")
    .map((e) => `${e.entity_id}@${hass.states[e.entity_id]?.last_updated ?? "-"}`)
    .sort()
    .join("|");
}
```

`set hass` fires often, for every entity in the house, so keep it cheap. Compare fingerprints
and only call `callWS` when the fingerprint differs. Also debounce the refetch by around 250
ms, because a single completion updates several entities in quick succession.

With more than one property, filter further. Each property is one device, so you can keep only
the entities whose `hass.entities[id].device_id` belongs to the chosen property.

---

## 5. Acting from the card

**Open the task.** Fire the standard more-info event with the task's sensor:

```js
this.dispatchEvent(new CustomEvent("hass-more-info", {
  bubbles: true, composed: true,
  detail: { entityId: task.sensor_entity_id },
}));
```

**Mark as done.** This is the same thing as pressing the task's button, but it lets you add a
note and a date:

```js
try {
  await hass.callService("boligloggen", "complete_task", {
    entity_id: task.sensor_entity_id,      // or: config_entry_id + task_id
    note: "Byttet filter",                 // optional
    completed_on: "2027-05-20",            // optional, not in the future
    // force: true,                        // optional, skip the "not due yet" guard
  });
} catch (err) {
  // e.g. not_due_yet: "«…» er ikke aktuell før 2027-05-11 …"
  showToast(err.message);
}
```

- The completion is recorded as the logged-in user who clicked.
- **Fixed** tasks refuse completion before their due-soon window opens. Show the error, or
  offer a "complete anyway" option that sends `force: true`.
- `boligloggen.undo_completion` (same target) is allowed for admins and for the user who made
  the completion.
- Admin-only services (`add_task`, `update_task`, `remove_task`, `restore_task`) fail with
  `Unauthorized` for other users. Hide editing controls when `hass.user.is_admin` is false.

Clicks on a `done` dot are a good place to show the log entry. Fetch it with
`boligloggen/log` and `task_id`, then match on `occurrence_date` (fixed tasks) or
`completed_on` (interval tasks).

---

## 6. A complete minimal card

The card below is a single file with no build step and no dependencies. It draws month
sectors, one ring per category, a dot per occurrence coloured by status and a today marker.
Clicking a dot opens the task. Use it as a starting point and restyle freely.

Save it as `config/www/boligloggen-year-wheel.js`, then add it as a dashboard resource (see §7)
and use it like this:

```yaml
type: custom:boligloggen-year-wheel
property: Enebolig      # optional: property name or config_entry_id; default = first property
year: 2027              # optional; default = current year
```

```js
// boligloggen-year-wheel.js – minimal Boligloggen årshjul card (MIT, adapt freely)
const STATUS_COLOR = {
  done: "var(--success-color, #43a047)",
  missed: "var(--disabled-text-color, #9e9e9e)",
  upcoming: "var(--primary-color, #03a9f4)",
  due_soon: "var(--warning-color, #ffa600)",
  overdue: "var(--error-color, #db4437)",
};
const SIZE = 320, C = SIZE / 2, R_OUT = 150, R_IN = 50;

const isLeap = (y) => (y % 4 === 0 && y % 100 !== 0) || y % 400 === 0;
const doy = (iso) => {
  const [y, m, d] = iso.split("-").map(Number);
  return (Date.UTC(y, m - 1, d) - Date.UTC(y, 0, 1)) / 86400000;
};
const polar = (r, a) => [C + r * Math.sin(a), C - r * Math.cos(a)];
const esc = (s) => String(s ?? "").replace(/[&<>"']/g, (ch) => `&#${ch.charCodeAt(0)};`);
const pad = (n) => String(n).padStart(2, "0");
const todayIso = () => {
  const d = new Date();
  return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())}`;
};

class BoligloggenYearWheel extends HTMLElement {
  setConfig(config) {
    this._config = config || {};
    this._fp = null;
    if (!this.shadowRoot) this.attachShadow({ mode: "open" });
  }

  set hass(hass) {
    this._hass = hass;
    const fp = Object.values(hass.entities || {})
      .filter((e) => e.platform === "boligloggen")
      .map((e) => `${e.entity_id}@${hass.states[e.entity_id]?.last_updated ?? "-"}`)
      .sort()
      .join("|");
    if (fp === this._fp) return;
    this._fp = fp;
    clearTimeout(this._timer);
    this._timer = setTimeout(() => this._load(), 250);
  }

  async _load() {
    const hass = this._hass;
    const year = Number(this._config.year) || new Date().getFullYear();
    try {
      const props = await hass.callWS({ type: "boligloggen/properties" });
      const wanted = this._config.property;
      const prop = wanted
        ? props.find((p) => p.config_entry_id === wanted || p.name === wanted)
        : props[0];
      if (!prop) throw new Error(wanted ? `Property "${wanted}" not found` : "No property set up");
      const id = prop.config_entry_id;
      const [plan, tasks] = await Promise.all([
        hass.callWS({ type: "boligloggen/year_plan", config_entry_id: id, year }),
        hass.callWS({ type: "boligloggen/tasks", config_entry_id: id }),
      ]);
      this._render(prop, year, plan, new Map(tasks.map((t) => [t.id, t])));
    } catch (err) {
      this.shadowRoot.innerHTML = `<ha-card><div class="msg">${esc(err.message)}</div></ha-card>`;
    }
  }

  _render(prop, year, plan, tasks) {
    const days = isLeap(year) ? 366 : 365;
    const ang = (iso) => ((doy(iso) + 0.5) / days) * 2 * Math.PI;
    const lang = this._hass.locale?.language || this._hass.language || "nb";
    const monthFmt = new Intl.DateTimeFormat(lang, { month: "short", timeZone: "UTC" });
    const cats = [...new Set(plan.map((t) => t.category))].sort();
    const step = (R_OUT - R_IN - 20) / Math.max(cats.length, 1);
    let svg = "";

    // Month sectors and labels.
    for (let m = 1; m <= 12; m++) {
      const a = (doy(`${year}-${pad(m)}-01`) / days) * 2 * Math.PI;
      const [x1, y1] = polar(R_IN, a), [x2, y2] = polar(R_OUT, a);
      svg += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" class="grid"/>`;
      const [lx, ly] = polar(R_OUT - 8, ang(`${year}-${pad(m)}-15`));
      const label = monthFmt.format(new Date(Date.UTC(year, m - 1, 15)));
      svg += `<text x="${lx}" y="${ly}" class="month">${esc(label)}</text>`;
    }
    // One ring per category.
    cats.forEach((_, i) => {
      svg += `<circle cx="${C}" cy="${C}" r="${R_IN + step * (i + 0.5)}" class="ring"/>`;
    });
    // Today marker.
    const today = todayIso();
    if (today.startsWith(`${year}-`)) {
      const [x, y] = polar(R_OUT, ang(today));
      svg += `<line x1="${C}" y1="${C}" x2="${x}" y2="${y}" class="today"/>`;
    }
    // Occurrences.
    for (const task of plan) {
      const r = R_IN + step * (cats.indexOf(task.category) + 0.5);
      for (const occ of task.occurrences) {
        const [x, y] = polar(r, ang(occ.date));
        svg += `<circle cx="${x}" cy="${y}" r="5" fill="${STATUS_COLOR[occ.status]}"
                 class="dot" data-task="${esc(task.task_id)}">
                 <title>${esc(task.title)} – ${occ.date} (${occ.status})</title></circle>`;
      }
    }

    this.shadowRoot.innerHTML = `
      <style>
        svg { width: 100%; height: auto; display: block; }
        .grid { stroke: var(--divider-color); }
        .ring { fill: none; stroke: var(--divider-color); stroke-dasharray: 2 3; }
        .month { fill: var(--secondary-text-color); font-size: 9px;
                 text-anchor: middle; dominant-baseline: middle; }
        .today { stroke: var(--primary-text-color); stroke-width: 1.5; }
        .dot { cursor: pointer; stroke: var(--card-background-color); stroke-width: 1.5; }
        .center { fill: var(--primary-text-color); font-size: 14px; text-anchor: middle; }
        .msg { padding: 16px; }
      </style>
      <ha-card header="${esc(prop.name)}">
        <svg viewBox="0 0 ${SIZE} ${SIZE}" role="img" aria-label="${esc(prop.name)} ${year}">
          ${svg}
          <text x="${C}" y="${C + 5}" class="center">${year}</text>
        </svg>
      </ha-card>`;

    this.shadowRoot.querySelectorAll(".dot").forEach((el) =>
      el.addEventListener("click", () => {
        const entityId = tasks.get(el.dataset.task)?.sensor_entity_id;
        if (!entityId) return;
        this.dispatchEvent(new CustomEvent("hass-more-info", {
          bubbles: true, composed: true, detail: { entityId },
        }));
      }),
    );
  }

  getCardSize() { return 7; }
  static getStubConfig() { return {}; }
}

customElements.define("boligloggen-year-wheel", BoligloggenYearWheel);
window.customCards = window.customCards || [];
window.customCards.push({
  type: "boligloggen-year-wheel",
  name: "Boligloggen årshjul",
  description: "Year-wheel of the Boligloggen maintenance plan",
});
```

Ideas for taking it further:

- Add a legend, and use category icons instead of plain rings.
- Show a side panel listing the tasks in the clicked month.
- Add previous/next year buttons. Note that only the current year has live statuses; past
  years are mostly `done` and `missed`.
- Add a "Done" button in your own popup that calls `complete_task` (§5).
- Show an overdue banner fed by `boligloggen/tasks` filtered on `due_status` (see §8 for why).

---

## 7. Theming, translations and packaging

**Theming.** Use Home Assistant's CSS variables rather than fixed colours. Then the card follows
the user's theme and dark mode automatically:

| Variable | Good for |
|---|---|
| `--primary-color` | upcoming |
| `--warning-color` | due soon |
| `--error-color` | overdue |
| `--success-color` | done |
| `--disabled-text-color` | missed |
| `--primary-text-color`, `--secondary-text-color` | text |
| `--divider-color` | grid lines |
| `--card-background-color` | cut-outs and dot outlines |

Wrap the card in `<ha-card>` so it gets the theme's card background, radius and shadow.

**Translations.**
- Task titles, descriptions and `schedule_text` are already in the property's language (nb or
  en), as chosen at onboarding.
- Status values and category ids are stable English keys. Translate them in the card, keyed on
  `hass.locale.language`.
- Use `Intl.DateTimeFormat` for month and date names.

**Installing for yourself.**
1. Put the file in `config/www/`.
2. Go to *Settings → Dashboards → ⋮ → Resources → Add resource* and enter
   `/local/boligloggen-year-wheel.js?v=1` as a *JavaScript module*. The menu needs *Advanced
   mode* in your user profile.
3. Bump `?v=` whenever you change the file, so browsers and the companion app reload it.

**Sharing via HACS.**
1. Publish the card in its own GitHub repository. A HACS repo has exactly one category, and
   cards are *Dashboard*, not *Integration*.
2. Add a `hacs.json` such as `{"name": "Boligloggen årshjul", "filename": "boligloggen-year-wheel.js"}`
   and put the file in the repo root or in `dist/`. Users then add the repo as a custom
   repository with category **Dashboard**, and HACS registers the resource for them.
3. In the card's README, state which Boligloggen version it needs. The websocket API is
   versioned with the integration (`manifest.json`).

---

## 8. Gotchas

- **Never parse dates with `new Date("2027-04-15")`.** JavaScript reads that as UTC midnight,
  which in a negative-offset time zone becomes 14 April. Split the string, as `doy()` above
  does, or use `Date.UTC`.
- **"Today" is the Home Assistant server's date**, not the browser's. Statuses are computed in
  HA's time zone. If you compare against the browser clock, a phone abroad can disagree around
  midnight. The today marker is cosmetic, so this rarely matters.
- **Overdue from last year doesn't appear in this year's plan.** An interval task that was due
  last December and is still not done has its `next_due` outside the current year, so
  `year_plan` for the current year shows only its future projections. Show overdue items from
  `boligloggen/tasks` (`due_status == "overdue"`), for example as a banner or in the centre of
  the wheel.
- **Rescheduled fixed tasks.** If an admin sets a fixed task's next due date by hand to an
  off-grid date, that date appears as an extra occurrence in that year. Don't assume fixed
  tasks only land on their configured dates.
- **Long intervals** (e.g. every 7 years) often have no occurrences in a given year. Decide
  whether to hide such tasks or show them in a "not this year" list.
- **Entity IDs can be renamed by users.** Always take them from `sensor_entity_id` and
  `button_entity_id`, never build them from the title.
- **Non-admins can't subscribe to custom events.** See §4. Base refreshes on state changes.
- **Escape titles.** Admins type custom task titles and descriptions as free text. Escape them
  before putting them into `innerHTML`, or use Lit templates, which escape automatically.
