"""Small Gemini client (free tier friendly) used by the AI study reviews.

Same approach as Silent_multiverse's core/ai_gemini.py: structured output through a
Pydantic schema and automatic fallback to the next model on rate limits / errors.
Differences: self-contained, its own API key, and models are chosen from the free
models.list() call instead of benchmarking each model with real generations.

The API key lives in the Windows Credential Manager (keyring), never in the database.
"""
import json
import logging
import re
import threading
from datetime import datetime, timedelta

log = logging.getLogger("gamification")

KEYRING_SERVICE = "DailyPersonalGamification"
KEYRING_ACCOUNT = "gemini-api-key"
TIMEOUT_SECONDS = 90
MODELS_CACHE_DAYS = 7
SETTING_MODELS = "ai_models_cache"      # hud_settings: {"at": iso, "models": [...]}
SETTING_PREFERRED = "ai_preferred_model"

_request_lock = threading.Lock()  # one request at a time keeps us under the free-tier RPM

try:
    from google import genai
    from google.genai import types
    AVAILABLE = True
except Exception:  # package not installed
    genai = types = None
    AVAILABLE = False

_EXCLUDED = ("embedding", "tts", "audio", "image", "imagen", "veo", "live", "vision", "robotics",
             "aqa", "gemma", "learnlm", "computer-use", "native")


class AIError(Exception):
    """Error with a message meant for the user."""


class AINotConfigured(AIError):
    pass


# ------------------------------------------------------------------ key
def get_api_key() -> str:
    try:
        import keyring
        return (keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT) or "").strip()
    except Exception:
        log.exception("Could not read the Gemini key from the Credential Manager")
        return ""


def set_api_key(key: str):
    import keyring
    key = (key or "").strip()
    if key:
        keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, key)
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except Exception:
            pass
    _clear_model_cache()


def is_configured() -> bool:
    return AVAILABLE and bool(get_api_key())


def status_text() -> str:
    if not AVAILABLE:
        return "The google-genai package is not installed (pip install -r requirements.txt)."
    if not get_api_key():
        return "No Gemini API key saved yet."
    return "Gemini is configured."


# ------------------------------------------------------------------ models
def rank_models(models) -> list:
    """Orders usable text models: stable before preview, Flash > Flash-Lite > Pro, newest first.

    `models` is an iterable of (name, supported_actions).
    Pro is last on purpose: its free-tier quota is the smallest.
    """
    ranked = []
    for name, actions in models:
        lower = name.lower()
        if "gemini" not in lower or any(term in lower for term in _EXCLUDED):
            continue
        if actions and "generateContent" not in actions:
            continue
        version = re.search(r"gemini-(\d+(?:\.\d+)?)", lower)
        version = float(version.group(1)) if version else 0.0
        if "flash-lite" in lower:
            family = 2
        elif "flash" in lower:
            family = 3
        elif "pro" in lower:
            family = 1
        else:
            family = 0
        stable = not any(tag in lower for tag in ("preview", "exp", "thinking"))
        ranked.append((stable, family, version, name))
    ranked.sort(key=lambda r: (r[0], r[1], r[2]), reverse=True)
    return [r[3] for r in ranked]


def _client(key: str = None):
    return genai.Client(api_key=key or get_api_key(),
                        http_options=types.HttpOptions(timeout=TIMEOUT_SECONDS * 1000))


def _list_models(client) -> list:
    return rank_models(
        (m.name, getattr(m, "supported_actions", None) or []) for m in client.models.list()
    )


def _clear_model_cache():
    try:
        import database as db
        db.set_hud_setting(SETTING_MODELS, "")
    except Exception:
        pass


def model_order(client=None, force: bool = False) -> list:
    """Models to try, best first (cached for MODELS_CACHE_DAYS; preferred model on top)."""
    import database as db
    settings = db.get_hud_settings()
    models = []
    try:
        cached = json.loads(settings.get(SETTING_MODELS) or "{}")
        if not force and cached.get("models") and \
                datetime.fromisoformat(cached["at"]) > datetime.now() - timedelta(days=MODELS_CACHE_DAYS):
            models = cached["models"]
    except (ValueError, KeyError, TypeError):
        models = []
    if not models:
        models = _list_models(client or _client())
        if models:
            db.set_hud_setting(SETTING_MODELS, json.dumps({"at": datetime.now().isoformat(), "models": models}))
    preferred = (settings.get(SETTING_PREFERRED) or "").strip()
    if preferred:
        preferred = preferred if preferred.startswith("models/") else f"models/{preferred}"
        models = [preferred] + [m for m in models if m != preferred]
    return models


# ------------------------------------------------------------------ errors
def _error_code(exc) -> int:
    code = getattr(exc, "code", None)
    return code if isinstance(code, int) else 0


def _is_rate_limit(exc) -> bool:
    text = str(exc).lower()
    return _error_code(exc) == 429 or any(k in text for k in ("resource_exhausted", "quota", "rate limit"))


def _is_bad_key(exc) -> bool:
    text = str(exc).lower()
    return _error_code(exc) in (401, 403) or "api_key_invalid" in text or "api key not valid" in text


# ------------------------------------------------------------------ generation
def generate(prompt: str, system: str, schema=None, temperature: float = 0.4, max_output_tokens: int = 8192):
    """Asks Gemini, falling back across models. Returns (result, model_name).

    With `schema` (a Pydantic model class) the result is a validated instance of it.
    Raises AIError / AINotConfigured with a user-facing message.
    """
    if not AVAILABLE:
        raise AIError(status_text())
    key = get_api_key()
    if not key:
        raise AINotConfigured("Set up your Gemini API key first (Study tab → AI settings).")

    config = types.GenerateContentConfig(
        system_instruction=system,
        temperature=temperature,
        max_output_tokens=max_output_tokens,
        response_mime_type="application/json" if schema else None,
        response_schema=schema,
    )
    with _request_lock:
        client = _client(key)
        try:
            models = model_order(client)
        except Exception as exc:
            if _is_bad_key(exc):
                raise AIError("Gemini rejected the API key. Check it in AI settings.") from exc
            raise AIError(f"Could not reach Gemini: {exc}") from exc
        if not models:
            raise AIError("No Gemini text models are available for this API key.")

        rate_limited, last_error = 0, None
        for model in models:
            try:
                response = client.models.generate_content(model=model, contents=prompt, config=config)
                text = (response.text or "").strip()
                if not text:
                    last_error = "empty response"
                    continue
                if schema is None:
                    return text, model
                return schema.model_validate_json(text), model
            except Exception as exc:
                if _is_bad_key(exc):
                    raise AIError("Gemini rejected the API key. Check it in AI settings.") from exc
                if _is_rate_limit(exc):
                    rate_limited += 1
                    log.warning("Gemini rate limit on %s, trying the next model", model)
                else:
                    log.warning("Gemini model %s failed: %s", model, exc)
                last_error = exc
        if rate_limited == len(models):
            raise AIError("Gemini free-tier quota reached for now. It will retry later.")
        raise AIError(f"All Gemini models failed ({last_error}).")


def test_connection(key: str = None):
    """Checks a key without spending generation quota. Returns (ok, message)."""
    if not AVAILABLE:
        return False, status_text()
    key = (key or "").strip() or get_api_key()
    if not key:
        return False, "Type or save an API key first."
    try:
        models = _list_models(_client(key))
    except Exception as exc:
        if _is_bad_key(exc):
            return False, "Gemini rejected this API key."
        return False, f"Could not reach Gemini: {exc}"
    if not models:
        return False, "The key works, but no text models are available for it."
    best = models[0].removeprefix("models/")
    return True, f"Connected — {len(models)} usable models (will use {best} first)."
