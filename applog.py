"""File logging in AppData (silent failures are invisible under pythonw)."""
import logging
import sys
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

_configured = False


def setup_logging() -> logging.Logger:
    global _configured
    log = logging.getLogger("gamification")
    if _configured:
        return log

    import database  # lazy import
    path = Path(database.get_db_path()).parent / "app.log"
    handler = RotatingFileHandler(path, maxBytes=512_000, backupCount=3, encoding="utf-8")
    handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(message)s"))
    log.setLevel(logging.INFO)
    log.addHandler(handler)

    sys.excepthook = lambda t, v, tb: log.error("Unhandled exception", exc_info=(t, v, tb))
    threading.excepthook = lambda a: log.error(
        "Thread error in %s", getattr(a.thread, "name", "?"),
        exc_info=(a.exc_type, a.exc_value, a.exc_traceback),
    )
    _configured = True
    return log
