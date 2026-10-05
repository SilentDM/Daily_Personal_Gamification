# 🎮 Daily Personal Gamification Tracker

A lightweight, modern, dark-mode desktop habit tracker and personal gamification dashboard built with **Python**, **Flet**, and **SQLite**.

Transform your daily routines, health habits, and study schedules into an RPG-like progression system featuring **XP, Levels, Streaks, Inverted Scoring for Bad Habits**, a **Multi-Week Analytics Dashboard**, a full **calendar**, and a **study system with a journal, spaced repetition and optional AI deep reviews (Gemini)**.

---

## ✨ Features

### 📅 1. Dynamic Weekly Schedule
* **Auto-Highlighting Today Column:** Instantly detects the current day of the week (`Mon`–`Sun`) and highlights it with a cyan accent.
* **Dynamic Habit Rows:** Add tasks on the fly with the `+` button, or delete unwanted tasks with the trash icon.
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
  * **Quest completed:** +15 XP · **Study chapter mastered:** +15 XP · **Calendar event done:** +10 XP.
  * **Quest notes progress:** +2 XP when notes grow by 10+ characters (15 min cooldown).
  * **Study journal:** +2 XP for the first real entry (20+ characters) of the day per chapter · **Study review:** +5 XP each.
* **Levels 1–100:** One level every 10 XP, max level at 1,000 XP.
* **Rank Titles:** **Novice** $\rightarrow$ **Apprentice** (16) $\rightarrow$ **Disciplined** (36) $\rightarrow$ **Elite** (61) $\rightarrow$ **Master** (81) $\rightarrow$ **Centurion** (100).

### 📊 3. Performance & Analytics Dashboard
* **KPI Metrics:** Track Weekly Average, Task Completion Rate (%), Vice Resistance Rate (%), and your Best Performing Day.
* **Daily Breakdown Bar Chart:** Visualizes Mon–Sun scores with dynamic color coding based on target thresholds.
* **Multi-Week Progression Chart:** Compares current week against past weeks to track long-term improvement over months.
* **XP Earned per Week:** Net XP per week from habits, quests, studies and events (last 8 weeks).
* **Category Mastery:** Visual progress bars displaying your performance per category (`Health`, `Study`, etc.).
* **Hero vs. Nemesis Habit:** Identifies your strongest habit vs. the activity needing the most focus.

### 🗺️ 4. Quests, Study, Calendar & Documents
* **Quests:** Main quests with weighted subquests (Planning → Complete), progress bars and a notepad.
* **Study:** chapters move through **Not started → Studying → Reviewing → Mastered**.
  * **Journal** while you study: log each session (notes, time spent, date) and keep a "where I stopped / next step" bookmark.
  * **Wrap-up** to finish: the "Proof of Work" template (ELI5, toy sandbox, break-it test, recall flashcards) with a completion checklist.
  * **Spaced repetition** after mastery: flashcard reviews on days 1, 3, 7 and 21 (a struggled review repeats the next day), shown in the Study tab, Calendar and wallpaper. Turn it off per chapter for projects.
  * **AI deep review (optional, Gemini free tier):** when you master a chapter, Gemini reads your journal and wrap-up and builds a review pack — a clean summary, key concepts, gaps/mistakes in your notes and harder questions for each review stage (recall → application → scenarios → synthesis). During reviews you can type an answer and let Gemini grade it. Set it up with the ✨ button in the Study tab (your key is stored in the Windows Credential Manager). Requires `google-genai` (in requirements.txt).
* **Calendar:** Month, Week, Day (time grid with current-time line, overlapping events side by side, mini-month) and searchable Agenda views.
  * Events with start time, duration or all-day, color, notes and a per-event reminder (tray notification), plus an alarm dialog at start time.
  * Repeats: daily, weekdays, weekly, monthly, yearly, with an optional end date. Edit or delete just one occurrence, this and following, or the whole series.
  * Overlap warnings while scheduling; mark events done for +10 XP.
* **Documents Vault:** Personal documents with masked numbers, auto-clearing clipboard copy, expiration alerts and **field-level encryption** (key stored in the Windows Credential Manager — back it up with `python secure.py show-key`).

### 🖼️ 5. Desktop Wallpaper HUD
* Renders your level, streak, today's score, quests, studies (next step and reviews due), upcoming events and document alerts onto your wallpaper (position, accent color and widgets are configurable).

### ⚡ 6. Quality of Life & Storage
* **⚡ Quick-Fill Today:** Automatically marks all unlogged tasks for today (`Ok` for positive habits, `Resisted` for bad habits) in one click.
* **💾 One-Click CSV Export:** Generates a timestamped CSV on your Desktop.
* **🔒 AppData Persistence:** Stores SQLite data in `%APPDATA%\Daily_Personal_Gamification`, so updates never erase your data.
* **🗄️ Daily Backups:** One backup per day (last 14 kept) in the `backups` folder; set `GAMIFICATION_BACKUP_DIR` to also copy it elsewhere (e.g. OneDrive).
* **🔄 Auto-Update & Tray:** Fast-forwards from GitHub on launch, closes to the system tray, single instance only.

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
├── graphs_view.py      # Analytics dashboard, KPI cards and charts
├── todo_view.py        # Quests and subquests
├── study_view.py       # Study chapters: journal, wrap-up, reviews, AI settings
├── calendar_view.py    # Calendar and events
├── documents_view.py   # Personal documents vault
├── wallpaper.py        # Wallpaper HUD renderer
├── wallpaper_view.py   # HUD settings screen
├── ai_gemini.py        # Small Gemini client: key in Credential Manager, model fallback
├── ai_review.py        # AI deep reviews: review packs and answer grading
├── ui_helpers.py       # Shared confirmation dialog
├── tests/              # Database and AI tests (unittest, no network)
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
* **AI (optional):** Google Gemini via `google-genai` (free tier, structured output with `pydantic`)
* **Database:** SQLite3 (Local & Persistent in `%APPDATA%`)

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).