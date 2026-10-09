"""Voice replies for the Telegram assistant: text -> MP3 with Microsoft's neural voices (edge-tts).

edge-tts uses an unofficial Microsoft endpoint (free, no key). If it is missing or fails, callers fall
back to sending text, so the assistant never goes silent because of the voice.
"""
import asyncio
import logging
import re

log = logging.getLogger("gamification")

try:
    import edge_tts
    AVAILABLE = True
except Exception:  # package not installed
    edge_tts = None
    AVAILABLE = False

# language -> gender -> voice
VOICES = {
    "pt": {"female": "pt-BR-FranciscaNeural", "male": "pt-BR-AntonioNeural"},
    "en": {"female": "en-US-AvaNeural", "male": "en-US-AndrewNeural"},
}
MAX_CHARS = 1500  # keeps voice notes short (about 1.5 minutes)


def voice_for(language_code: str, gender: str) -> str:
    return VOICES.get(language_code, VOICES["pt"]).get(gender, VOICES["pt"]["female"])


def speakable(text: str) -> str:
    """Strips markdown-ish symbols and emojis that a voice would read out loud."""
    text = re.sub(r"[*_`#>|~]", "", text or "")
    text = re.sub(r"[\U0001F000-\U0001FAFF☀-➿]", "", text)
    return " ".join(text.split())[:MAX_CHARS]


async def _synthesize(text: str, voice: str) -> bytes:
    data = b""
    async for chunk in edge_tts.Communicate(text, voice).stream():
        if chunk.get("type") == "audio":
            data += chunk["data"]
    return data


def synthesize(text: str, language_code: str = "pt", gender: str = "female") -> bytes:
    """MP3 bytes, or b"" when voice isn't available (the caller then sends text)."""
    if not AVAILABLE:
        return b""
    clean = speakable(text)
    if not clean:
        return b""
    try:
        return asyncio.run(_synthesize(clean, voice_for(language_code, gender)))
    except Exception:
        log.exception("Voice synthesis failed; sending text instead")
        return b""
