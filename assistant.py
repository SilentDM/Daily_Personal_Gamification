"""Telegram assistant: chat (text or voice) with Gemini + the app's tools, check-in buttons, proactive sends.

Runs in a background thread with long polling (no server, no port): it only works while the app is open.
Security: it talks to ONE chat, paired with a one-time code shown in Options; everything else is ignored.
"""
import logging
import secrets
import threading
import time
from collections import deque
from datetime import date, datetime

import ai_gemini
import assistant_tools as tools
import database as db
import messages
import settings
import telegram_api
import tts
from constants import POSITIVE_SCORES, NEGATIVE_SCORES, REST_STATUS, DAY_NAMES

log = logging.getLogger("gamification")

HISTORY_TURNS = 6           # remembered exchanges (short-term memory, not persisted)
STALE_MESSAGE_SECONDS = 600  # messages sent while the app was closed for longer than this are skipped
SHORT = {"Excellent": "Excellent", "Ok": "Ok", "A Little": "A little", "Skipped": "Skipped",
         "Resisted": "Resisted", "Slipped": "Slipped", "Relapsed": "Relapsed", REST_STATUS: "Rest"}


# ------------------------------------------------------------------ check-in keyboard
def checkin_keyboard(d: date = None):
    """(text, inline keyboard) for the habits still unmarked on `d`, or (None, None) when all are answered."""
    d = d or date.today()
    iso = d.isocalendar()
    logs = db.get_current_week_logs(iso[0], iso[1])
    rows = []
    pending = 0
    for aid, name, _, neg in db.get_activities():
        status, score = logs.get((aid, iso[2] - 1), ("-", None))
        if score is not None or status == REST_STATUS:
            continue
        pending += 1
        answers = [k for k in (NEGATIVE_SCORES if neg else POSITIVE_SCORES) if k != "-"]
        if not neg and db.can_rest(aid, iso[0], iso[1], iso[2] - 1):
            answers.append(REST_STATUS)
        rows.append([{"text": f"— {name} —", "callback_data": "noop"}])
        rows.append([{"text": SHORT.get(a, a), "callback_data": f"h|{aid}|{d.isoformat()}|{a}"} for a in answers])
    if not pending:
        return None, None
    return messages.t("checkin_title", n=pending), rows


def day_score_text(d: date) -> str:
    iso = d.isocalendar()
    scores = [s for (aid, day), (_, s) in db.get_current_week_logs(iso[0], iso[1]).items()
              if day == iso[2] - 1 and s is not None]
    if not scores:
        return messages.t("checkin_done_noscore")
    return messages.t("checkin_done", score=f"{sum(scores) / len(scores):.1f}")


# ------------------------------------------------------------------ prompts
def system_prompt() -> str:
    now = datetime.now()
    language = "Brazilian Portuguese" if messages.lang() == "pt" else "English"
    return f"""You are the personal assistant inside the user's habit-gamification app, talking on Telegram.
Now: {DAY_NAMES[now.weekday()]} {now:%Y-%m-%d %H:%M}. Always answer in {language}.

How to work:
- Use the tools to read real data before answering about habits, agenda, quests, studies, progress or documents.
  Never invent data.
- You may act (mark habits, create events, log studies, update quests) when the user clearly asks.
  Convert relative dates ("sexta", "amanhã", "next monday") to YYYY-MM-DD yourself from today's date.
- If a request is ambiguous (which habit? what time?), ask a short question instead of guessing.
  If a tool returns ok=false, explain the error simply and ask what to do.
- You cannot delete anything (there is no tool for it). If asked, say it must be done in the app.
- Never reveal document numbers or notes (the tools don't have them anyway).
- Be warm, encouraging and brief: this is a chat. Plain text, short lines, at most one or two emojis,
  no markdown tables or headings. Confirm actions in one line (e.g. "Gym: Ok ✓").
- The app is about steady improvement without pressure: never shame missed days."""


class Assistant:
    def __init__(self, bot_factory=None, generate=None, synthesize=None):
        self._bot_factory = bot_factory or telegram_api.Bot
        self._generate = generate or ai_gemini.generate
        self._synthesize = synthesize or tts.synthesize
        self.bot = None
        self.bot_username = ""
        self.pairing_code = f"{secrets.randbelow(10 ** 6):06d}"
        self.last_error = ""
        self.history = deque(maxlen=HISTORY_TURNS * 2)
        self._stop = None
        self._thread = None
        self._lock = threading.Lock()

    # ---------------------------------------------------------- lifecycle
    @property
    def running(self) -> bool:
        return bool(self._thread and self._thread.is_alive() and not self._stop.is_set())

    @property
    def chat_id(self) -> str:
        return settings.get("tg_chat_id")

    def start(self) -> bool:
        """Starts polling when the assistant is enabled and a token is saved. Safe to call again (restarts)."""
        self.stop()
        if not settings.flag("tg_enabled"):
            return False
        bot = self._bot_factory()
        if not bot.token:
            self.last_error = "No Telegram bot token saved yet."
            return False
        self.bot = bot
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, args=(bot, self._stop), daemon=True,
                                        name="telegram-assistant")
        self._thread.start()
        return True

    def stop(self):
        if self._stop:
            self._stop.set()

    def unpair(self):
        settings.set("tg_chat_id", "")
        self.pairing_code = f"{secrets.randbelow(10 ** 6):06d}"

    def status_text(self) -> str:
        if not settings.flag("tg_enabled"):
            return "Off."
        if self.last_error:
            return f"Problem: {self.last_error}"
        if not self.running:
            return "Not running (save a bot token and turn it on)."
        name = f"@{self.bot_username}" if self.bot_username else "the bot"
        if not self.chat_id:
            return f"Running. Send  /start {self.pairing_code}  to {name} to pair your Telegram."
        return f"Running and paired with your chat ({name})."

    def _run(self, bot, stop):
        try:
            self.bot_username = (bot.get_me() or {}).get("username", "")
            self.last_error = ""
        except telegram_api.TelegramError as exc:
            self.last_error = str(exc)
            log.warning("Telegram assistant: %s", exc)
        offset, backoff = None, 5
        while not stop.is_set():
            try:
                updates = bot.get_updates(offset, timeout=50)
                self.last_error = ""
                backoff = 5
            except telegram_api.TelegramError as exc:
                self.last_error = str(exc)
                log.warning("Telegram polling failed: %s", exc)
                stop.wait(backoff)
                backoff = min(backoff * 2, 300)
                continue
            for update in updates:
                offset = update["update_id"] + 1
                if stop.is_set():
                    break
                try:
                    self.handle_update(update)
                except Exception:
                    log.exception("Telegram update failed")

    # ---------------------------------------------------------- sending
    def send(self, text: str, buttons=None, speak: bool = False) -> bool:
        """Sends to the paired chat. speak=True follows the reply mode (voice/text); buttons force text."""
        chat = self.chat_id
        if not (self.bot and chat and text):
            return False
        try:
            mode = settings.get("tg_reply_mode")
            if speak and not buttons and mode in ("voice", "both"):
                mp3 = self._synthesize(text, messages.lang(), settings.get("tg_voice"))
                if mp3:
                    caption = text if mode == "both" and len(text) <= 1024 else None
                    self.bot.send_voice(chat, mp3, caption=caption)
                    if mode == "both" and caption is None:
                        self.bot.send_message(chat, text)
                    return True
            self.bot.send_message(chat, text, buttons=buttons)
            return True
        except telegram_api.TelegramError as exc:
            self.last_error = str(exc)
            log.warning("Telegram send failed: %s", exc)
            return False

    def send_checkin(self, d: date = None) -> bool:
        text, buttons = checkin_keyboard(d)
        if not text:
            return False
        return self.send(text, buttons=buttons)

    # ---------------------------------------------------------- updates
    def handle_update(self, update: dict):
        if "callback_query" in update:
            self._handle_callback(update["callback_query"])
            return
        msg = update.get("message") or {}
        chat = str((msg.get("chat") or {}).get("id", ""))
        if not chat:
            return
        text = (msg.get("text") or "").strip()

        if not self.chat_id:  # not paired yet: only "/start CODE" is accepted
            if text.startswith("/start"):
                code = text.split(maxsplit=1)[1].strip() if " " in text else ""
                if code and secrets.compare_digest(code, self.pairing_code):
                    settings.set("tg_chat_id", chat)
                    self.bot.send_message(chat, messages.t("paired") + "\n\n" + messages.t("help"))
                else:
                    self.bot.send_message(chat, messages.t("private"))
            return
        if chat != self.chat_id:
            return  # a stranger: stay silent
        if time.time() - msg.get("date", time.time()) > STALE_MESSAGE_SECONDS:
            return  # sent while the app was closed long ago

        if text in ("/start", "/help") or text.startswith("/start "):
            self.bot.send_message(chat, messages.t("help"))
            return
        if text == "/checkin":
            if not self.send_checkin():
                self.bot.send_message(chat, day_score_text(date.today()))
            return

        voice = msg.get("voice") or msg.get("audio")
        if voice:
            self.bot.send_chat_action(chat, "record_voice" if settings.get("tg_reply_mode") != "text" else "typing")
            try:
                audio = self.bot.download_file(voice["file_id"])
            except telegram_api.TelegramError as exc:
                self.bot.send_message(chat, messages.t("ai_error", error=exc))
                return
            reply = self.ask(audio=audio, mime=voice.get("mime_type") or "audio/ogg")
        elif text:
            self.bot.send_chat_action(chat, "typing")
            reply = self.ask(text=text)
        else:
            return
        self.send(reply, speak=True)

    def _handle_callback(self, cq: dict):
        chat = str(((cq.get("message") or {}).get("chat") or {}).get("id", ""))
        if not self.chat_id or chat != self.chat_id:
            return
        data = cq.get("data") or ""
        if not data.startswith("h|"):
            self.bot.answer_callback(cq["id"])
            return
        try:
            _, aid, day, status = data.split("|", 3)
            habit = next((n for a, n, _, _ in db.get_activities() if a == int(aid)), None)
            if habit is None:
                raise ValueError("habit not found")
            with tools.ActionLog():
                result = tools.mark_habit(habit, status, day)
        except ValueError:
            result = {"ok": False, "error": "?"}
        self.bot.answer_callback(cq["id"], messages.t("marked", habit=result.get("habit", ""), answer=status)
                                 if result.get("ok") else result.get("error", "")[:190])
        message_id = cq["message"]["message_id"]
        text, buttons = checkin_keyboard(date.fromisoformat(day))
        try:
            if text:
                self.bot.edit_text(chat, message_id, text, buttons=buttons)
            else:
                self.bot.edit_text(chat, message_id, day_score_text(date.fromisoformat(day)))
        except telegram_api.TelegramError:
            pass  # "message is not modified" etc.

    # ---------------------------------------------------------- thinking
    def ask(self, text: str = "", audio: bytes = None, mime: str = "audio/ogg") -> str:
        """One conversational turn with tools. Returns the reply text (errors become friendly text)."""
        history = "\n".join(f"{who}: {said}" for who, said in self.history)
        intro = f"Recent conversation:\n{history}\n\n" if history else ""
        if audio is not None:
            prompt = [intro + "The user sent this voice message. Understand it and reply to it:",
                      ai_gemini.types.Part.from_bytes(data=audio, mime_type=mime)]
            said = "(voice message)"
        else:
            prompt = intro + f"User: {text}"
            said = text
        with self._lock, tools.ActionLog():
            try:
                reply, _ = self._generate(prompt, system_prompt(), temperature=0.5, max_output_tokens=2048,
                                          tools=tools.ALL_TOOLS, max_tool_calls=10)
            except ai_gemini.AINotConfigured:
                return messages.t("no_ai")
            except ai_gemini.AIError as exc:
                return messages.t("ai_error", error=exc)
        self.history.append(("User", said))
        self.history.append(("Assistant", reply))
        return reply

    def compose(self, instruction: str, fallback: str) -> str:
        """Short proactive text written by Gemini from live data (briefing); `fallback` if AI is unavailable."""
        try:
            with tools.ActionLog():
                reply, _ = self._generate(instruction, system_prompt(), temperature=0.6, max_output_tokens=1024,
                                          tools=tools.READ_TOOLS, max_tool_calls=4)
            return reply
        except ai_gemini.AIError:
            return fallback


assistant = Assistant()  # the app's single instance
