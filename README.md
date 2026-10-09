# 🎮 Daily Personal Gamification Tracker

A lightweight, modern, dark-mode desktop habit tracker and personal gamification dashboard built with **Python**, **Flet**, and **SQLite**.

Transform your daily routines, health habits, and study schedules into an RPG-like progression system featuring **XP, Levels, Streaks, Inverted Scoring for Bad Habits**, a **Multi-Week Analytics Dashboard**, a full **calendar**, and a **study system with a journal, spaced repetition and optional AI deep reviews (Gemini)**.

---

## ✨ Features

### 📅 1. Dynamic Weekly Schedule
* **Built for a 30-second check-in:** today's column shows every option as a button — **one click per habit** (click again to clear), with a "Today 5/7 marked" counter. Nothing to confirm: answers save instantly.
* **Keyboard shortcuts:** `1`–`4` mark the highlighted habit and jump to the next unmarked one, `R` marks a rest day, `0` / `Backspace` clears, arrow keys move (never into future days).
* **Rest days (🌙):** for days when a habit doesn't apply (e.g. no training the day after a 10 km run). A rest counts as answered but **never affects any score or XP**; a day where every answer is Rest still **counts towards the streak**. Positive habits only (vices have no day off), up to **3 per habit per week**, and always visible in the Graphs (heatmap, year map, ranking) and the weekly summary.
* **Past days** are coloured squares (one click opens a short menu to correct them); future days are locked.
* **Nightly reminder:** a tray notification at the time you choose (default 21:30) if anything is still unmarked; the tracker opens on this tab.
* **Dynamic Habit Rows:** Add habits with the `+` button, edit (rename / category), reorder or delete them.
* **Categorization:** Tag habits into `Health`, `Study`, `Routine`, or `Vice / Avoid` with colored badges.
* **Dual Habit Logic (Positive vs. Negative Habits):**
  * **Positive Habits:** `Excellent (+10)`, `Ok (+7)`, `A Little (+4)`, `Skipped (0)`.
  * **Bad Habits to Avoid (Inverted Scoring):** `Resisted (+10)`, `Slipped (+4)`, `Relapsed (0)`.
* **Daily Scoring (0–10 Scale):** Dynamically calculates your daily performance average using passing thresholds (Green $\ge 7.0$, Orange $\ge 5.0$, Red $< 5.0$).
* **Past Weeks:** Navigate back to earlier weeks and fix missed entries (XP updates accordingly).

### 🔥 2. Gamification System
* **Streak Counter (🔥):** Tracks consecutive days maintaining a daily average score $\ge 7.0$.
* **XP Ledger:** Every XP gain is recorded once in an immutable ledger, so your level never shifts retroactively:
  * **Habit day:** `(daily average − 5) × 2` (a bad day costs XP, a perfect day gives +10).
  * **Quest completed:** by difficulty — Easy +10 · Normal +15 · Hard +30 · Epic +60 XP (repeatable quests: once per week/month).
  * **Subquest checked:** +2 XP · **Quest log:** +2 XP for the first real entry of the day per quest.
  * **Study chapter mastered:** +15 XP · **Calendar event done:** +10 XP.
  * **Study journal:** +2 XP for the first real entry (20+ characters) of the day per chapter · **Study review:** +5 XP each.
* **Levels 1–100:** One level every 10 XP, max level at 1,000 XP.
* **Rank Titles:** **Novice** $\rightarrow$ **Apprentice** (16) $\rightarrow$ **Disciplined** (36) $\rightarrow$ **Elite** (61) $\rightarrow$ **Master** (81) $\rightarrow$ **Centurion** (100).

### 📊 3. Graphs
* **One period filter for everything:** last 7 days, 30 days, 12 weeks or 12 months.
* **Headline tiles vs the previous period:** average score, days logged, XP earned, best streak and study time (▲ / ▼ with the difference).
* **Habit heatmap** (habit × day, or × week for long periods) — consistency at a glance, with a tooltip per cell.
* **Daily score trend** (line) with the 7.0 goal, **habit ranking** (strongest first) and **weekday pattern**.
* **Year map:** one square per day for the last 12 months, coloured by the daily score.
* **XP per week** (gains and net losses), **study time per week** and **reviews & quests completed per week**.
* **This week (Gemini, optional):** a short weekly summary — what went well, one pattern, one small suggestion (one call per week).
* Colours follow a validated, colour-blind-safe palette (one blue scale for scores; text is never coloured).

### 🗺️ 4. Quests, Study, Calendar & Documents
* **Quests:** an RPG quest log — **no deadlines on purpose**: nothing can be late; quests can be put **On hold**.
  * **Main / Side / Epic** quests with **Easy / Normal / Hard / Epic** difficulty (the XP reward).
  * **Checkbox steps**, a dated **quest log** with a "next step" bookmark, and a description box.
  * **Measurable targets** (optional): start → target with a unit (e.g. 82 → 77 kg); log values and see a chart.
  * **Repeatable quests** (weekly / monthly): complete once per period; steps reset; skipping a period costs nothing.
  * **Hall of Fame** for completed quests, and an **AI quest planner** (✨, Gemini): describe a goal and get type, difficulty, steps, a first step and an optional target to edit before saving.
* **Study:** chapters move through **Not started → Studying → Reviewing → Mastered**.
  * **Journal** while you study: log each session (notes, time spent, date) and keep a "where I stopped / next step" bookmark.
  * **Wrap-up** to finish: the "Proof of Work" template (ELI5, toy sandbox, break-it test, recall flashcards) with a completion checklist.
  * **Spaced repetition** after mastery: flashcard reviews on days 1, 3, 7 and 21 (a struggled review repeats the next day), shown in the Study tab, Calendar and wallpaper. Turn it off per chapter for projects.
  * **AI deep review (optional, Gemini free tier):** when you master a chapter, Gemini reads your journal and wrap-up and builds a review pack — a clean summary, key concepts, gaps/mistakes in your notes and harder questions for each review stage (recall → application → scenarios → synthesis). During reviews you can type an answer and let Gemini grade it. Set it up with the ✨ button in the Study tab (your key is stored in the Windows Credential Manager). Requires `google-genai` (in requirements.txt).
* **Calendar:** Month, Week, Day (time grid with current-time line, overlapping events side by side, mini-month) and searchable Agenda views.
  * Events with start time, duration or all-day, color, notes and a per-event reminder (tray notification), plus an alarm dialog at start time.
  * Repeats: daily, weekdays, weekly, monthly, yearly, with an optional end date. Edit or delete just one occurrence, this and following, or the whole series.
  * Overlap warnings while scheduling; mark events done for +10 XP.
* **Documents:** a lean expiration tracker — only a name, type and expiration date are needed.
  * Brazilian presets (CNH, RG / CIN, Passaporte, CRLV, IPVA, IPTU, insurance…) with a sensible reminder window each (e.g. passport 6 months, CNH 2 months), editable per document.
  * Status at a glance (valid / expires soon / expired), shown in the **Calendar**, on the wallpaper and as **tray reminders** (when the window starts, 7 days before, on the day).
  * **Renewal quests:** a document entering its window adds a "Renew …" quest to the Quest Log; pressing **Renewed** sets the new date, keeps the history and completes the quest (+XP).
  * **Yearly items** (IPVA, licensing, IPTU, insurance) suggest next year's date automatically.
  * The number and notes are **optional**, encrypted (key in the Windows Credential Manager — back it up with `python secure.py show-key`) and can be hidden behind a **PIN**.

### 🖼️ 5. Desktop Wallpaper HUD
* A **modular card** on your wallpaper: turn blocks on/off and reorder them — streak & today's score, level & XP, **insight of the day**, quests, studies & reviews due, upcoming calendar, document alerts (empty blocks hide).
* **1 or 2 columns**, Compact / Normal / Large size, position and accent color; text **scales with the screen resolution** (sharp on 1440p / 4K).
* **Insight of the day (Gemini, optional):** one short, kind, specific sentence per day based on your recent habits, quests and studies (Português or English; one call per day).
* **Backgrounds:** pure black, the project image, or **a new image each day from a folder** you choose — images fill the screen without being stretched.
* **Live preview** in the tab before applying, and **Pause & restore**: your original wallpaper is kept on the first apply and comes back whenever you pause the HUD.

### 🤖 6. Telegram Assistant (optional)
* **A real assistant in your pocket:** chat by **text or voice message** — "how's my day?", "mark gym as ok", "rest day for stretching today", "add dentist friday 2:30pm", "I studied docker 40 minutes: volumes", "what expires this month?". Gemini reads your real data and acts through safe tools.
* **It never deletes anything** (there is no tool for it), never sees document numbers, and only talks to **your** chat, paired with a one-time code.
* **Replies in text, voice or both**, with a **female or male** neural voice (Brazilian Portuguese or English, via `edge-tts`).
* **Messages it sends you:** a **morning briefing** (your wake-up message: events, reviews, documents, next quest step), **calendar reminders** at each event's own reminder time, **documents expiring**, **study reviews due**, an **evening check-in with answer buttons** (tap to mark each habit) and **achievements** (level up, streak milestones, quests completed, chapters mastered).
* **Quiet hours** hold back non-urgent messages; nothing is ever sent twice, even after a restart.
* Uses long polling (no server, no open port). It works while the app is running (it lives in the tray).

### ⚙️ 7. Options
* **AI & messages language** (Português / English), **start with Windows**, close-to-tray, auto-update on/off.
* **Turn tabs off:** Graphs, Quests, Study, Wallpaper, Calendar and Documents can be disabled — a disabled tab is **not loaded at all** and its background work stops (restart button included).
* **Scoring rules:** the passing score (streak / green day) and rest days per habit per week.
* **Quiet hours**, extra **backup folder**, open the data folder, CSV export, Gemini settings and the whole Telegram setup.

### ⚡ 8. Quality of Life & Storage
* **⚡ Quick-Fill Today:** Automatically marks all unlogged tasks for today (`Ok` for positive habits, `Resisted` for bad habits) in one click.
* **💾 One-Click CSV Export:** Generates a timestamped CSV on your Desktop.
* **🔒 AppData Persistence:** Stores SQLite data in `%APPDATA%\Daily_Personal_Gamification`, so updates never erase your data.
* **🗄️ Daily Backups:** One backup per day (last 14 kept) in the `backups` folder; pick an extra folder in **Options → Data** to also copy it elsewhere (e.g. OneDrive).
* **🔄 Auto-Update & Tray:** Fast-forwards from GitHub on launch (can be turned off), closes to the system tray, single instance only.

---

## 🏗️ Project Architecture

```text
Daily_Personal_Gamification/
│
├── main.py             # App entrypoint, navigation rail, tray icon, reminder loop
├── constants.py        # Scoring weights, XP values, thresholds, rank titles
├── database.py         # SQLite schema & migrations, XP ledger, streaks, backups, CSV export
├── secure.py           # Field-level encryption for the documents vault
├── applog.py           # Rotating log file in AppData
├── updater.py          # git fast-forward auto-update on launch
├── schedule_view.py    # Weekly habit grid and gamification banner
├── graphs_view.py      # Graphs: period filter, tiles, heatmap, trend, ranking, year map, weekly charts
├── analytics.py        # Read-only analytics behind the Graphs tab
├── todo_view.py        # Quest log: steps, quest log, targets, repeats, Hall of Fame, AI planner
├── study_view.py       # Study chapters: journal, wrap-up, reviews, AI settings
├── calendar_view.py    # Calendar and events
├── documents_view.py   # Document expiration tracker, renewals, PIN lock
├── wallpaper.py        # Wallpaper HUD: modular blocks, scaling, backgrounds, pause/restore
├── wallpaper_view.py   # HUD settings screen
├── options_view.py     # Options tab: general, tabs on/off, scoring, quiet hours, data, AI, Telegram
├── settings.py         # Typed app options with defaults (secrets live in the Credential Manager)
├── assistant.py        # Telegram assistant: pairing, chat (text/voice) with Gemini tools, check-in buttons
├── assistant_tools.py  # What the assistant can read and do (no delete tools, idempotent actions)
├── notifier.py         # Proactive messages: briefing, calendar, documents, reviews, check-in, achievements
├── messages.py         # Fixed message texts in Portuguese and English
├── telegram_api.py     # Minimal Telegram Bot API client (httpx, long polling)
├── tts.py              # Voice replies (edge-tts neural voices, falls back to text)
├── ai_gemini.py        # Small Gemini client: key in Credential Manager, model fallback
├── ai_review.py        # AI deep reviews: review packs and answer grading
├── ai_quest.py         # AI quest planner (no dates or deadlines)
├── ai_insight.py       # Insight of the day for the wallpaper (one Gemini call per day)
├── ai_weekly.py        # Weekly summary for the Graphs tab (one Gemini call per week)
├── ui_helpers.py       # Shared confirmation dialog
├── tests/              # Database, AI and assistant tests (unittest, no network)
├── base_wallpaper.jpg  # Background image for the HUD
└── requirements.txt
```

---

## 🚀 Quickstart & Installation

### 1. Clone the repository
```bash
git clone https://github.com/SilentDM/Daily_Personal_Gamification.git
cd Daily_Personal_Gamification
```

### 2. Set up a virtual environment (`venv`)

* **Windows (PowerShell):**
  ```powershell
  python -m venv .venv
  .venv\Scripts\Activate.ps1
  ```
* **Windows (cmd):**
  ```bat
  python -m venv .venv
  .venv\Scripts\activate
  ```
  You can also skip activation and call the venv's Python directly: `.venv\Scripts\python.exe main.py`.
* **macOS / Linux:**
  ```bash
  python3 -m venv .venv
  source .venv/bin/activate
  ```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Run the application
```bash
python main.py
```

### 5. Run the tests
```bash
python -m unittest discover tests
```
Tests use a temporary data folder, so your real database is never touched.

### 6. (Optional) Set up AI deep reviews
1. Get a free Gemini API key at [Google AI Studio](https://aistudio.google.com) → **Get API key**.
2. In the app, open **Study → ✨ AI review settings**, paste the key, click **Test connection** (uses no quota) and **Save**. The key is stored in the Windows Credential Manager, never in the database.
3. Mastered chapters now get an AI review pack automatically; use **Generate missing packs** for chapters mastered earlier.

> When a pack is generated, that chapter's journal and wrap-up are sent to Google's Gemini API. On the free tier, Google may use that content to improve its products.

### 7. (Optional) Set up the Telegram assistant
1. In Telegram, open **@BotFather**, send `/newbot` and follow the steps; copy the **token** it gives you.
2. In the app, open **Options → Telegram assistant**, paste the token and click 💾 (it is checked, then stored in the Windows Credential Manager).
3. Turn **Assistant on** and send `/start <code>` (the pairing code shown in Options) to your new bot. From then on it only answers you.
4. Pick text or voice replies, the voice, and which messages you want. Chatting needs the Gemini key (step 6).

> Your messages (and voice notes) are sent to Gemini to be understood; the replies' voice is generated by Microsoft's free Edge text-to-speech service.

---

## 🖥️ Running as a Silent Desktop Shortcut (Windows)

To launch the tracker directly from your desktop **without opening an ugly black console window**:

1. Right-click on your Desktop $\rightarrow$ **New $\rightarrow$ Shortcut**.
2. Set the target location (pointing to `pythonw.exe` inside your virtual environment):
   ```text
   "C:\Path\To\Daily_Personal_Gamification\.venv\Scripts\pythonw.exe" "C:\Path\To\Daily_Personal_Gamification\main.py"
   ```
3. Set the **Start in** property in the shortcut properties to your project directory:
   ```text
   C:\Path\To\Daily_Personal_Gamification
   ```

> **Pro-Tip (Auto-Launch on Boot):** Press `Win + R`, type `shell:startup`, and paste this shortcut inside the folder. The tracker will greet you every morning when your PC turns on!

---

## 🛠️ Tech Stack

* **Language:** Python 3.10+
* **GUI Framework:** [Flet](https://flet.dev/) (Flutter for Python)
* **Visualizations:** `flet-charts`
* **Wallpaper / Tray:** `Pillow`, `pystray`
* **Encryption:** `cryptography` (Fernet) + `keyring`
* **AI (optional):** Google Gemini via `google-genai` (free tier, structured output with `pydantic`, function calling for the assistant)
* **Assistant (optional):** Telegram Bot API over `httpx`, voice with `edge-tts`
* **Database:** SQLite3 (Local & Persistent in `%APPDATA%`)

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).