# 🎮 Daily Personal Gamification Tracker

A lightweight, modern, dark-mode desktop habit tracker and personal gamification dashboard built with **Python**, **Flet**, and **SQLite**.

Transform your daily routines, health habits, and study schedules into an RPG-like progression system featuring **XP, Levels, Streaks, Inverted Scoring for Bad Habits**, and a **Multi-Week Analytics Dashboard**.

---

## ✨ Features

### 📅 1. Dynamic Weekly Schedule
* **Auto-Highlighting Today Column:** Instantly detects the current day of the week (`Mon`–`Sun`) and highlights it with a cyan accent.
* **Dynamic Habit Rows:** Add tasks on the fly with the `+` button, or delete unwanted tasks with the trash icon.
* **Categorization:** Tag habits into `Health`, `Study`, `Routine`, or `Vice / Avoid` with colored badges.
* **Dual Habit Logic (Positive vs. Negative Habits):**
  * **Positive Habits:** `Excellent (+10)`, `Ok (+7)`, `A Little (+4)`, `Skipped (0)`.
  * **Bad Habits to Avoid (Inverted Scoring):** `Resisted (+10)`, `Slipped (+4)`, `Relapsed (0)`.
* **Daily Scoring (0–10 Scale):** Dynamically calculates your daily performance average using passing thresholds (Green $\ge 8.0$, Orange $\ge 5.0$, Red $< 5.0$).

### 🔥 2. Gamification System
* **Streak Counter (🔥):** Tracks consecutive days maintaining a daily average score $\ge 7.0$.
* **XP & Level Progression:** Earn 10 XP for every score point logged. Level up every 100 XP with an animated progress bar.
* **Rank Titles:** Progress through ranks from **Novice** $\rightarrow$ **Consistent** $\rightarrow$ **Disciplined** $\rightarrow$ **Habit Master** $\rightarrow$ **Ascended**.

### 📊 3. Performance & Analytics Dashboard
* **KPI Metrics:** Track Weekly Average, Task Completion Rate (%), Vice Resistance Rate (%), and your Best Performing Day.
* **Daily Breakdown Bar Chart:** Visualizes Mon–Sun scores with dynamic color coding based on target thresholds.
* **Multi-Week Progression Chart:** Compares current week against past weeks to track long-term improvement over months.
* **Category Mastery:** Visual progress bars displaying your performance per category (`Health`, `Study`, etc.).
* **Hero vs. Nemesis Habit:** Identifies your strongest habit vs. the activity needing the most focus.

### ⚡ 4. Quality of Life & Storage
* **⚡ Quick-Fill Today:** Automatically marks all unlogged tasks for today (`Ok` for positive habits, `Resisted` for bad habits) in one click.
* **💾 One-Click CSV Export:** Generates a timestamped backup CSV on your Desktop.
* **🔒 AppData Persistence:** Stores SQLite data safely in your operating system's `AppData` folder, ensuring updates never erase your data.

---

## 🏗️ Project Architecture

```text
Daily_Personal_Gamification/
│
├── constants.py       # Scoring weights, categories, day names, rank titles
├── database.py        # SQLite schema, queries, streak/XP logic, CSV exporter
├── schedule_view.py   # Tracker grid, dynamic rows, gamification banner
├── graphs_view.py     # Analytics dashboard, KPI cards, and charts
├── main.py            # App entrypoint, window config, and navigation rail
├── requirements.txt   # Dependencies (flet, flet-charts)
└── README.md
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
* **Database:** SQLite3 (Local & Persistent in `%APPDATA%`)

---

## 📜 License

This project is open-source and available under the [MIT License](LICENSE).