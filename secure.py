"""Field-level encryption for the personal documents vault (Fernet / AES).

- Encrypted values are stored as  "enc:<token>"; plain text is still readable, so
  old rows keep working and are encrypted by the migration in database.init_db().
- The key lives in the Windows Credential Manager (via `keyring`). If keyring is
  unavailable a key file (documents.key) is created next to the database.
- If `cryptography` is not installed everything degrades to plain text (with a log
  warning) instead of breaking the app.

!! Losing the key means losing the encrypted fields. Save a copy of it:
       python secure.py show-key      -> store the output in your password manager
       python secure.py set-key <key> -> restore it on a new machine
"""
import logging
import sys
from pathlib import Path

PREFIX = "enc:"
SERVICE = "DailyPersonalGamification"
ACCOUNT = "documents-key"

log = logging.getLogger("gamification")

try:
    from cryptography.fernet import Fernet
    AVAILABLE = True
except Exception:  # package not installed
    Fernet = None
    AVAILABLE = False

_fernet = None


def _key_file() -> Path:
    import database  # lazy: avoids a circular import
    return Path(database.get_db_path()).parent / "documents.key"


def _load_key() -> bytes:
    try:
        import keyring
        stored = keyring.get_password(SERVICE, ACCOUNT)
        if stored:
            return stored.encode()
        if not _key_file().exists():
            key = Fernet.generate_key()
            keyring.set_password(SERVICE, ACCOUNT, key.decode())
            return key
    except Exception:
        pass  # keyring missing or broken -> key file fallback

    path = _key_file()
    if path.exists():
        return path.read_bytes().strip()
    key = Fernet.generate_key()
    path.write_bytes(key)
    return key


def _get():
    global _fernet
    if _fernet is None:
        _fernet = Fernet(_load_key())
    return _fernet


def _reset():
    """For tests."""
    global _fernet
    _fernet = None


def encrypt(text):
    if not text or text.startswith(PREFIX):
        return text
    if not AVAILABLE:
        log.warning("cryptography not installed: storing document field as plain text")
        return text
    return PREFIX + _get().encrypt(text.encode("utf-8")).decode("ascii")


def decrypt(text):
    if not text or not text.startswith(PREFIX):
        return text
    if not AVAILABLE:
        return text
    try:
        return _get().decrypt(text[len(PREFIX):].encode("ascii")).decode("utf-8")
    except Exception:
        # Wrong/missing key: return the ciphertext untouched so that re-saving
        # the record can never destroy the data.
        log.error("Could not decrypt a document field (wrong key?)")
        return text


if __name__ == "__main__":
    if len(sys.argv) >= 2 and sys.argv[1] == "show-key":
        print(_load_key().decode())
    elif len(sys.argv) == 3 and sys.argv[1] == "set-key":
        try:
            import keyring
            keyring.set_password(SERVICE, ACCOUNT, sys.argv[2])
            print("Key stored in the Windows Credential Manager.")
        except Exception:
            _key_file().write_text(sys.argv[2])
            print(f"keyring unavailable; key written to {_key_file()}")
    else:
        print(__doc__)
