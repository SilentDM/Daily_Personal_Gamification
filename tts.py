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


_MP3_KBPS = (0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160)  # MPEG-2/2.5 layer III
_MP3_RATES = {0: (11025, 12000, 8000), 2: (22050, 24000, 16000), 3: (44100, 48000, 32000)}


def mp3_duration(data: bytes) -> float:
    """Real length in seconds, from the MP3 frame headers.

    Telegram expects voice notes in OGG/Opus; for an MP3 without an explicit duration it guesses the
    length and the player stops early, cutting the end of the message. Senders pass this instead.
    """
    i, seconds = 0, 0.0
    while i + 4 <= len(data):
        b1, b2 = data[i + 1], data[i + 2]
        version, bitrate_idx, rate_idx = (b1 >> 3) & 3, b2 >> 4, (b2 >> 2) & 3
        if data[i] != 0xFF or (b1 & 0xE0) != 0xE0 or (b1 >> 1) & 3 != 1 or version == 1 \
                or not 0 < bitrate_idx < 15 or rate_idx == 3:
            i += 1  # not a layer III frame header (e.g. an ID3 tag): keep scanning
            continue
        rate = _MP3_RATES[version][rate_idx]
        if version == 3:  # MPEG-1: 1152 samples per frame, its own bitrate table
            kbps = (0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320)[bitrate_idx]
            size, samples = 144 * kbps * 1000 // rate, 1152
        else:
            kbps = _MP3_KBPS[bitrate_idx]
            size, samples = 72 * kbps * 1000 // rate, 576
        i += size + ((b2 >> 1) & 1)
        seconds += samples / rate
    return seconds


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
