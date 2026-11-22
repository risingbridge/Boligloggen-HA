"""Human-readable schedule descriptions (nb/en)."""

from __future__ import annotations

from .models import Schedule

_MONTHS = {
    "nb": ["jan", "feb", "mar", "apr", "mai", "jun", "jul", "aug", "sep", "okt", "nov", "des"],
    "en": ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec"],
}


def describe_schedule(schedule: Schedule, lang: str = "nb") -> str:
    lang = lang if lang in _MONTHS else "en"
    if schedule.type == "fixed":
        months = _MONTHS[lang]
        if lang == "nb":
            parts = [f"{d.day}. {months[d.month - 1]}" for d in schedule.dates]
            return "Årlig " + ", ".join(parts)
        parts = [f"{months[d.month - 1]} {d.day}" for d in schedule.dates]
        return "Yearly on " + ", ".join(parts)

    n, unit = schedule.every, schedule.unit
    if lang == "nb":
        if unit == "months":
            return {1: "Hver måned", 3: "Hvert kvartal", 6: "Hvert halvår"}.get(
                n, f"Hver {n}. måned"
            )
        return "Hvert år" if n == 1 else f"Hvert {n}. år"
    if unit == "months":
        return {1: "Monthly", 3: "Quarterly", 6: "Every 6 months"}.get(n, f"Every {n} months")
    return "Yearly" if n == 1 else f"Every {n} years"
