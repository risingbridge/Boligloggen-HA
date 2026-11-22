// Boligloggen admin panel.
//
// A dependency-free web component served by the integration (see panel.py) and
// shown in the sidebar for admin users only. It reads through the websocket API
// (boligloggen/properties, /tasks, /catalog, /log) and writes only through the
// integration's services, so every change gets the same validation, admin check
// and events as a service call from an automation.

const DOMAIN = "boligloggen";
const CATEGORIES = [
  "safety", "indoor", "wet_room", "heating", "ventilation",
  "exterior", "outdoor", "cabin", "seasonal",
];
const LOG_PAGE = 50;

const I18N = {
  en: {
    tabs: { plan: "Plan", add: "Add tasks", archived: "Removed", history: "History" },
    category: {
      safety: "Safety", indoor: "Indoor", wet_room: "Wet room", heating: "Heating",
      ventilation: "Ventilation", exterior: "Exterior", outdoor: "Outdoor",
      cabin: "Cabin", seasonal: "Seasonal",
    },
    status: { ok: "On track", due_soon: "Due soon", overdue: "Overdue" },
    property: "Property",
    filter: "Filter tasks…",
    property_details: "Edit property details",
    next_due: "Next",
    last_done: "Last",
    never_done: "Never done",
    edit: "Edit",
    undo: "Undo last",
    archive: "Remove",
    restore: "Restore",
    no_tasks: "No tasks in the plan yet. Add some from the catalog.",
    no_match: "No tasks match the filter.",
    no_archived: "No removed tasks.",
    no_history: "Nothing has been completed yet.",
    no_properties: "No property is set up yet.",
    add_property: "Add Boligloggen",
    not_admin: "Only administrators can edit the maintenance plan.",
    catalog_title: "From the catalog",
    catalog_help: "Tasks that match this property and aren't in the plan yet.",
    show_all: "Show the whole catalog",
    not_matching: "doesn't match the property",
    catalog_empty: "Every matching catalog task is already in the plan (or removed).",
    add_selected: (n) => `Add selected (${n})`,
    added: (n) => (n === 1 ? "1 task added" : `${n} tasks added`),
    custom_title: "Custom task",
    custom_help: "Anything the catalog doesn't cover, with its own schedule.",
    new_custom: "New custom task",
    load_more: "Load more",
    forced: "forced",
    by: "by",
    removed_task: "(removed task)",
    confirm_archive: (t) => `Remove «${t}» from the plan? Its history is kept and it can be restored.`,
    confirm_undo: (t, who) => `Undo the latest completion of «${t}»${who ? ` (by ${who})` : ""}?`,
    archived_msg: (t) => `«${t}» removed`,
    restored_msg: (t) => `«${t}» restored`,
    undone_msg: (t) => `Last completion of «${t}» undone`,
    saved: "Saved",
    dialog_new: "New custom task",
    dialog_edit: (t) => `Edit «${t}»`,
    f_title: "Title",
    f_description: "Description",
    f_category: "Category",
    f_schedule_type: "Schedule",
    f_interval: "Interval (from when last done)",
    f_fixed: "Fixed dates",
    f_every: "Every",
    f_unit: "Unit",
    f_months: "months",
    f_years: "years",
    f_dates: "Dates",
    f_dates_help: "Comma separated, as MM-DD (12-01) or D.M (1.12).",
    f_due_soon: "Warning days (due soon)",
    f_due_soon_help: "Leave empty for the default.",
    f_last: "Last done",
    f_last_help: "Changing this recalculates the next due date.",
    f_next: "Next due",
    cancel: "Cancel",
    save: "Save",
    create: "Add",
    loading: "Loading…",
  },
  nb: {
    tabs: { plan: "Plan", add: "Legg til", archived: "Fjernet", history: "Historikk" },
    category: {
      safety: "Sikkerhet", indoor: "Innendørs", wet_room: "Våtrom", heating: "Oppvarming",
      ventilation: "Ventilasjon", exterior: "Utvendig", outdoor: "Uteområde",
      cabin: "Hytte", seasonal: "Sesong",
    },
    status: { ok: "I rute", due_soon: "Snart aktuelt", overdue: "Forfalt" },
    property: "Bolig",
    filter: "Filtrer gjøremål…",
    property_details: "Endre boligdetaljer",
    next_due: "Neste",
    last_done: "Sist",
    never_done: "Aldri utført",
    edit: "Endre",
    undo: "Angre siste",
    archive: "Fjern",
    restore: "Gjenopprett",
    no_tasks: "Planen er tom. Legg til gjøremål fra katalogen.",
    no_match: "Ingen gjøremål passer filteret.",
    no_archived: "Ingen fjernede gjøremål.",
    no_history: "Ingenting er utført ennå.",
    no_properties: "Ingen bolig er satt opp ennå.",
    add_property: "Legg til Boligloggen",
    not_admin: "Bare administratorer kan endre vedlikeholdsplanen.",
    catalog_title: "Fra katalogen",
    catalog_help: "Gjøremål som passer boligen og ikke er i planen ennå.",
    show_all: "Vis hele katalogen",
    not_matching: "passer ikke boligen",
    catalog_empty: "Alle gjøremål som passer boligen er allerede i planen (eller fjernet).",
    add_selected: (n) => `Legg til valgte (${n})`,
    added: (n) => (n === 1 ? "1 gjøremål lagt til" : `${n} gjøremål lagt til`),
    custom_title: "Egendefinert gjøremål",
    custom_help: "Alt katalogen ikke dekker, med egen plan.",
    new_custom: "Nytt egendefinert gjøremål",
    load_more: "Vis flere",
    forced: "tvunget",
    by: "av",
    removed_task: "(fjernet gjøremål)",
    confirm_archive: (t) => `Fjerne «${t}» fra planen? Historikken beholdes, og gjøremålet kan gjenopprettes.`,
    confirm_undo: (t, who) => `Angre siste fullføring av «${t}»${who ? ` (av ${who})` : ""}?`,
    archived_msg: (t) => `«${t}» fjernet`,
    restored_msg: (t) => `«${t}» gjenopprettet`,
    undone_msg: (t) => `Siste fullføring av «${t}» angret`,
    saved: "Lagret",
    dialog_new: "Nytt egendefinert gjøremål",
    dialog_edit: (t) => `Endre «${t}»`,
    f_title: "Tittel",
    f_description: "Beskrivelse",
    f_category: "Kategori",
    f_schedule_type: "Type plan",
    f_interval: "Intervall (fra sist utført)",
    f_fixed: "Faste datoer",
    f_every: "Hver",
    f_unit: "Enhet",
    f_months: "måneder",
    f_years: "år",
    f_dates: "Datoer",
    f_dates_help: "Kommaseparert, som MM-DD (12-01) eller D.M (1.12).",
    f_due_soon: "Dager varsel (snart aktuelt)",
    f_due_soon_help: "La stå tomt for standardverdi.",
    f_last: "Sist utført",
    f_last_help: "Endring her beregner neste frist på nytt.",
    f_next: "Neste frist",
    cancel: "Avbryt",
    save: "Lagre",
    create: "Legg til",
    loading: "Laster…",
  },
};

const esc = (value) =>
  String(value ?? "").replace(/[&<>"']/g, (ch) => `&#${ch.charCodeAt(0)};`);

const formatDates = (schedule) =>
  (schedule?.dates || [])
    .map((d) => `${String(d.month).padStart(2, "0")}-${String(d.day).padStart(2, "0")}`)
    .join(", ");

const STYLE = `
  :host {
    display: block;
    min-height: 100vh;
    background: var(--primary-background-color);
    color: var(--primary-text-color);
    font-family: var(--paper-font-body1_-_font-family, Roboto, sans-serif);
  }
  .toolbar {
    display: flex; align-items: center; gap: 12px;
    height: var(--header-height, 56px); padding: 0 12px 0 4px; box-sizing: border-box;
    background: var(--app-header-background-color, var(--primary-color));
    color: var(--app-header-text-color, #fff);
    border-bottom: var(--app-header-border-bottom, none);
    position: sticky; top: 0; z-index: 2;
  }
  .toolbar .title { flex: 1; font-size: 20px; font-weight: 400; padding-left: 12px; }
  .toolbar select { max-width: 45vw; }
  .menu {
    background: none; border: 0; color: inherit; font-size: 22px;
    width: 48px; height: 48px; cursor: pointer;
  }
  .tabs {
    display: flex; gap: 4px; padding: 0 16px; overflow-x: auto;
    border-bottom: 1px solid var(--divider-color);
    background: var(--app-header-background-color, var(--primary-color));
  }
  .tab {
    background: none; border: 0; border-bottom: 2px solid transparent;
    color: var(--app-header-text-color, #fff); opacity: .75;
    padding: 12px 14px; font: inherit; cursor: pointer; white-space: nowrap;
  }
  .tab.active { opacity: 1; border-bottom-color: var(--app-header-text-color, #fff); }
  main { max-width: 960px; margin: 0 auto; padding: 16px; box-sizing: border-box; }
  .card {
    background: var(--card-background-color, #fff);
    border-radius: var(--ha-card-border-radius, 12px);
    border: var(--ha-card-border-width, 1px) solid var(--ha-card-border-color, var(--divider-color));
    box-shadow: var(--ha-card-box-shadow, none);
    padding: 16px; margin-bottom: 16px;
  }
  .card h2 { margin: 0 0 4px; font-size: 18px; font-weight: 500; }
  .help, .sub { color: var(--secondary-text-color); font-size: 13px; }
  .bar { display: flex; flex-wrap: wrap; gap: 8px; align-items: center; margin-bottom: 16px; }
  .bar input[type=search] { flex: 1; min-width: 180px; }
  h3 {
    margin: 20px 0 6px; font-size: 13px; font-weight: 500; text-transform: uppercase;
    letter-spacing: .04em; color: var(--secondary-text-color);
  }
  .row {
    display: flex; flex-wrap: wrap; gap: 8px 12px; align-items: center;
    padding: 10px 12px; border-left: 4px solid var(--divider-color);
    background: var(--card-background-color, #fff);
    border-radius: 8px; margin-bottom: 6px;
  }
  .row.ok { border-left-color: var(--success-color, #43a047); }
  .row.due_soon { border-left-color: var(--warning-color, #ffa600); }
  .row.overdue { border-left-color: var(--error-color, #db4437); }
  .row .main { flex: 1 1 260px; min-width: 0; }
  .row .t { font-weight: 500; overflow-wrap: anywhere; }
  .chip {
    font-size: 12px; padding: 2px 8px; border-radius: 10px; white-space: nowrap;
    background: var(--secondary-background-color); color: var(--primary-text-color);
  }
  .chip.due_soon { background: var(--warning-color, #ffa600); color: #000; }
  .chip.overdue { background: var(--error-color, #db4437); color: #fff; }
  .chip.muted { color: var(--secondary-text-color); }
  .actions { display: flex; gap: 6px; flex-wrap: wrap; }
  button.btn, .btn {
    font: inherit; font-size: 14px; cursor: pointer; border-radius: 8px;
    padding: 6px 12px; border: 1px solid var(--divider-color);
    background: var(--card-background-color, #fff); color: var(--primary-color);
  }
  .btn.primary { background: var(--primary-color); color: var(--text-primary-color, #fff); border-color: transparent; }
  .btn.danger { color: var(--error-color, #db4437); }
  .btn:disabled { opacity: .5; cursor: default; }
  input, select, textarea {
    font: inherit; font-size: 14px; color: var(--primary-text-color);
    background: var(--input-fill-color, var(--secondary-background-color));
    border: 1px solid var(--divider-color); border-radius: 6px; padding: 8px; box-sizing: border-box;
  }
  .toolbar select { color: inherit; background: transparent; border-color: currentColor; }
  .toolbar select option { color: var(--primary-text-color); background: var(--card-background-color, #fff); }
  label.check { display: flex; gap: 10px; align-items: flex-start; padding: 8px 4px; cursor: pointer; }
  label.check input { margin-top: 3px; }
  .empty { padding: 24px; text-align: center; color: var(--secondary-text-color); }
  .log { display: grid; grid-template-columns: auto 1fr; gap: 4px 16px; }
  .log .d { color: var(--secondary-text-color); white-space: nowrap; font-variant-numeric: tabular-nums; }
  .log .note { color: var(--secondary-text-color); font-style: italic; }
  dialog {
    border: 0; border-radius: 16px; padding: 0; width: min(560px, calc(100vw - 32px));
    background: var(--card-background-color, #fff); color: var(--primary-text-color);
    box-shadow: 0 8px 32px rgba(0,0,0,.35);
  }
  dialog::backdrop { background: rgba(0,0,0,.45); }
  dialog form { display: flex; flex-direction: column; max-height: calc(100vh - 64px); }
  dialog header { padding: 20px 24px 8px; font-size: 20px; }
  dialog .fields { padding: 8px 24px; overflow-y: auto; display: grid; gap: 14px; }
  dialog footer { display: flex; justify-content: flex-end; gap: 8px; padding: 16px 24px; }
  .field { display: grid; gap: 4px; }
  .field > span { font-size: 13px; color: var(--secondary-text-color); }
  .field input, .field select, .field textarea { width: 100%; }
  .pair { display: grid; grid-template-columns: 1fr 1fr; gap: 12px; align-items: start; }
  .radios { display: flex; flex-wrap: wrap; gap: 4px 16px; }
  .radios label { display: flex; gap: 6px; align-items: center; cursor: pointer; }
  .field .radios input { width: auto; margin: 0; }
  .error {
    color: var(--error-color, #db4437); font-size: 14px;
    padding: 8px 12px; border-radius: 6px; background: rgba(219,68,55,.08);
  }
  [hidden] { display: none !important; }
  @media (max-width: 600px) {
    main { padding: 12px; }
    .pair { grid-template-columns: 1fr; }
  }
`;

class BoligloggenPanel extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
    this._s = {
      tab: "plan",
      entryId: null,
      properties: [],
      tasks: [],
      archived: [],
      catalog: [],
      showAll: false,
      selected: new Set(),
      log: [],
      logNext: null,
      filter: "",
      loading: true,
      busy: false,
    };
    this._fp = null;
    this._narrow = false;
    this._editing = null;
  }

  // --- Home Assistant hooks -------------------------------------------------

  set hass(hass) {
    const first = !this._hass;
    this._hass = hass;
    if (first) {
      this._lang = this._pickLanguage();
      this._build();
      this._refresh();
    }
    // Refetch when any Boligloggen entity changes: completions, edits, the
    // daily status scan, tasks being added or removed – also from elsewhere.
    const fp = Object.values(hass.entities || {})
      .filter((e) => e.platform === DOMAIN)
      .map((e) => `${e.entity_id}@${hass.states[e.entity_id]?.last_updated ?? "-"}`)
      .sort()
      .join("|");
    if (fp !== this._fp) {
      const had = this._fp !== null;
      this._fp = fp;
      if (had) {
        clearTimeout(this._timer);
        this._timer = setTimeout(() => this._refresh(), 300);
      }
    }
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.hass = hass;
  }

  set narrow(narrow) {
    this._narrow = narrow;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) menu.narrow = narrow;
    const fallback = this.shadowRoot.querySelector(".menu");
    if (fallback) fallback.hidden = !narrow;
  }

  set panel(_panel) {}
  set route(_route) {}

  // --- helpers ---------------------------------------------------------------

  _pickLanguage() {
    const lang = (this._hass.locale?.language || this._hass.language || "en").toLowerCase();
    return /^(nb|no|nn)\b/.test(lang) ? "nb" : "en";
  }

  get _t() {
    return I18N[this._lang] || I18N.en;
  }

  _date(iso) {
    if (!iso) return "";
    const [y, m, d] = iso.slice(0, 10).split("-").map(Number);
    try {
      return new Intl.DateTimeFormat(this._hass.locale?.language || this._lang, {
        dateStyle: "medium",
        timeZone: "UTC",
      }).format(new Date(Date.UTC(y, m - 1, d)));
    } catch (_err) {
      return iso.slice(0, 10);
    }
  }

  _ws(msg) {
    return this._hass.callWS(msg);
  }

  /** A readable, translated message for a websocket/service error. */
  async _errorText(err) {
    if (err?.translation_key && err?.translation_domain) {
      const text = await this._exceptionText(
        err.translation_domain,
        err.translation_key,
        err.translation_placeholders,
      );
      if (text) return text;
    }
    return String(err?.message ?? err).replace(/^Validation error: /, "");
  }

  async _exceptionText(domain, key, placeholders) {
    const lang = this._hass.language || "en";
    const cacheKey = `${lang}:${domain}`;
    this._exceptions = this._exceptions || {};
    if (!this._exceptions[cacheKey]) {
      try {
        const result = await this._ws({
          type: "frontend/get_translations",
          language: lang,
          category: "exceptions",
          integration: [domain],
        });
        this._exceptions[cacheKey] = result.resources || {};
      } catch (_e) {
        this._exceptions[cacheKey] = {};
      }
    }
    const resources = this._exceptions[cacheKey];
    const base = `component.${domain}.exceptions.${key}`;
    // The resource shape has varied between HA versions: "<base>" → string,
    // "<base>.message" → string, or "<base>" → {message}.
    const entry = resources[base];
    const template = typeof entry === "string" ? entry : resources[`${base}.message`] ?? entry?.message;
    if (typeof template !== "string") return null;
    return template.replace(/\{(\w+)\}/g, (match, name) => placeholders?.[name] ?? match);
  }

  /** Call a Boligloggen service; throws Error(readable message) on failure. */
  async _call(service, data, returnResponse = false) {
    try {
      const result = await this._ws({
        type: "call_service",
        domain: DOMAIN,
        service,
        service_data: data,
        return_response: returnResponse,
      });
      return result?.response;
    } catch (err) {
      throw new Error(await this._errorText(err));
    }
  }

  _toast(message) {
    this.dispatchEvent(
      new CustomEvent("hass-notification", { bubbles: true, composed: true, detail: { message } }),
    );
  }

  _navigate(path) {
    history.pushState(null, "", path);
    window.dispatchEvent(new CustomEvent("location-changed", { detail: { replace: false } }));
  }

  _task(id) {
    return this._s.tasks.find((t) => t.id === id) || this._s.archived.find((t) => t.id === id);
  }

  // --- data ------------------------------------------------------------------

  async _refresh() {
    if (!this._hass.user?.is_admin) {
      this._s.loading = false;
      this._render();
      return;
    }
    try {
      const props = await this._ws({ type: `${DOMAIN}/properties` });
      this._s.properties = props;
      if (!props.some((p) => p.config_entry_id === this._s.entryId)) {
        let saved = null;
        try {
          saved = localStorage.getItem("boligloggen-panel-entry");
        } catch (_e) {
          /* storage unavailable */
        }
        this._s.entryId = (props.find((p) => p.config_entry_id === saved) || props[0])
          ?.config_entry_id ?? null;
      }
      if (this._s.entryId) {
        await Promise.all([this._loadTasks(), this._loadTabData()]);
      }
    } catch (err) {
      this._toast(await this._errorText(err));
    }
    this._s.loading = false;
    this._render();
  }

  async _loadTasks() {
    const all = await this._ws({
      type: `${DOMAIN}/tasks`,
      config_entry_id: this._s.entryId,
      include_archived: true,
    });
    const byCategory = (a, b) =>
      CATEGORIES.indexOf(a.category) - CATEGORIES.indexOf(b.category) ||
      a.next_due.localeCompare(b.next_due) ||
      a.title.localeCompare(b.title);
    this._s.tasks = all.filter((t) => t.status === "active").sort(byCategory);
    this._s.archived = all
      .filter((t) => t.status === "archived")
      .sort((a, b) => a.title.localeCompare(b.title));
  }

  async _loadTabData() {
    if (this._s.tab === "add") await this._loadCatalog();
    if (this._s.tab === "history") await this._loadLog(false);
  }

  async _loadCatalog() {
    this._s.catalog = await this._ws({
      type: `${DOMAIN}/catalog`,
      config_entry_id: this._s.entryId,
      show_all: this._s.showAll,
    });
    const keys = new Set(this._s.catalog.map((c) => c.key));
    this._s.selected = new Set([...this._s.selected].filter((k) => keys.has(k)));
  }

  async _loadLog(more) {
    const msg = { type: `${DOMAIN}/log`, config_entry_id: this._s.entryId, limit: LOG_PAGE };
    if (more && this._s.logNext) msg.before = this._s.logNext;
    const page = await this._ws(msg);
    this._s.log = more ? [...this._s.log, ...page.entries] : page.entries;
    this._s.logNext = page.next_before;
  }

  // --- rendering ---------------------------------------------------------------

  _build() {
    const t = this._t;
    this.shadowRoot.innerHTML = `
      <style>${STYLE}</style>
      <div class="toolbar">
        ${customElements.get("ha-menu-button")
          ? "<ha-menu-button></ha-menu-button>"
          : `<button class="menu" title="Menu" hidden>☰</button>`}
        <div class="title">Boligloggen</div>
        <select id="property" aria-label="${esc(t.property)}" hidden></select>
      </div>
      <nav class="tabs">
        ${Object.entries(t.tabs)
          .map(([id, label]) => `<button class="tab" data-tab="${id}">${esc(label)}</button>`)
          .join("")}
      </nav>
      <main id="main"><div class="empty">${esc(t.loading)}</div></main>
      <dialog id="dialog"></dialog>
      <dialog id="confirm"></dialog>
    `;
    const menu = this.shadowRoot.querySelector("ha-menu-button");
    if (menu) {
      menu.hass = this._hass;
      menu.narrow = this._narrow;
    }
    const fallback = this.shadowRoot.querySelector(".menu");
    if (fallback) {
      fallback.hidden = !this._narrow;
      fallback.addEventListener("click", () =>
        this.dispatchEvent(new Event("hass-toggle-menu", { bubbles: true, composed: true })),
      );
    }
    this.shadowRoot.querySelector(".tabs").addEventListener("click", (ev) => {
      const tab = ev.target.closest("[data-tab]")?.dataset.tab;
      if (tab && tab !== this._s.tab) this._switchTab(tab);
    });
    this.shadowRoot.getElementById("property").addEventListener("change", (ev) => {
      this._s.entryId = ev.target.value;
      this._s.selected.clear();
      this._s.log = [];
      try {
        localStorage.setItem("boligloggen-panel-entry", ev.target.value);
      } catch (_e) {
        /* storage unavailable */
      }
      this._s.loading = true;
      this._render();
      this._refresh();
    });
    const main = this.shadowRoot.getElementById("main");
    main.addEventListener("click", (ev) => this._onClick(ev));
    main.addEventListener("input", (ev) => this._onInput(ev));
    main.addEventListener("change", (ev) => this._onChange(ev));
  }

  async _switchTab(tab) {
    this._s.tab = tab;
    this._s.loading = true;
    this._render();
    try {
      await this._loadTabData();
    } catch (err) {
      this._toast(await this._errorText(err));
    }
    this._s.loading = false;
    this._render();
  }

  _render() {
    const root = this.shadowRoot;
    const t = this._t;
    root.querySelectorAll(".tab").forEach((el) =>
      el.classList.toggle("active", el.dataset.tab === this._s.tab),
    );
    const select = root.getElementById("property");
    select.hidden = this._s.properties.length < 2;
    select.innerHTML = this._s.properties
      .map(
        (p) =>
          `<option value="${esc(p.config_entry_id)}" ${
            p.config_entry_id === this._s.entryId ? "selected" : ""
          }>${esc(p.name)}</option>`,
      )
      .join("");

    const main = root.getElementById("main");
    const focused = root.activeElement?.id;
    let html;
    if (!this._hass.user?.is_admin) {
      html = `<div class="card empty">${esc(t.not_admin)}</div>`;
    } else if (this._s.loading) {
      html = `<div class="empty">${esc(t.loading)}</div>`;
    } else if (!this._s.entryId) {
      html = `<div class="card empty">${esc(t.no_properties)}<br><br>
        <button class="btn primary" data-action="add-property">${esc(t.add_property)}</button></div>`;
    } else {
      html = {
        plan: () => this._renderPlan(),
        add: () => this._renderAdd(),
        archived: () => this._renderArchived(),
        history: () => this._renderHistory(),
      }[this._s.tab]();
    }
    main.innerHTML = html;
    if (focused === "filter") {
      const input = root.getElementById("filter");
      input.focus();
      input.setSelectionRange(input.value.length, input.value.length);
    }
  }

  _renderPlan() {
    const t = this._t;
    return `
      <div class="bar">
        <input type="search" id="filter" placeholder="${esc(t.filter)}" value="${esc(this._s.filter)}">
        <button class="btn" data-action="profile">${esc(t.property_details)}</button>
      </div>
      <div id="plan-list">${this._renderPlanList()}</div>`;
  }

  _renderPlanList() {
    const t = this._t;
    if (!this._s.tasks.length) return `<div class="card empty">${esc(t.no_tasks)}</div>`;
    const needle = this._s.filter.trim().toLowerCase();
    const tasks = needle
      ? this._s.tasks.filter((task) =>
          `${task.title} ${task.description} ${t.category[task.category] || ""}`
            .toLowerCase()
            .includes(needle),
        )
      : this._s.tasks;
    if (!tasks.length) return `<div class="empty">${esc(t.no_match)}</div>`;
    let html = "";
    let current = null;
    for (const task of tasks) {
      if (task.category !== current) {
        current = task.category;
        const count = tasks.filter((x) => x.category === current).length;
        html += `<h3>${esc(t.category[current] || current)} · ${count}</h3>`;
      }
      const last = task.last_completed
        ? `${t.last_done}: ${this._date(task.last_completed)}${
            task.last_completed_by ? ` ${t.by} ${task.last_completed_by}` : ""
          }`
        : t.never_done;
      html += `
        <div class="row ${esc(task.due_status)}">
          <div class="main">
            <div class="t">${esc(task.title)}</div>
            <div class="sub">${esc(task.schedule_text)} · ${esc(t.next_due)}: ${esc(
              this._date(task.next_due),
            )} · ${esc(last)}</div>
          </div>
          ${task.due_status !== "ok"
            ? `<span class="chip ${esc(task.due_status)}">${esc(t.status[task.due_status])}</span>`
            : ""}
          <div class="actions">
            <button class="btn" data-action="edit" data-id="${esc(task.id)}">${esc(t.edit)}</button>
            ${task.last_completed_by
              ? `<button class="btn" data-action="undo" data-id="${esc(task.id)}">${esc(t.undo)}</button>`
              : ""}
            <button class="btn danger" data-action="archive" data-id="${esc(task.id)}">${esc(t.archive)}</button>
          </div>
        </div>`;
    }
    return html;
  }

  _renderAdd() {
    const t = this._t;
    let list = "";
    if (!this._s.catalog.length) {
      list = `<div class="empty">${esc(t.catalog_empty)}</div>`;
    } else {
      let current = null;
      for (const item of this._s.catalog) {
        if (item.category !== current) {
          current = item.category;
          list += `<h3>${esc(t.category[current] || current)}</h3>`;
        }
        list += `
          <label class="check">
            <input type="checkbox" data-key="${esc(item.key)}" ${
              this._s.selected.has(item.key) ? "checked" : ""
            }>
            <span>
              <span class="t">${esc(item.title)}</span>
              ${item.matches ? "" : `<span class="chip muted">${esc(t.not_matching)}</span>`}
              <div class="sub">${esc(item.schedule_text)}${
                item.description ? ` — ${esc(item.description)}` : ""
              }</div>
            </span>
          </label>`;
      }
    }
    const n = this._s.selected.size;
    return `
      <section class="card">
        <h2>${esc(t.catalog_title)}</h2>
        <div class="help">${esc(t.catalog_help)}</div>
        <label class="check"><input type="checkbox" id="show-all" ${
          this._s.showAll ? "checked" : ""
        }> ${esc(t.show_all)}</label>
        ${list}
        <div class="bar" style="margin: 12px 0 0">
          <button class="btn primary" data-action="add-selected" ${n && !this._s.busy ? "" : "disabled"}>
            ${esc(t.add_selected(n))}</button>
        </div>
      </section>
      <section class="card">
        <h2>${esc(t.custom_title)}</h2>
        <div class="help">${esc(t.custom_help)}</div>
        <div class="bar" style="margin: 12px 0 0">
          <button class="btn primary" data-action="new-custom">${esc(t.new_custom)}</button>
        </div>
      </section>`;
  }

  _renderArchived() {
    const t = this._t;
    if (!this._s.archived.length) return `<div class="card empty">${esc(t.no_archived)}</div>`;
    return this._s.archived
      .map(
        (task) => `
        <div class="row">
          <div class="main">
            <div class="t">${esc(task.title)}</div>
            <div class="sub">${esc(t.category[task.category] || task.category)} · ${esc(
              task.schedule_text,
            )}</div>
          </div>
          <div class="actions">
            <button class="btn" data-action="restore" data-id="${esc(task.id)}">${esc(t.restore)}</button>
          </div>
        </div>`,
      )
      .join("");
  }

  _renderHistory() {
    const t = this._t;
    if (!this._s.log.length) return `<div class="card empty">${esc(t.no_history)}</div>`;
    const rows = this._s.log
      .map(
        (e) => `
        <div class="d">${esc(this._date(e.completed_on))}</div>
        <div>
          <span class="t">${esc(e.title ?? t.removed_task)}</span>
          <span class="sub">${esc(t.by)} ${esc(e.user_name)}</span>
          ${e.forced ? `<span class="chip muted">${esc(t.forced)}</span>` : ""}
          ${e.note ? `<div class="note">${esc(e.note)}</div>` : ""}
        </div>`,
      )
      .join("");
    return `
      <section class="card"><div class="log">${rows}</div>
        ${this._s.logNext
          ? `<div class="bar" style="margin: 16px 0 0"><button class="btn" data-action="more-log">${esc(
              t.load_more,
            )}</button></div>`
          : ""}
      </section>`;
  }

  // --- events ------------------------------------------------------------------

  _onInput(ev) {
    if (ev.target.id === "filter") {
      this._s.filter = ev.target.value;
      const list = this.shadowRoot.getElementById("plan-list");
      if (list) list.innerHTML = this._renderPlanList();
    }
  }

  async _onChange(ev) {
    const el = ev.target;
    if (el.id === "show-all") {
      this._s.showAll = el.checked;
      await this._withBusy(() => this._loadCatalog());
    } else if (el.dataset.key) {
      if (el.checked) this._s.selected.add(el.dataset.key);
      else this._s.selected.delete(el.dataset.key);
      const btn = this.shadowRoot.querySelector('[data-action="add-selected"]');
      if (btn) {
        btn.textContent = this._t.add_selected(this._s.selected.size);
        btn.disabled = !this._s.selected.size;
      }
    }
  }

  async _onClick(ev) {
    const el = ev.target.closest("[data-action]");
    if (!el || el.disabled) return;
    const t = this._t;
    const id = el.dataset.id;
    const task = id ? this._task(id) : null;
    const entry = this._s.entryId;
    switch (el.dataset.action) {
      case "edit":
        this._openDialog(task);
        break;
      case "new-custom":
        this._openDialog(null);
        break;
      case "archive":
        if (!(await this._confirm(t.confirm_archive(task.title), t.archive, true))) return;
        await this._withBusy(async () => {
          await this._call("remove_task", { config_entry_id: entry, task_id: id });
          this._toast(t.archived_msg(task.title));
          await this._loadTasks();
        });
        break;
      case "restore":
        await this._withBusy(async () => {
          await this._call("restore_task", { config_entry_id: entry, task_id: id });
          this._toast(t.restored_msg(task.title));
          await this._loadTasks();
        });
        break;
      case "undo":
        if (!(await this._confirm(t.confirm_undo(task.title, task.last_completed_by), t.undo))) {
          return;
        }
        await this._withBusy(async () => {
          await this._call("undo_completion", { config_entry_id: entry, task_id: id });
          this._toast(t.undone_msg(task.title));
          await this._loadTasks();
        });
        break;
      case "add-selected": {
        const keys = [...this._s.selected];
        await this._withBusy(async () => {
          const resp = await this._call(
            "add_task",
            { config_entry_id: entry, template_id: keys },
            true,
          );
          this._s.selected.clear();
          this._toast(t.added(resp?.task_ids?.length ?? keys.length));
          await Promise.all([this._loadTasks(), this._loadCatalog()]);
        });
        break;
      }
      case "more-log":
        await this._withBusy(() => this._loadLog(true));
        break;
      case "profile":
        this._navigate(`/config/integrations/integration/${DOMAIN}`);
        break;
      case "add-property":
        this._navigate(`/config/integrations/dashboard/add?domain=${DOMAIN}`);
        break;
      default:
    }
  }

  /** In-panel confirmation (no blocking window.confirm). Resolves true on OK. */
  _confirm(message, okLabel, danger = false) {
    const dialog = this.shadowRoot.getElementById("confirm");
    dialog.innerHTML = `
      <form method="dialog">
        <div class="fields" style="padding-top: 24px">${esc(message)}</div>
        <footer>
          <button class="btn" value="cancel">${esc(this._t.cancel)}</button>
          <button class="btn ${danger ? "danger" : "primary"}" value="ok">${esc(okLabel)}</button>
        </footer>
      </form>`;
    return new Promise((resolve) => {
      dialog.addEventListener("close", () => resolve(dialog.returnValue === "ok"), { once: true });
      dialog.returnValue = "";
      dialog.showModal();
    });
  }

  async _withBusy(fn) {
    if (this._s.busy) return;
    this._s.busy = true;
    try {
      await fn();
    } catch (err) {
      this._toast(err instanceof Error ? err.message : await this._errorText(err));
    }
    this._s.busy = false;
    this._render();
  }

  // --- add / edit dialog ---------------------------------------------------------

  _openDialog(task) {
    const t = this._t;
    this._editing = task;
    const schedule = task?.schedule || { type: "interval", every: 1, unit: "years" };
    const interval = schedule.type === "interval";
    const dialog = this.shadowRoot.getElementById("dialog");
    const option = (value, label, selected) =>
      `<option value="${esc(value)}" ${selected ? "selected" : ""}>${esc(label)}</option>`;
    dialog.innerHTML = `
      <form method="dialog" novalidate>
        <header>${esc(task ? t.dialog_edit(task.title) : t.dialog_new)}</header>
        <div class="fields">
          <div class="error" hidden></div>
          <label class="field"><span>${esc(t.f_title)}</span>
            <input name="title" required value="${esc(task?.title)}"></label>
          <label class="field"><span>${esc(t.f_description)}</span>
            <textarea name="description" rows="3">${esc(task?.description)}</textarea></label>
          <label class="field"><span>${esc(t.f_category)}</span>
            <select name="category">${CATEGORIES.map((c) =>
              option(c, t.category[c], (task?.category || "indoor") === c),
            ).join("")}</select></label>
          <div class="field"><span>${esc(t.f_schedule_type)}</span>
            <div class="radios">
              <label><input type="radio" name="schedule_type" value="interval" ${
                interval ? "checked" : ""
              }> ${esc(t.f_interval)}</label>
              <label><input type="radio" name="schedule_type" value="fixed" ${
                interval ? "" : "checked"
              }> ${esc(t.f_fixed)}</label>
            </div></div>
          <div class="pair" data-when="interval">
            <label class="field"><span>${esc(t.f_every)}</span>
              <input name="every" type="number" min="1" max="50" step="1"
                value="${esc(interval ? schedule.every : 1)}"></label>
            <label class="field"><span>${esc(t.f_unit)}</span>
              <select name="unit">
                ${option("months", t.f_months, interval && schedule.unit === "months")}
                ${option("years", t.f_years, !interval || schedule.unit === "years")}
              </select></label>
          </div>
          <label class="field" data-when="fixed"><span>${esc(t.f_dates)}</span>
            <input name="dates" placeholder="04-15, 09-15" value="${esc(formatDates(schedule))}">
            <span class="help">${esc(t.f_dates_help)}</span></label>
          <label class="field"><span>${esc(t.f_due_soon)}</span>
            <input name="due_soon_days" type="number" min="0" max="3650" step="1"
              value="${esc(task?.due_soon_days ?? "")}">
            <span class="help">${esc(t.f_due_soon_help)}</span></label>
          ${task
            ? `<div class="pair">
                <label class="field"><span>${esc(t.f_last)}</span>
                  <input name="last_completed" type="date" value="${esc(task.last_completed ?? "")}">
                  <span class="help">${esc(t.f_last_help)}</span></label>
                <label class="field"><span>${esc(t.f_next)}</span>
                  <input name="next_due" type="date" value="${esc(task.next_due)}"></label>
              </div>`
            : ""}
        </div>
        <footer>
          <button class="btn" value="cancel" type="button" data-close>${esc(t.cancel)}</button>
          <button class="btn primary" type="submit">${esc(task ? t.save : t.create)}</button>
        </footer>
      </form>`;
    const form = dialog.querySelector("form");
    const toggle = () => {
      const type = form.elements.schedule_type.value;
      form.querySelectorAll("[data-when]").forEach((el) => {
        el.hidden = el.dataset.when !== type;
      });
    };
    form.querySelectorAll('input[name="schedule_type"]').forEach((r) =>
      r.addEventListener("change", toggle),
    );
    toggle();
    form.querySelector("[data-close]").addEventListener("click", () => dialog.close());
    form.addEventListener("submit", (ev) => {
      ev.preventDefault();
      this._submitDialog(form);
    });
    dialog.showModal();
    form.elements.title.focus();
  }

  _formData(form) {
    const f = form.elements;
    const type = f.schedule_type.value;
    const data = {
      title: f.title.value.trim(),
      description: f.description.value,
      category: f.category.value,
      schedule_type: type,
    };
    if (type === "interval") {
      data.every = Number(f.every.value);
      data.unit = f.unit.value;
    } else {
      data.dates = f.dates.value;
    }
    if (f.due_soon_days.value !== "") data.due_soon_days = Number(f.due_soon_days.value);
    if (f.last_completed) data.last_completed = f.last_completed.value;
    if (f.next_due) data.next_due = f.next_due.value;
    return data;
  }

  /** Only the fields that differ from the task, like the options flow does. */
  _changes(task, data) {
    const changes = {};
    for (const key of ["title", "description", "category"]) {
      if (data[key] !== (task[key] ?? "")) changes[key] = data[key];
    }
    const s = task.schedule;
    const scheduleChanged =
      data.schedule_type !== s.type ||
      (s.type === "interval"
        ? data.every !== s.every || data.unit !== s.unit
        : data.dates.replace(/\s+/g, "") !== formatDates(s).replace(/\s+/g, ""));
    if (scheduleChanged) {
      for (const key of ["schedule_type", "every", "unit", "dates"]) {
        if (key in data) changes[key] = data[key];
      }
    }
    if ("due_soon_days" in data && data.due_soon_days !== task.due_soon_days) {
      changes.due_soon_days = data.due_soon_days;
    }
    if (data.last_completed && data.last_completed !== (task.last_completed ?? "")) {
      changes.last_completed = data.last_completed;
    }
    if (data.next_due && data.next_due !== task.next_due) changes.next_due = data.next_due;
    return changes;
  }

  async _submitDialog(form) {
    const dialog = this.shadowRoot.getElementById("dialog");
    const errorBox = form.querySelector(".error");
    const submit = form.querySelector('button[type="submit"]');
    const task = this._editing;
    const data = this._formData(form);
    errorBox.hidden = true;
    submit.disabled = true;
    try {
      if (task) {
        const changes = this._changes(task, data);
        if (Object.keys(changes).length) {
          await this._call("update_task", {
            config_entry_id: this._s.entryId,
            task_id: task.id,
            ...changes,
          });
          this._toast(this._t.saved);
        }
      } else {
        delete data.last_completed;
        delete data.next_due;
        await this._call("add_task", { config_entry_id: this._s.entryId, ...data }, true);
        this._toast(this._t.added(1));
      }
      dialog.close();
      await this._loadTasks();
      if (this._s.tab === "add") await this._loadCatalog();
      this._render();
    } catch (err) {
      errorBox.textContent = err.message;
      errorBox.hidden = false;
    } finally {
      submit.disabled = false;
    }
  }
}

if (!customElements.get("boligloggen-panel")) {
  customElements.define("boligloggen-panel", BoligloggenPanel);
}
