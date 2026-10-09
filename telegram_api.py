"""Minimal Telegram Bot API client (plain HTTPS via httpx, no extra dependency).

The bot token lives in the Windows Credential Manager, never in the database.
"""
import json
import logging

import httpx

log = logging.getLogger("gamification")

KEYRING_SERVICE = "DailyPersonalGamification"
KEYRING_ACCOUNT = "telegram-bot-token"
API = "https://api.telegram.org"
TIMEOUT = 20


class TelegramError(Exception):
    """Error with a message meant for the user."""


# ------------------------------------------------------------------ token
def get_token() -> str:
    try:
        import keyring
        return (keyring.get_password(KEYRING_SERVICE, KEYRING_ACCOUNT) or "").strip()
    except Exception:
        log.exception("Could not read the Telegram token from the Credential Manager")
        return ""


def set_token(token: str):
    import keyring
    token = (token or "").strip()
    if token:
        keyring.set_password(KEYRING_SERVICE, KEYRING_ACCOUNT, token)
    else:
        try:
            keyring.delete_password(KEYRING_SERVICE, KEYRING_ACCOUNT)
        except Exception:
            pass


# ------------------------------------------------------------------ calls
class Bot:
    def __init__(self, token: str = None, client: httpx.Client = None):
        self.token = (token or get_token()).strip()
        self.client = client or httpx.Client(timeout=TIMEOUT)

    def _url(self, method: str) -> str:
        return f"{API}/bot{self.token}/{method}"

    def call(self, method: str, timeout: float = TIMEOUT, files=None, **params):
        if not self.token:
            raise TelegramError("No Telegram bot token saved yet.")
        data = {k: (json.dumps(v) if isinstance(v, (dict, list)) else v) for k, v in params.items() if v is not None}
        try:
            if files:
                resp = self.client.post(self._url(method), data=data, files=files, timeout=timeout)
            else:
                resp = self.client.post(self._url(method), data=data, timeout=timeout)
        except httpx.HTTPError as exc:
            raise TelegramError(f"Could not reach Telegram: {exc}") from exc
        try:
            body = resp.json()
        except ValueError:
            raise TelegramError(f"Telegram answered HTTP {resp.status_code}")
        if not body.get("ok"):
            desc = body.get("description", f"HTTP {resp.status_code}")
            if resp.status_code == 401:
                raise TelegramError("Telegram rejected the bot token.")
            raise TelegramError(desc)
        return body.get("result")

    def get_me(self):
        return self.call("getMe")

    def get_updates(self, offset: int = None, timeout: int = 50):
        """Long-polls for new messages / button presses. getUpdates' own `timeout` is the long-poll
        time, so the HTTP timeout must be longer (call() can't be used: its `timeout` means HTTP)."""
        if not self.token:
            raise TelegramError("No Telegram bot token saved yet.")
        params = {"timeout": timeout, "allowed_updates": json.dumps(["message", "callback_query"])}
        if offset is not None:
            params["offset"] = offset
        try:
            resp = self.client.post(self._url("getUpdates"), data=params, timeout=timeout + 10)
            body = resp.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise TelegramError(f"Could not reach Telegram: {exc}") from exc
        if not body.get("ok"):
            raise TelegramError(body.get("description", "getUpdates failed"))
        return body.get("result", [])

    def send_message(self, chat_id, text: str, buttons=None, reply_to=None):
        return self.call("sendMessage", chat_id=chat_id, text=text[:4096],
                         reply_markup={"inline_keyboard": buttons} if buttons else None,
                         reply_to_message_id=reply_to)

    def edit_buttons(self, chat_id, message_id, buttons):
        return self.call("editMessageReplyMarkup", chat_id=chat_id, message_id=message_id,
                         reply_markup={"inline_keyboard": buttons or []})

    def edit_text(self, chat_id, message_id, text: str, buttons=None):
        return self.call("editMessageText", chat_id=chat_id, message_id=message_id, text=text[:4096],
                         reply_markup={"inline_keyboard": buttons} if buttons else None)

    def answer_callback(self, callback_id: str, text: str = None):
        return self.call("answerCallbackQuery", callback_query_id=callback_id, text=text)

    def send_voice(self, chat_id, mp3: bytes, caption: str = None):
        return self.call("sendVoice", files={"voice": ("reply.mp3", mp3, "audio/mpeg")}, chat_id=chat_id,
                         caption=caption[:1024] if caption else None, timeout=60)

    def send_chat_action(self, chat_id, action: str = "typing"):
        try:
            self.call("sendChatAction", chat_id=chat_id, action=action)
        except TelegramError:
            pass

    def download_file(self, file_id: str) -> bytes:
        info = self.call("getFile", file_id=file_id)
        path = info.get("file_path")
        try:
            resp = self.client.get(f"{API}/file/bot{self.token}/{path}", timeout=60)
            resp.raise_for_status()
        except httpx.HTTPError as exc:
            raise TelegramError(f"Could not download the voice message: {exc}") from exc
        return resp.content
