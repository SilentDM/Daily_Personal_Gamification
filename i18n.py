"""App language (Português do Brasil / English) for the whole program: screens, wallpaper, notifications,
the Telegram assistant and what the AI writes.

The code is written in English; `tr("English text")` returns the Portuguese version from i18n_pt.PT when the
app is in Portuguese (falling back to the English text if a translation is missing). Data stored in the
database (habit answers, categories, stages…) stays in English: it is translated only when shown, so
switching languages never touches your data. The language is read once at start-up (changing it restarts).
"""
import locale

LANGUAGES = {"pt": "Português (Brasil)", "en": "English"}
SETTING = "language"
OLD_SETTING = "ai_language"          # the former "AI & messages language" (full names)
_OLD_NAMES = {"Português (Brasil)": "pt", "English": "en"}

_current = None


def _system_default() -> str:
    try:
        name = locale.getlocale()[0] or locale.getdefaultlocale()[0] or ""
    except Exception:
        name = ""
    return "pt" if name.lower().startswith(("pt", "portuguese")) else "en"


def stored_language() -> str:
    """What the settings say (or the old AI-language setting, or the system language)."""
    try:
        import database as db
        stored = db.get_hud_settings()
    except Exception:
        return _system_default()
    code = stored.get(SETTING)
    if code in LANGUAGES:
        return code
    old = stored.get(OLD_SETTING) or stored.get("insight_language")
    if old in _OLD_NAMES:
        return _OLD_NAMES[old]
    return _system_default()


def language() -> str:
    """'pt' or 'en' — fixed for this run of the app (read on first use)."""
    global _current
    if _current is None:
        _current = stored_language()
    return _current


def set_language(code: str, save: bool = False):
    """Switches the running language (tests) and/or saves the choice for the next start."""
    global _current
    if code not in LANGUAGES:
        raise ValueError(code)
    _current = code
    if save:
        import database as db
        db.set_hud_setting(SETTING, code)


def save_language(code: str):
    """Saves the choice without switching the running app (it applies after a restart)."""
    if code not in LANGUAGES:
        raise ValueError(code)
    import database as db
    db.set_hud_setting(SETTING, code)


def ai_language_name() -> str:
    """How the AI prompts name the language to write in."""
    return "Brazilian Portuguese" if language() == "pt" else "English"


def tr(text: str, /, **kw) -> str:  # "/": a {text} placeholder is fine too
    """Translated text; `{name}` placeholders are filled from kw (in both languages)."""
    if language() == "pt":
        from i18n_pt import PT
        text = PT.get(text, text)
    return text.format(**kw) if kw else text


def trn(one: str, many: str, n, /, **kw) -> str:
    """Singular/plural: trn("{n} day", "{n} days", n)."""
    return tr(one if n == 1 else many, n=n, **kw)


# ------------------------------------------------------------------ dates
_DAYS = {"en": ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday", "Saturday", "Sunday"],
         "pt": ["Segunda-feira", "Terça-feira", "Quarta-feira", "Quinta-feira", "Sexta-feira", "Sábado", "Domingo"]}
_DAYS_SHORT = {"en": ["Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun"],
               "pt": ["Seg", "Ter", "Qua", "Qui", "Sex", "Sáb", "Dom"]}
_MONTHS = {"en": ["January", "February", "March", "April", "May", "June", "July", "August", "September",
                  "October", "November", "December"],
           "pt": ["janeiro", "fevereiro", "março", "abril", "maio", "junho", "julho", "agosto", "setembro",
                  "outubro", "novembro", "dezembro"]}


def day_name(weekday: int) -> str:
    return _DAYS[language()][weekday]


def day_short(weekday: int) -> str:
    return _DAYS_SHORT[language()][weekday]


def day_names_short() -> list:
    return list(_DAYS_SHORT[language()])


def month_name(month: int) -> str:
    return _MONTHS[language()][month - 1]


def month_short(month: int) -> str:
    return month_name(month)[:3].capitalize() if language() == "pt" else month_name(month)[:3]


def fmt_long(d) -> str:
    """'Monday, 12 October 2026' / 'Segunda-feira, 12 de outubro de 2026'."""
    if language() == "pt":
        return f"{day_name(d.weekday())}, {d.day} de {month_name(d.month)} de {d.year}"
    return f"{day_name(d.weekday())}, {d.day} {month_name(d.month)} {d.year}"


def fmt_month_year(d) -> str:
    """'October 2026' / 'Outubro de 2026'."""
    if language() == "pt":
        return f"{month_name(d.month).capitalize()} de {d.year}"
    return f"{month_name(d.month)} {d.year}"


def fmt_short(d, year: bool = True) -> str:
    """'Mon 12/10/2026' / 'Seg 12/10/2026'."""
    return f"{day_short(d.weekday())} {d:%d/%m}" + (f"/{d.year}" if year else "")
