"""Generate strings.json, translations/en.json and translations/nb.json.

Single source of truth for UI text: every leaf is an ``(en, nb)`` tuple.
Run from the repository root:  python script/gen_translations.py
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1] / "custom_components" / "boligloggen"

T = tuple[str, str]


def opts(**pairs: T) -> dict[str, Any]:
    return {"options": dict(pairs)}


# --- shared step definitions (config + options flow) --------------------------

BASIC_DATA = {
    "name": ("Name", "Navn"),
    "address": ("Address", "Adresse"),
    "type": ("Property type", "Boligtype"),
    "build_year": ("Year built", "Byggeår"),
    "age_band": ("Age (if you don't know the year)", "Alder (hvis du ikke vet byggeåret)"),
}
BASIC_DESC = {
    "name": (
        "Shown as the device name, e.g. “Home” or “Cabin”.",
        "Vises som enhetsnavn, f.eks. «Hjemme» eller «Hytta».",
    ),
    "address": ("Free text, optional.", "Fritekst, valgfritt."),
    "build_year": (
        "Leave empty and choose an age band if unsure.",
        "La stå tomt og velg aldersbånd hvis du er usikker.",
    ),
}
BUILDING = {
    "title": ("The building", "Bygningen"),
    "description": (
        "These answers decide heating, ventilation, wet-room and exterior tasks.",
        "Svarene avgjør oppgaver for oppvarming, ventilasjon, våtrom og fasade.",
    ),
    "data": {
        "heating": ("Heating (choose all that apply)", "Oppvarming (velg alle som passer)"),
        "ventilation": ("Ventilation", "Ventilasjon"),
        "cladding": ("Exterior cladding", "Utvendig kledning"),
        "bathroom_count": ("Bathrooms / wet rooms", "Antall bad/våtrom"),
    },
    "data_description": {
        "ventilation": (
            "“Don't know” is set from the building's age.",
            "«Vet ikke» settes ut fra byggeåret.",
        ),
    },
}
OUTDOOR = {
    "title": ("Outdoor area", "Uteområde"),
    "description": (
        "Answer each item – choose “No/None” for what you don't have.",
        "Svar på hvert punkt – velg «Nei/Ingen» for det du ikke har.",
    ),
    "data": {
        "garden": ("Own garden/lawn?", "Egen hage/plen?"),
        "driveway": ("Own driveway?", "Egen oppkjørsel?"),
        "deck": ("Deck/patio?", "Terrasse/platting?"),
        "garage": ("Garage/carport?", "Garasje/carport?"),
        "water": ("Water supply", "Vannforsyning"),
    },
}
CABIN = {
    "title": ("The cabin", "Hytta"),
    "description": ("A few cabin-specific questions.", "Noen spørsmål som gjelder hytta."),
    "data": {
        "cabin_winter_use": ("Winter use", "Vinterbruk"),
        "cabin_water": ("Water at the cabin", "Vann på hytta"),
    },
}
TASK_DATA = {
    "title": ("Title", "Tittel"),
    "description": ("Description", "Beskrivelse"),
    "category": ("Category", "Kategori"),
    "schedule_type": ("Schedule type", "Type plan"),
    "every": ("Every", "Hver"),
    "unit": ("Unit", "Enhet"),
    "dates": ("Fixed dates", "Faste datoer"),
    "due_soon_days": ("Days of warning (due soon)", "Dager varsel (snart aktuell)"),
    "last_completed": ("Last done", "Sist utført"),
    "next_due": ("Next due", "Neste frist"),
}
TASK_DESC = {
    "schedule_type": (
        "Fixed = tied to the calendar/season. Interval = counted from when it was last done.",
        "Fast = knyttet til kalender/sesong. Intervall = regnes fra sist utført.",
    ),
    "dates": (
        "For fixed schedules: comma-separated, as MM-DD (12-01) or D.M (1.12).",
        "For faste datoer: kommaseparert, som MM-DD (12-01) eller D.M (1.12).",
    ),
    "due_soon_days": ("Leave empty for the default.", "La stå tomt for standardverdi."),
    "last_completed": (
        "Changing this recomputes the next due date.",
        "Endring her beregner neste frist på nytt.",
    ),
}

SCHEDULE_ERRORS = {
    "title_required": ("Enter a title.", "Skriv inn en tittel."),
    "invalid_date": (
        "Invalid date. Use MM-DD or D.M, e.g. 12-01 or 1.12.",
        "Ugyldig dato. Bruk MM-DD eller D.M, f.eks. 12-01 eller 1.12.",
    ),
    "invalid_interval": ("Enter a valid interval.", "Skriv inn et gyldig intervall."),
    "completed_on_in_future": (
        "The date can't be in the future.",
        "Datoen kan ikke være fram i tid.",
    ),
    "age_required": (
        "Enter the year built or choose an age band.",
        "Fyll inn byggeår eller velg et aldersbånd.",
    ),
    "name_required": ("Enter a name.", "Skriv inn et navn."),
}

SOURCE: dict[str, Any] = {
    "config": {
        "step": {
            "user": {
                "title": ("New property", "Ny bolig"),
                "description": (
                    "Answer a few questions and Boligloggen suggests a maintenance plan. You can adjust everything afterwards.",
                    "Svar på noen spørsmål, så foreslår Boligloggen en vedlikeholdsplan. Alt kan justeres etterpå.",
                ),
                "data": BASIC_DATA,
                "data_description": BASIC_DESC,
            },
            "building": BUILDING,
            "outdoor": OUTDOOR,
            "cabin": CABIN,
            "review": {
                "title": ("Your plan", "Din plan"),
                "description": (
                    "{count} tasks suggested for {name}. Untick the ones that don't apply.",
                    "{count} gjøremål foreslått for {name}. Fjern haken for dem som ikke passer.",
                ),
                "data": {"tasks": ("Tasks", "Gjøremål")},
            },
        },
        "error": SCHEDULE_ERRORS,
    },
    "options": {
        "step": {
            "init": {
                "title": ("Edit plan", "Endre plan"),
                "menu_options": {
                    "add_catalog": ("Add from catalog", "Legg til fra katalog"),
                    "add_custom": ("Add custom task", "Legg til egendefinert"),
                    "edit_task": ("Edit task", "Endre gjøremål"),
                    "remove_task": ("Remove task", "Fjern gjøremål"),
                    "restore_task": ("Restore archived task", "Gjenopprett gjøremål"),
                    "profile": ("Edit property details", "Endre boligdetaljer"),
                },
            },
            "add_catalog": {
                "title": ("Add from catalog", "Legg til fra katalog"),
                "description": (
                    "{count} catalog tasks are available. Tick “show all” and submit without choosing to list tasks that don't match your property too.",
                    "{count} katalogoppgaver er tilgjengelige. Kryss av for «vis alle» og send uten å velge for å se også oppgaver som ikke passer boligen.",
                ),
                "data": {
                    "templates": ("Tasks", "Gjøremål"),
                    "show_all": ("Show all catalog tasks", "Vis alle katalogoppgaver"),
                },
            },
            "add_custom": {
                "title": ("Add custom task", "Legg til egendefinert gjøremål"),
                "data": {
                    k: v for k, v in TASK_DATA.items() if k not in ("last_completed", "next_due")
                },
                "data_description": {k: v for k, v in TASK_DESC.items() if k != "last_completed"},
            },
            "edit_task": {
                "title": ("Edit task", "Endre gjøremål"),
                "data": {"task_id": ("Task", "Gjøremål")},
            },
            "edit_task_fields": {
                "title": ("Edit “{title}”", "Endre «{title}»"),
                "data": TASK_DATA,
                "data_description": TASK_DESC,
            },
            "remove_task": {
                "title": ("Remove tasks", "Fjern gjøremål"),
                "description": (
                    "Removed tasks are archived – their history is kept and they can be restored.",
                    "Fjernede gjøremål arkiveres – historikken beholdes og de kan gjenopprettes.",
                ),
                "data": {"task_ids": ("Tasks", "Gjøremål")},
            },
            "restore_task": {
                "title": ("Restore tasks", "Gjenopprett gjøremål"),
                "data": {"task_ids": ("Tasks", "Gjøremål")},
            },
            "profile": {
                "title": ("Property details", "Boligdetaljer"),
                "data": BASIC_DATA,
                "data_description": BASIC_DESC,
            },
            "building": BUILDING,
            "outdoor": OUTDOOR,
            "cabin": CABIN,
            "profile_review": {
                "title": ("Suggested changes", "Foreslåtte endringer"),
                "description": (
                    "Based on the new details: {add_count} tasks to add and {remove_count} catalog tasks that no longer fit. Custom tasks are never removed automatically.",
                    "Ut fra de nye detaljene: {add_count} gjøremål å legge til og {remove_count} katalogoppgaver som ikke lenger passer. Egendefinerte gjøremål fjernes aldri automatisk.",
                ),
                "data": {
                    "add": ("Add", "Legg til"),
                    "remove": ("Remove (archive)", "Fjern (arkiver)"),
                },
            },
        },
        "error": SCHEDULE_ERRORS,
        "abort": {
            "no_tasks": ("There are no active tasks.", "Det finnes ingen aktive gjøremål."),
            "no_archived": ("There are no archived tasks.", "Det finnes ingen arkiverte gjøremål."),
        },
    },
    "selector": {
        "property_type": opts(
            house=("House", "Enebolig"),
            townhouse=("Townhouse / semi-detached", "Rekkehus/tomannsbolig"),
            apartment=("Apartment", "Leilighet"),
            cabin=("Cabin", "Hytte"),
        ),
        "age_band": opts(
            lt10=("Under 10 years", "Under 10 år"),
            **{"10to30": ("10–30 years", "10–30 år"), "30to50": ("30–50 years", "30–50 år")},
            gt50=("Over 50 years", "Over 50 år"),
        ),
        "heating": opts(
            wood_stove=("Wood stove/fireplace with chimney", "Vedovn/peis med pipe"),
            heat_pump=("Heat pump", "Varmepumpe"),
            hydronic=("Hydronic (radiators/underfloor)", "Vannbåren (radiator/gulvvarme)"),
            electric=("Electric", "Elektrisk"),
            district=("District heating", "Fjernvarme"),
        ),
        "ventilation": opts(
            balanced=("Balanced with heat recovery", "Balansert med varmegjenvinning"),
            exhaust=("Mechanical exhaust", "Mekanisk avtrekk"),
            natural=("Natural", "Naturlig"),
            unknown=("Don't know", "Vet ikke"),
        ),
        "cladding": opts(
            wood=("Wood (painted/stained)", "Tre (malt/beiset)"),
            render=("Masonry/render", "Mur/puss"),
            brick=("Brick", "Tegl"),
            mixed=("Combination", "Kombinasjon"),
        ),
        "bathroom_count": opts(
            **{"1": ("1", "1"), "2": ("2", "2"), "3": ("3 or more", "3 eller flere")}
        ),
        "yes_no": opts(no=("No", "Nei"), yes=("Yes", "Ja")),
        "driveway": opts(
            none=("No", "Nei"),
            asphalt=("Asphalt", "Asfalt"),
            pavers=("Paving stones", "Belegningsstein"),
            gravel=("Gravel", "Grus"),
            concrete=("Concrete", "Betong"),
        ),
        "deck": opts(
            none=("No", "Nei"),
            wood=("Wood", "Tre"),
            composite_or_stone=("Composite/stone", "Kompositt/stein"),
        ),
        "garage": opts(
            none=("No", "Nei"),
            garage_with_door=("Garage with door", "Garasje med port"),
            carport=("Carport", "Carport"),
        ),
        "water": opts(
            public=("Public", "Offentlig"), own_well=("Own well/borehole", "Egen brønn/borehull")
        ),
        "cabin_winter_use": opts(
            closed=("Closed/unheated in winter", "Vinterstengt/uoppvarmet"),
            year_round=("Year-round", "Helårs"),
        ),
        "cabin_water": opts(
            year_round=("Running water all year", "Innlagt helår"),
            summer=("Summer water", "Sommervann"),
            none=("No running water", "Ikke innlagt"),
        ),
        "category": opts(
            safety=("Safety", "Sikkerhet"),
            indoor=("Indoor", "Innendørs"),
            wet_room=("Wet room", "Våtrom"),
            heating=("Heating", "Oppvarming"),
            ventilation=("Ventilation", "Ventilasjon"),
            exterior=("Exterior", "Utvendig"),
            outdoor=("Outdoor", "Uteområde"),
            cabin=("Cabin", "Hytte"),
            seasonal=("Seasonal", "Sesong"),
        ),
        "schedule_type": opts(
            interval=("Interval (from last done)", "Intervall (fra sist utført)"),
            fixed=("Fixed dates", "Faste datoer"),
        ),
        "unit": opts(months=("Months", "Måneder"), years=("Years", "År")),
    },
    "entity": {
        "sensor": {
            "next_task": {"name": ("Next task", "Neste gjøremål")},
            "overdue": {"name": ("Overdue", "Forfalt")},
            "due_soon": {"name": ("Due soon", "Snart aktuelt")},
            "last_completed": {"name": ("Last completed", "Sist utført")},
        },
        "calendar": {"plan": {"name": ("Maintenance plan", "Vedlikeholdsplan")}},
    },
    "exceptions": {
        "task_not_found": ("Task {task_id} was not found.", "Fant ikke gjøremålet {task_id}."),
        "task_archived": ("“{title}” is archived.", "«{title}» er arkivert."),
        "not_due_yet": (
            "“{title}” is not due until {date}. Use force to complete it anyway.",
            "«{title}» er ikke aktuell før {date}. Bruk «force» for å fullføre likevel.",
        ),
        "completed_on_in_future": (
            "The date can't be in the future.",
            "Datoen kan ikke være fram i tid.",
        ),
        "nothing_to_undo": (
            "“{title}” has no completion to undo.",
            "«{title}» har ingen fullføring å angre.",
        ),
        "unknown_template": (
            "Unknown catalog task: {template_id}.",
            "Ukjent katalogoppgave: {template_id}.",
        ),
        "title_required": ("A title is required.", "Tittel må fylles ut."),
        "property_not_found": (
            "Property {config_entry_id} was not found or is not loaded.",
            "Fant ikke boligen {config_entry_id}, eller den er ikke lastet.",
        ),
        "not_a_task_entity": (
            "{entity_id} is not a Boligloggen task entity.",
            "{entity_id} er ikke en Boligloggen-gjøremålsentitet.",
        ),
        "task_target_required": (
            "Give entity_id, or config_entry_id and task_id.",
            "Oppgi entity_id, eller config_entry_id og task_id.",
        ),
        "schedule_required": (
            "schedule_type is required for custom tasks.",
            "schedule_type må oppgis for egendefinerte gjøremål.",
        ),
        "invalid_date": ("Invalid date: {value}.", "Ugyldig dato: {value}."),
        "invalid_interval": ("Invalid interval: {value}.", "Ugyldig intervall: {value}."),
    },
}

_TARGET_FIELDS = {
    "entity_id": (
        "Task entity",
        "Gjøremålsentitet",
        "Task sensor or button.",
        "Gjøremålets sensor eller knapp.",
    ),
    "config_entry_id": (
        "Property",
        "Bolig",
        "Config entry ID of the property.",
        "Konfigurasjons-ID for boligen.",
    ),
    "task_id": (
        "Task ID",
        "Gjøremåls-ID",
        "Use with config_entry_id instead of entity_id.",
        "Brukes sammen med config_entry_id i stedet for entity_id.",
    ),
}
_TASK_FIELDS = {
    "title": ("Title", "Tittel", "", ""),
    "description": ("Description", "Beskrivelse", "", ""),
    "category": ("Category", "Kategori", "", ""),
    "schedule_type": (
        "Schedule type",
        "Type plan",
        "fixed or interval.",
        "fixed (fast) eller interval.",
    ),
    "every": ("Every", "Hver", "Interval length.", "Intervallets lengde."),
    "unit": ("Unit", "Enhet", "months or years.", "months (måneder) eller years (år)."),
    "dates": (
        "Dates",
        "Datoer",
        "Fixed dates as MM-DD, e.g. 04-01, 10-01.",
        "Faste datoer som MM-DD, f.eks. 04-01, 10-01.",
    ),
    "due_soon_days": ("Due-soon days", "Dager varsel", "", ""),
}


def _fields(spec: dict[str, tuple[str, str, str, str]]) -> dict[str, Any]:
    return {
        k: {"name": (en, nb), "description": (den or en, dnb or nb)}
        for k, (en, nb, den, dnb) in spec.items()
    }


SOURCE["services"] = {
    "complete_task": {
        "name": ("Complete task", "Fullfør gjøremål"),
        "description": (
            "Mark a task as done and log who did it.",
            "Merk et gjøremål som utført og logg hvem som gjorde det.",
        ),
        "fields": _fields(
            {
                **_TARGET_FIELDS,
                "note": (
                    "Note",
                    "Notat",
                    "Optional note for the log.",
                    "Valgfritt notat i loggen.",
                ),
                "completed_on": (
                    "Completed on",
                    "Utført dato",
                    "Defaults to today.",
                    "Standard er i dag.",
                ),
                "force": (
                    "Force",
                    "Tving",
                    "Complete a fixed-date task before it is due.",
                    "Fullfør et gjøremål med fast dato før det er aktuelt.",
                ),
            }
        ),
    },
    "undo_completion": {
        "name": ("Undo completion", "Angre fullføring"),
        "description": (
            "Remove the task's latest log entry and restore its dates.",
            "Fjern siste loggføring og gjenopprett datoene.",
        ),
        "fields": _fields(_TARGET_FIELDS),
    },
    "add_task": {
        "name": ("Add task", "Legg til gjøremål"),
        "description": (
            "Add a catalog task (template_id) or a custom task. Admin only.",
            "Legg til en katalogoppgave (template_id) eller et egendefinert gjøremål. Kun admin.",
        ),
        "fields": _fields(
            {
                "config_entry_id": _TARGET_FIELDS["config_entry_id"],
                "template_id": (
                    "Catalog task",
                    "Katalogoppgave",
                    "Template id, e.g. heat_pump_filter.",
                    "Mal-ID, f.eks. heat_pump_filter.",
                ),
                **_TASK_FIELDS,
            }
        ),
    },
    "update_task": {
        "name": ("Update task", "Endre gjøremål"),
        "description": ("Edit a task. Admin only.", "Endre et gjøremål. Kun admin."),
        "fields": _fields(
            {
                **_TARGET_FIELDS,
                **_TASK_FIELDS,
                "last_completed": (
                    "Last done",
                    "Sist utført",
                    "Recomputes the next due date.",
                    "Beregner neste frist på nytt.",
                ),
                "next_due": (
                    "Next due",
                    "Neste frist",
                    "Set the next due date directly.",
                    "Sett neste frist direkte.",
                ),
            }
        ),
    },
    "remove_task": {
        "name": ("Remove task", "Fjern gjøremål"),
        "description": (
            "Archive a task (history is kept). Admin only.",
            "Arkiver et gjøremål (historikken beholdes). Kun admin.",
        ),
        "fields": _fields(_TARGET_FIELDS),
    },
    "restore_task": {
        "name": ("Restore task", "Gjenopprett gjøremål"),
        "description": (
            "Restore an archived task. Admin only.",
            "Gjenopprett et arkivert gjøremål. Kun admin.",
        ),
        "fields": _fields({k: _TARGET_FIELDS[k] for k in ("config_entry_id", "task_id")}),
    },
}


def pick(node: Any, index: int) -> Any:
    if isinstance(node, tuple):
        return node[index]
    if isinstance(node, dict):
        return {k: pick(v, index) for k, v in node.items()}
    raise TypeError(f"Unexpected node {node!r}")


def main() -> None:
    en, nb = pick(SOURCE, 0), pick(SOURCE, 1)
    dump = lambda d: json.dumps(d, ensure_ascii=False, indent=2) + "\n"  # noqa: E731
    (ROOT / "strings.json").write_text(dump(en), encoding="utf-8")
    (ROOT / "translations").mkdir(exist_ok=True)
    (ROOT / "translations" / "en.json").write_text(dump(en), encoding="utf-8")
    (ROOT / "translations" / "nb.json").write_text(dump(nb), encoding="utf-8")
    print("Wrote strings.json, translations/en.json, translations/nb.json")


if __name__ == "__main__":
    main()
