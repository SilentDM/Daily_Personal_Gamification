import math
import threading
from datetime import date

import flet as ft
import flet_charts as fch

import ai_gemini
import database as db
from constants import QUEST_TYPES, QUEST_DIFFICULTY_XP, QUEST_REPEATS, XP_SUBQUEST, XP_QUEST_LOG, DAY_NAMES
from ui_helpers import confirm_action
from wallpaper import request_wallpaper_update as update_desktop_wallpaper

TYPE_STYLE = {
    "Main": (ft.Icons.STAR_ROUNDED, ft.Colors.AMBER_ACCENT),
    "Side": (ft.Icons.EXPLORE_OUTLINED, ft.Colors.LIGHT_BLUE_300),
    "Epic": (ft.Icons.WORKSPACE_PREMIUM, ft.Colors.PURPLE_ACCENT_100),
}
DIFFICULTY_COLORS = {"Easy": ft.Colors.GREEN_300, "Normal": ft.Colors.CYAN_300,
                     "Hard": ft.Colors.ORANGE_ACCENT, "Epic": ft.Colors.PURPLE_ACCENT_100}
REPEAT_LABELS = {"none": "One-time", "weekly": "Every week", "monthly": "Every month"}
PERIOD_WORD = {"weekly": "this week", "monthly": "this month"}
FILTERS = ("active", "hold", "fame")
GOLD = ft.Colors.AMBER_ACCENT


# ---------------------------------------------------------------- helpers
def fmt_num(value) -> str:
    if value is None:
        return "—"
    return f"{value:g}" if float(value).is_integer() else f"{value:.2f}".rstrip("0").rstrip(".")


def fmt_day(iso: str) -> str:
    try:
        d = date.fromisoformat(iso[:10])
    except (TypeError, ValueError):
        return iso or ""
    return f"{DAY_NAMES[d.weekday()]}, {d:%d/%m/%Y}"


def parse_number(text):
    try:
        return float(str(text).strip().replace(",", "."))
    except (TypeError, ValueError):
        return None


def badge(text, color, size=10):
    return ft.Container(content=ft.Text(text, size=size, color=color, weight=ft.FontWeight.BOLD),
                        border=ft.Border.all(1, color), border_radius=4,
                        padding=ft.Padding.symmetric(horizontal=5, vertical=1))


def section(title, controls, color=ft.Colors.CYAN_ACCENT, trailing=None):
    head = ft.Row([ft.Text(title, size=11, weight=ft.FontWeight.BOLD, color=color, expand=True)] +
                  ([trailing] if trailing else []))
    return ft.Container(content=ft.Column([head, *controls], spacing=8,
                                          horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
                        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=14)


# ---------------------------------------------------------------- AI planner
def open_quest_planner(page: ft.Page, on_saved=None, existing: dict = None):
    """Gemini proposes a quest (or extra steps for `existing`); the user edits it before saving."""
    if not ai_gemini.is_configured():
        def open_settings(e):
            page.pop_dialog()
            from study_view import open_ai_settings
            open_ai_settings(page)

        page.show_dialog(ft.AlertDialog(
            title=ft.Text("AI quest planner", weight=ft.FontWeight.BOLD),
            content=ft.Text(ai_gemini.status_text() + "\nThe planner uses the same Gemini key as the AI study "
                            "reviews (Study tab → ✨)."),
            actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog()),
                     ft.Button("Open AI settings", icon=ft.Icons.SETTINGS, on_click=open_settings)],
        ))
        return

    goal_f = ft.TextField(label="What do you want to achieve?", value=existing["title"] if existing else "",
                          autofocus=not existing, dense=True)
    context_f = ft.TextField(label="Context (optional): where you are now, constraints, what you know",
                             multiline=True, min_lines=2, max_lines=5, dense=True)
    status = ft.Text("", size=12)
    plan_area = ft.Column(spacing=10, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
    state = {"plan": None}
    plan_btn = ft.Button("Plan with AI" if not existing else "Suggest steps", icon=ft.Icons.AUTO_AWESOME)
    save_btn = ft.Button("Create quest" if not existing else "Add selected steps", icon=ft.Icons.CHECK,
                         visible=False)

    def build_preview(plan):
        rows = []
        sub_rows = []
        for s in plan.subquests:
            cb = ft.Checkbox(value=True)
            tf = ft.TextField(value=s, dense=True, expand=True, text_size=13)
            sub_rows.append((cb, tf))
            rows.append(ft.Row([cb, tf], spacing=4))
        state["subs"] = sub_rows
        if existing:
            controls = [ft.Text("Suggested extra steps (untick the ones you don't want):", size=12,
                                color=ft.Colors.GREY_400), *rows]
            if not rows:
                controls.append(ft.Text("Gemini had no extra steps to add.", color=ft.Colors.GREY_500))
            if plan.measurable and not existing.get("has_metric") and existing.get("repeat") == "none":
                state["metric_cb"] = ft.Checkbox(
                    label=f"Also track a target: {fmt_num(plan.metric_start)} → {fmt_num(plan.metric_target)} "
                          f"{plan.metric_unit}", value=False)
                controls.append(state["metric_cb"])
            plan_area.controls = controls
            return
        state["title"] = ft.TextField(label="Quest title", value=plan.title, dense=True)
        state["type"] = ft.Dropdown(label="Type", value=plan.quest_type, dense=True, width=130,
                                    options=[ft.DropdownOption(t) for t in QUEST_TYPES])
        state["difficulty"] = ft.Dropdown(label="Difficulty", value=plan.difficulty, dense=True, width=190,
                                          options=[ft.DropdownOption(key=d, text=f"{d} (+{xp} XP)")
                                                   for d, xp in QUEST_DIFFICULTY_XP.items()])
        state["repeat"] = ft.Dropdown(label="Repeats", value=plan.repeat, dense=True, width=160,
                                      options=[ft.DropdownOption(key=r, text=REPEAT_LABELS[r]) for r in QUEST_REPEATS])
        state["description"] = ft.TextField(label="Description", value=plan.description, multiline=True,
                                            min_lines=2, max_lines=5, dense=True)
        state["first"] = ft.TextField(label="First step (becomes your 'next step' bookmark)", value=plan.first_step,
                                      dense=True)
        state["metric_cb"] = ft.Checkbox(label="Track a numeric target", value=plan.measurable)
        state["unit"] = ft.TextField(label="Unit", value=plan.metric_unit, dense=True, width=110)
        state["start"] = ft.TextField(label="Start", value=fmt_num(plan.metric_start) if plan.measurable else "",
                                      dense=True, width=110)
        state["target"] = ft.TextField(label="Target", value=fmt_num(plan.metric_target) if plan.measurable else "",
                                       dense=True, width=110)
        metric_row = ft.Row([state["unit"], state["start"], state["target"]], spacing=8, visible=plan.measurable)
        state["metric_cb"].on_change = lambda e: (setattr(metric_row, "visible", bool(e.control.value)), page.update())
        plan_area.controls = [
            ft.Divider(height=1, color=ft.Colors.GREY_800),
            state["title"],
            ft.Row([state["type"], state["difficulty"], state["repeat"]], spacing=8, wrap=True),
            state["description"],
            ft.Text("Steps (untick or edit before saving):", size=12, color=ft.Colors.GREY_400),
            *rows,
            state["first"],
            state["metric_cb"],
            metric_row,
        ]

    def run_plan(e):
        if not (goal_f.value or "").strip():
            status.value, status.color = "Describe your goal first.", ft.Colors.RED_ACCENT
            page.update()
            return
        plan_btn.disabled = True
        status.value, status.color = "Gemini is planning your quest…", ft.Colors.GREY_400
        page.update()

        def work():
            import ai_quest
            try:
                plan = ai_quest.plan_quest(goal_f.value, context_f.value or "", existing=existing)
                state["plan"] = plan
                build_preview(plan)
                status.value = ""
                save_btn.visible = True
                plan_btn.content = "Plan again"
            except Exception as exc:
                status.value, status.color = str(exc), ft.Colors.RED_ACCENT
            plan_btn.disabled = False
            page.update()

        threading.Thread(target=work, daemon=True, name="ai-quest-plan").start()

    def save(e):
        plan = state["plan"]
        if plan is None:
            return
        steps = [tf.value.strip() for cb, tf in state.get("subs", []) if cb.value and (tf.value or "").strip()]
        if existing:
            for s in steps:
                db.add_subquest(existing["id"], s)
            if state.get("metric_cb") is not None and state["metric_cb"].value:
                db.update_quest(existing["id"], metric_unit=plan.metric_unit, metric_start=plan.metric_start,
                                metric_target=plan.metric_target)
            page.pop_dialog()
            if on_saved:
                on_saved(existing["id"])
            return
        title = (state["title"].value or "").strip()
        if not title:
            status.value, status.color = "The quest needs a title.", ft.Colors.RED_ACCENT
            page.update()
            return
        metric = {}
        if state["metric_cb"].value and state["repeat"].value == "none":
            start, target = parse_number(state["start"].value), parse_number(state["target"].value)
            if start is None or target is None or not (state["unit"].value or "").strip():
                status.value, status.color = "Fill unit, start and target (numbers) or untick the target.", \
                    ft.Colors.RED_ACCENT
                page.update()
                return
            metric = {"metric_unit": state["unit"].value.strip(), "metric_start": start, "metric_target": target}
        quest_id = db.add_quest(title, quest_type=state["type"].value, difficulty=state["difficulty"].value,
                                repeat=state["repeat"].value, notes=(state["description"].value or "").strip(),
                                next_step=(state["first"].value or "").strip(), subquests=steps, **metric)
        page.pop_dialog()
        if on_saved:
            on_saved(quest_id)

    plan_btn.on_click = run_plan
    save_btn.on_click = save
    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color=GOLD),
                      ft.Text("AI quest planner" if not existing else f"More steps for '{existing['title']}'",
                              weight=ft.FontWeight.BOLD, expand=True)]),
        content=ft.Container(width=620, content=ft.Column(
            [goal_f, context_f, ft.Row([plan_btn, status], spacing=12), plan_area,
             ft.Text("No deadlines: Gemini is told to order steps, never to schedule them.", size=11,
                     color=ft.Colors.GREY_600)],
            spacing=12, tight=True, scroll=ft.ScrollMode.AUTO, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
        actions=[ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()), save_btn],
    ))


# ---------------------------------------------------------------- view
class TodoView(ft.Row):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=0, visible=False,
                         vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.app_page = page
        self.selected_id = None
        self.filter = "active"
        self.drafts = {}      # quest_id -> unsent quest-log entry {"text", "value", "next_step"}
        self.feedback = {}    # quest_id -> last feedback message
        self.sidebar = ft.Column(spacing=8, expand=True)
        self.workspace = ft.Column(spacing=14, expand=True, scroll=ft.ScrollMode.AUTO,
                                   horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.controls = [
            ft.Container(content=self.sidebar, width=340, padding=15, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW),
            ft.VerticalDivider(width=1, color=ft.Colors.GREY_800),
            ft.Container(content=self.workspace, expand=True,
                         padding=ft.Padding.only(left=20, right=30, top=15, bottom=30)),
        ]
        self.render()

    # ------------------------------------------------------------ data helpers
    def _visible(self, quests):
        return self._visible_for(quests, self.filter)

    def _changed(self):
        self.render()
        update_desktop_wallpaper()

    def _update(self):
        if self.app_page:
            self.app_page.update()

    def select(self, quest_id):
        self.selected_id = quest_id
        self.render()

    def _saved_from_planner(self, quest_id):
        self.selected_id = quest_id
        self.filter = "active"
        self._changed()

    # ------------------------------------------------------------ public (used by main.py)
    def render(self):
        quests = db.get_quests()
        visible = self._visible(quests)
        if not any(q["id"] == self.selected_id for q in visible):
            self.selected_id = visible[0]["id"] if visible else None
        self._render_sidebar(quests, visible)
        self._render_workspace(next((q for q in quests if q["id"] == self.selected_id), None))
        self._update()

    # ------------------------------------------------------------ sidebar
    def _render_sidebar(self, quests, visible):
        new_f = ft.TextField(hint_text="New quest…", expand=True, dense=True, text_size=13)

        def add(e=None):
            title = (new_f.value or "").strip()
            if title:
                self.selected_id = db.add_quest(title)
                self.filter = "active"
                self._changed()

        new_f.on_submit = add
        year, week, _ = db.get_current_week_info()
        done_count, week_xp = db.get_quest_week_stats(year, week)
        counts = {f: len(self._visible_for(quests, f)) for f in FILTERS}

        controls = [
            ft.Row([ft.Icon(ft.Icons.MILITARY_TECH, color=GOLD, size=26),
                    ft.Text("Quest Log", size=18, weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(ft.Icons.AUTO_AWESOME, icon_color=GOLD if ai_gemini.is_configured()
                                  else ft.Colors.GREY_500, tooltip="Plan a new quest with AI",
                                  on_click=lambda e: open_quest_planner(self.app_page, self._saved_from_planner))]),
            ft.Row([new_f, ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=GOLD, tooltip="Add quest", on_click=add)]),
            ft.Container(
                content=ft.Row([ft.Icon(ft.Icons.EMOJI_EVENTS, color=GOLD, size=18),
                                ft.Text(f"This week: {done_count} quest{'s' if done_count != 1 else ''} done • "
                                        f"+{week_xp:g} XP from quests", size=12, expand=True)]),
                bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER), border_radius=8, padding=8,
            ),
            ft.SegmentedButton(
                segments=[ft.Segment(value="active", label=ft.Text(f"Active {counts['active']}", size=12, no_wrap=True)),
                          ft.Segment(value="hold", label=ft.Text(f"On hold {counts['hold']}", size=12, no_wrap=True)),
                          ft.Segment(value="fame", label=ft.Text(f"Hall of Fame {counts['fame']}", size=12,
                                                                 no_wrap=True))],
                selected=[self.filter], show_selected_icon=False,
                on_change=lambda e: self._set_filter(e.control.selected[0]) if e.control.selected else None,
            ),
            ft.Divider(color=ft.Colors.GREY_800, height=1),
        ]
        tiles = [self._tile(q) for q in visible] or [ft.Text(
            {"active": "No active quests. Add one above, or let ✨ plan one with you!",
             "hold": "Nothing on hold.",
             "fame": "Completed quests will be celebrated here."}[self.filter], color=ft.Colors.GREY_500, size=13)]
        controls.append(ft.Column(tiles, spacing=6, scroll=ft.ScrollMode.AUTO, expand=True))
        self.sidebar.controls = controls

    @staticmethod
    def _visible_for(quests, f):
        wanted = {"active": "Active", "hold": "On hold", "fame": "Complete"}[f]
        return [q for q in quests if q["status"] == wanted]

    def _set_filter(self, value):
        self.filter = value
        self.render()

    def _tile(self, q):
        selected = q["id"] == self.selected_id
        icon, icolor = TYPE_STYLE.get(q["quest_type"], TYPE_STYLE["Main"])
        dcolor = DIFFICULTY_COLORS.get(q["difficulty"], ft.Colors.CYAN_300)
        if q["status"] == "Complete":
            hint = f"Completed {fmt_day(q['completed_at'] or '')} • +{q['xp_reward']} XP"
            hint_color = GOLD
        elif q["repeat"] != "none":
            if q["done_this_period"]:
                back = db.next_period_start(q["repeat"])
                hint, hint_color = f"Done {PERIOD_WORD[q['repeat']]} ✓ • back {back:%d/%m}", ft.Colors.GREEN_ACCENT
            else:
                hint, hint_color = f"{REPEAT_LABELS[q['repeat']]} • ready", ft.Colors.CYAN_200
        elif q["next_step"]:
            hint, hint_color = f"→ {q['next_step']}", ft.Colors.GREY_300
        elif q["has_metric"]:
            hint = f"{fmt_num(q['metric_current'])} / {fmt_num(q['metric_target'])} {q['metric_unit']}"
            hint_color = ft.Colors.GREY_300
        else:
            hint, hint_color = f"{q['sub_done']}/{q['sub_total']} steps" if q["sub_total"] else "", ft.Colors.GREY_500
        bar_color = GOLD if q["status"] == "Complete" else (ft.Colors.GREEN_ACCENT if q["progress_pct"] >= 99.9
                                                            else icolor)
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Icon(icon, color=icolor, size=18),
                        ft.Text(q["title"], size=14, weight=ft.FontWeight.BOLD if selected else ft.FontWeight.W_500,
                                expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                        badge(f"+{q['xp_reward']}", dcolor)], spacing=6),
                ft.ProgressBar(value=q["progress_pct"] / 100.0, color=bar_color, bgcolor=ft.Colors.GREY_800, height=4),
                ft.Text(hint, size=11, color=hint_color, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS)
                if hint else ft.Container(height=0),
            ], spacing=4),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if selected else ft.Colors.TRANSPARENT,
            border=ft.Border.only(left=ft.BorderSide(3, icolor)),
            border_radius=8, padding=10, ink=True,
            on_click=lambda e, qid=q["id"]: self.select(qid),
        )

    # ------------------------------------------------------------ workspace
    def _render_workspace(self, q):
        if q is None:
            self.workspace.controls = [ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.MAP_OUTLINED, size=48, color=ft.Colors.GREY_600),
                    ft.Text("Start a quest on the left — or press ✨ and plan one with Gemini.",
                            color=ft.Colors.GREY_400),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                alignment=ft.Alignment.CENTER, padding=50)]
            return
        controls = [self._header(q), self._progress_card(q)]
        if q["status"] != "Complete":
            controls.append(self._next_step_card(q))
        controls.append(self._subquests_card(q))
        if q["has_metric"] or (q["repeat"] == "none" and q["status"] != "Complete"):
            controls.append(self._target_card(q))
        controls += [self._log_card(q), self._description_card(q)]
        self.workspace.controls = controls

    def _save(self, qid, **fields):
        db.update_quest(qid, **fields)
        self._changed()

    def _header(self, q):
        qid = q["id"]
        title_f = ft.TextField(value=q["title"], label="Quest", dense=True, expand=True, text_size=16)
        title_f.on_blur = lambda e: self._save(qid, title=(e.control.value or "").strip() or "Untitled") \
            if (e.control.value or "").strip() != q["title"] else None
        type_dd = ft.Dropdown(label="Type", value=q["quest_type"], dense=True, width=130,
                              options=[ft.DropdownOption(t) for t in QUEST_TYPES],
                              on_select=lambda e: self._save(qid, quest_type=e.control.value))
        diff_dd = ft.Dropdown(label="Difficulty", value=q["difficulty"], dense=True, width=190,
                              options=[ft.DropdownOption(key=d, text=f"{d} (+{xp} XP)")
                                       for d, xp in QUEST_DIFFICULTY_XP.items()],
                              on_select=lambda e: self._save(qid, difficulty=e.control.value),
                              disabled=q["status"] == "Complete")
        repeat_dd = ft.Dropdown(label="Repeats", value=q["repeat"], dense=True, width=160,
                                options=[ft.DropdownOption(key=r, text=REPEAT_LABELS[r]) for r in QUEST_REPEATS],
                                on_select=lambda e: self._save(qid, repeat=e.control.value),
                                disabled=q["status"] == "Complete",
                                tooltip="Repeatable quests can be completed once per week/month")
        actions = []
        if q["status"] == "Active":
            actions.append(ft.TextButton("Put on hold", icon=ft.Icons.PAUSE_CIRCLE_OUTLINE,
                                         on_click=lambda e: (db.set_quest_status(qid, "On hold"), self._changed())))
        elif q["status"] == "On hold":
            actions.append(ft.TextButton("Resume", icon=ft.Icons.PLAY_CIRCLE_OUTLINE,
                                         on_click=lambda e: (db.set_quest_status(qid, "Active"), self._changed())))
        actions += [
            ft.IconButton(ft.Icons.ARROW_UPWARD, icon_size=16, tooltip="Move quest up",
                          on_click=lambda e: (db.move_quest(qid, "up"), self.render())),
            ft.IconButton(ft.Icons.ARROW_DOWNWARD, icon_size=16, tooltip="Move quest down",
                          on_click=lambda e: (db.move_quest(qid, "down"), self.render())),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, tooltip="Delete quest",
                          on_click=lambda e: confirm_action(
                              self.app_page, "Delete quest?", f"'{q['title']}', its steps and its log will be removed.",
                              lambda: (db.delete_quest(qid), self._changed()))),
        ]
        return ft.Column([
            ft.Row([title_f], spacing=10),
            ft.Row([ft.Row([type_dd, diff_dd, repeat_dd], spacing=8), ft.Row(actions, spacing=0)],
                   alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
        ], spacing=10)

    def _progress_card(self, q):
        qid = q["id"]
        pct = q["progress_pct"]
        parts = []
        if q["sub_total"]:
            parts.append(f"{q['sub_done']}/{q['sub_total']} steps")
        if q["has_metric"]:
            parts.append(f"{fmt_num(q['metric_current'])} of {fmt_num(q['metric_target'])} {q['metric_unit']}")
        if q["repeat"] != "none":
            parts.append(f"completed {q['times_completed']} time{'s' if q['times_completed'] != 1 else ''}")
        feedback = self.feedback.pop(qid, "")

        if q["status"] == "Complete":
            action = ft.Row([
                ft.Icon(ft.Icons.EMOJI_EVENTS, color=GOLD),
                ft.Text(f"Completed {fmt_day(q['completed_at'] or '')} • +{q['xp_reward']} XP earned",
                        color=GOLD, weight=ft.FontWeight.BOLD, expand=True),
                ft.TextButton("Reopen", icon=ft.Icons.UNDO, on_click=lambda e: confirm_action(
                    self.app_page, "Reopen quest?", f"It leaves the Hall of Fame and its +{q['xp_reward']} XP is "
                    "removed until you complete it again.", lambda: (db.set_quest_status(qid, "Active"),
                                                                     self._changed()), confirm_label="Reopen")),
            ])
        elif q["repeat"] != "none" and q["done_this_period"]:
            back = db.next_period_start(q["repeat"])
            action = ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE, color=ft.Colors.GREEN_ACCENT),
                ft.Text(f"Done {PERIOD_WORD[q['repeat']]}! Available again {fmt_day(back.isoformat())}.",
                        color=ft.Colors.GREEN_ACCENT, expand=True),
                ft.TextButton("Undo", icon=ft.Icons.UNDO,
                              on_click=lambda e: (db.undo_quest_completion(qid), self._changed())),
            ])
        else:
            label = f"Complete {PERIOD_WORD[q['repeat']]}" if q["repeat"] != "none" else "Complete quest"
            ready = pct >= 99.9 or not (q["sub_total"] or q["has_metric"])
            btn = ft.Button(f"{label} (+{q['xp_reward']} XP)", icon=ft.Icons.EMOJI_EVENTS,
                            on_click=lambda e: self.complete(q),
                            bgcolor=GOLD if ready else None, color=ft.Colors.BLACK if ready else None,
                            disabled=q["status"] == "On hold")
            hint = "All steps done — turn it in!" if pct >= 99.9 and (q["sub_total"] or q["has_metric"]) else \
                ("On hold — resume it to complete." if q["status"] == "On hold" else
                 "You can complete it whenever you feel it's done.")
            action = ft.Row([ft.Text(hint, size=12, color=ft.Colors.GREY_400, expand=True), btn])

        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Text(f"{pct:.0f}%", size=26, weight=ft.FontWeight.BOLD),
                        ft.Text(" • ".join(parts), size=12, color=ft.Colors.GREY_400, expand=True)], spacing=12),
                ft.ProgressBar(value=pct / 100.0, height=10, bgcolor=ft.Colors.GREY_800,
                               color=GOLD if q["status"] == "Complete" else (
                                   ft.Colors.GREEN_ACCENT if pct >= 99.9 else TYPE_STYLE[q["quest_type"]][1])),
                action,
                ft.Text(feedback, size=12, color=ft.Colors.GREEN_ACCENT) if feedback else ft.Container(height=0),
            ], spacing=8),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=14,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.4, GOLD) if q["status"] == "Complete" else
                                 ft.Colors.with_opacity(0.12, ft.Colors.GREY)),
        )

    def complete(self, q):
        xp = db.complete_quest(q["id"])
        if q["repeat"] != "none":
            self.feedback[q["id"]] = f"+{xp:g} XP — nice! See you {('next week' if q['repeat'] == 'weekly' else 'next month')}."
            self._changed()
            return
        self._changed()
        self.app_page.show_dialog(ft.AlertDialog(
            title=ft.Row([ft.Icon(ft.Icons.EMOJI_EVENTS, color=GOLD, size=32),
                          ft.Text("Quest complete!", weight=ft.FontWeight.BOLD)]),
            content=ft.Text(f"'{q['title']}' joins your Hall of Fame. +{xp:g} XP"),
            actions=[ft.Button("Awesome", on_click=lambda e: self.app_page.pop_dialog())],
        ))

    def _next_step_card(self, q):
        qid = q["id"]
        field = ft.TextField(value=q["next_step"], hint_text="What's the next small step?", dense=True,
                             border=ft.InputBorder.NONE, expand=True, text_size=14)
        field.on_blur = lambda e: self._save(qid, next_step=(e.control.value or "").strip()) \
            if (e.control.value or "").strip() != q["next_step"] else None
        return ft.Container(
            content=ft.Row([ft.Icon(ft.Icons.BOOKMARK, color=ft.Colors.ORANGE_ACCENT),
                            ft.Column([ft.Text("NEXT STEP", size=11, weight=ft.FontWeight.BOLD,
                                               color=ft.Colors.ORANGE_ACCENT), field], spacing=0, expand=True)],
                           spacing=12),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE), border_radius=10, padding=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.ORANGE)),
        )

    def _subquests_card(self, q):
        qid = q["id"]
        rows = []
        for i, s in enumerate(q["subquests"]):
            cb = ft.Checkbox(value=s["done"], label=s["title"],
                             label_style=ft.TextStyle(decoration=ft.TextDecoration.LINE_THROUGH if s["done"] else None,
                                                      color=ft.Colors.GREY_500 if s["done"] else ft.Colors.WHITE),
                             on_change=lambda e, sid=s["id"]: self._toggle_sub(qid, sid, bool(e.control.value)),
                             expand=True)
            rows.append(ft.Row([
                cb,
                ft.Text(f"+{XP_SUBQUEST:g}", size=10, color=ft.Colors.GREY_600),
                ft.IconButton(ft.Icons.EDIT, icon_size=14, tooltip="Rename",
                              on_click=lambda e, sub=s: self._rename_sub(sub)),
                ft.IconButton(ft.Icons.ARROW_UPWARD, icon_size=14, tooltip="Move step up", disabled=i == 0,
                              on_click=lambda e, sid=s["id"]: (db.move_subquest(sid, "up"), self.render())),
                ft.IconButton(ft.Icons.ARROW_DOWNWARD, icon_size=14, tooltip="Move step down",
                              disabled=i == len(q["subquests"]) - 1,
                              on_click=lambda e, sid=s["id"]: (db.move_subquest(sid, "down"), self.render())),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=ft.Colors.RED_300, tooltip="Delete step",
                              on_click=lambda e, sid=s["id"]: (db.delete_subquest(sid), self._changed())),
            ], spacing=0))
        new_f = ft.TextField(hint_text="Add a step…", dense=True, expand=True, text_size=13)

        def add(e=None):
            if (new_f.value or "").strip():
                db.add_subquest(qid, new_f.value.strip())
                self._changed()

        new_f.on_submit = add
        if not rows:
            rows.append(ft.Text("No steps yet. Break the quest into small actions — or let ✨ suggest some.",
                                size=12, color=ft.Colors.GREY_500, italic=True))
        if q["repeat"] != "none":
            rows.insert(0, ft.Text(f"Steps reset {('every Monday' if q['repeat'] == 'weekly' else 'on the 1st of each month')}.",
                                   size=11, color=ft.Colors.GREY_500))
        suggest = ft.TextButton("Suggest steps", icon=ft.Icons.AUTO_AWESOME,
                                on_click=lambda e: open_quest_planner(self.app_page, lambda _id: self._changed(),
                                                                      existing=q))
        return section(f"STEPS ({q['sub_done']}/{q['sub_total']})",
                       rows + [ft.Row([new_f, ft.IconButton(ft.Icons.ADD, tooltip="Add step", on_click=add)])],
                       trailing=suggest)

    def _toggle_sub(self, qid, sid, done):
        xp = db.set_subquest_done(sid, done)
        if xp:
            self.feedback[qid] = f"Step done! +{xp:g} XP"
        self._changed()

    def _rename_sub(self, sub):
        field = ft.TextField(value=sub["title"], autofocus=True, dense=True)

        def save(e=None):
            if (field.value or "").strip():
                db.rename_subquest(sub["id"], field.value.strip())
            self.app_page.pop_dialog()
            self.render()

        field.on_submit = save
        self.app_page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Rename step"), content=ft.Container(field, width=420),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.app_page.pop_dialog()),
                     ft.Button("Save", on_click=save)]))

    # ------------------------------------------------------------ measurable target
    def _target_card(self, q):
        qid = q["id"]
        if not q["has_metric"]:
            return section("TARGET", [
                ft.Text("Is progress a number? (kg, books, km, money…) Track it here.", size=12,
                        color=ft.Colors.GREY_500),
                ft.Row([ft.TextButton("Add a measurable target", icon=ft.Icons.ADD_CHART,
                                      on_click=lambda e: self._edit_target(q))]),
            ])
        values = [e for e in reversed(db.get_quest_log(qid)) if e["value"] is not None][-12:]
        summary = ft.Row([
            ft.Column([ft.Text("START", size=10, color=ft.Colors.GREY_500),
                       ft.Text(f"{fmt_num(q['metric_start'])} {q['metric_unit']}", size=15)], spacing=0),
            ft.Icon(ft.Icons.ARROW_FORWARD, color=ft.Colors.GREY_600, size=16),
            ft.Column([ft.Text("NOW", size=10, color=ft.Colors.GREY_500),
                       ft.Text(f"{fmt_num(q['metric_current'])} {q['metric_unit']}", size=18,
                               weight=ft.FontWeight.BOLD, color=GOLD)], spacing=0),
            ft.Icon(ft.Icons.ARROW_FORWARD, color=ft.Colors.GREY_600, size=16),
            ft.Column([ft.Text("TARGET", size=10, color=ft.Colors.GREY_500),
                       ft.Text(f"{fmt_num(q['metric_target'])} {q['metric_unit']}", size=15)], spacing=0),
            ft.Container(expand=True),
            ft.Text(f"{q['metric_pct']:.0f}%", size=18, weight=ft.FontWeight.BOLD),
        ], spacing=12)
        controls = [summary]
        if values:
            controls.append(ft.Container(content=self._metric_chart(q, values), height=170))
        else:
            controls.append(ft.Text("Log your first value below to start the chart.", size=12, color=ft.Colors.GREY_500))
        if q["status"] != "Complete":
            value_f = ft.TextField(label=f"New value ({q['metric_unit']})", dense=True, width=170)
            note_f = ft.TextField(label="Note (optional)", dense=True, expand=True)
            error = ft.Text("", size=12, color=ft.Colors.RED_ACCENT)

            def log_value(e=None):
                value = parse_number(value_f.value)
                if value is None:
                    error.value = "Type a number."
                    self._update()
                    return
                xp = db.add_quest_log(qid, (note_f.value or "").strip(), value=value)
                self.feedback[qid] = f"Logged {fmt_num(value)} {q['metric_unit']}" + (f" • +{xp:g} XP" if xp else "")
                self._changed()

            value_f.on_submit = log_value
            controls += [ft.Row([value_f, note_f, ft.Button("Log value", icon=ft.Icons.ADD, on_click=log_value)],
                                spacing=8), error]
        edit = ft.TextButton("Edit target", icon=ft.Icons.TUNE, on_click=lambda e: self._edit_target(q))
        return section("TARGET", controls, trailing=edit)

    def _metric_chart(self, q, values):
        nums = [e["value"] for e in values] + [q["metric_start"], q["metric_target"]]
        lo, hi = min(nums), max(nums)
        pad = max((hi - lo) * 0.15, 1.0)
        y_min, y_max = math.floor(lo - pad), math.ceil(hi + pad)
        step = max(1, math.ceil((y_max - y_min) / 4))
        increasing = q["metric_target"] >= q["metric_start"]
        groups = []
        for i, e in enumerate(values):
            good = e["value"] >= q["metric_start"] if increasing else e["value"] <= q["metric_start"]
            groups.append(fch.BarChartGroup(x=i, rods=[fch.BarChartRod(
                from_y=y_min, to_y=e["value"], width=22, color=ft.Colors.GREEN_ACCENT if good else ft.Colors.ORANGE_ACCENT,
                border_radius=ft.BorderRadius.all(3), tooltip=f"{fmt_num(e['value'])} {q['metric_unit']}")]))
        return fch.BarChart(
            groups=groups,
            border=ft.Border.all(1, ft.Colors.GREY_800),
            left_axis=fch.ChartAxis(labels=[fch.ChartAxisLabel(value=v, label=ft.Text(fmt_num(v), size=10))
                                            for v in range(y_min, y_max + 1, step)], label_size=40),
            bottom_axis=fch.ChartAxis(labels=[fch.ChartAxisLabel(value=i, label=ft.Text(e["entry_date"][8:10] + "/" +
                                                                                         e["entry_date"][5:7], size=10))
                                              for i, e in enumerate(values)], label_size=24),
            horizontal_grid_lines=fch.ChartGridLines(color=ft.Colors.GREY_800, interval=step),
            min_y=y_min, max_y=y_max, interactive=True, expand=True,
        )

    def _edit_target(self, q):
        unit_f = ft.TextField(label="Unit (kg, books, km, R$…)", value=q["metric_unit"], dense=True)
        start_f = ft.TextField(label="Start value", value=fmt_num(q["metric_start"]) if q["metric_start"] is not None
                               else "", dense=True, width=150)
        target_f = ft.TextField(label="Target value", value=fmt_num(q["metric_target"]) if q["metric_target"] is not None
                                else "", dense=True, width=150)
        error = ft.Text("", size=12, color=ft.Colors.RED_ACCENT)

        def save(e):
            start, target = parse_number(start_f.value), parse_number(target_f.value)
            if not (unit_f.value or "").strip() or start is None or target is None or start == target:
                error.value = "Fill the unit and two different numbers."
                self._update()
                return
            db.update_quest(q["id"], metric_unit=unit_f.value.strip(), metric_start=start, metric_target=target)
            self.app_page.pop_dialog()
            self._changed()

        def remove(e):
            db.update_quest(q["id"], metric_unit="", metric_start=None, metric_target=None)
            self.app_page.pop_dialog()
            self._changed()

        actions = [ft.TextButton("Cancel", on_click=lambda e: self.app_page.pop_dialog()),
                   ft.Button("Save", icon=ft.Icons.CHECK, on_click=save)]
        if q["has_metric"]:
            actions.insert(0, ft.TextButton("Remove target", icon=ft.Icons.DELETE_OUTLINE,
                                            icon_color=ft.Colors.RED_300, on_click=remove))
        self.app_page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Measurable target", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=420, content=ft.Column([
                ft.Text("Works both ways: 82 → 77 kg (going down) or 0 → 12 books (going up). "
                        "Logged values keep their history.", size=12, color=ft.Colors.GREY_400),
                unit_f, ft.Row([start_f, target_f], spacing=10), error],
                spacing=12, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
            actions=actions))

    # ------------------------------------------------------------ quest log
    def _log_card(self, q):
        qid = q["id"]
        draft = self.drafts.setdefault(qid, {"text": "", "next_step": ""})
        text_f = ft.TextField(value=draft["text"], label="What did you do? Progress, ideas, blockers…",
                              multiline=True, min_lines=2, max_lines=8, text_size=13)
        text_f.on_change = lambda e: draft.update(text=e.control.value or "")
        next_f = ft.TextField(label="Next step (updates the bookmark)", value=draft["next_step"], dense=True)
        next_f.on_change = lambda e: draft.update(next_step=e.control.value or "")
        msg = ft.Text("", size=12, color=ft.Colors.RED_ACCENT)

        def log(e):
            text = (text_f.value or "").strip()
            if not text:
                msg.value = "Write something first."
                self._update()
                return
            xp = db.add_quest_log(qid, text, next_step=(next_f.value or "").strip())
            self.drafts.pop(qid, None)
            self.feedback[qid] = f"Logged! +{xp:g} XP" if xp else (
                f"Logged (write {db.QUEST_LOG_MIN_CHARS}+ characters to earn XP)." if len(text) < db.QUEST_LOG_MIN_CHARS
                else "Logged (today's log XP for this quest already earned).")
            self._changed()

        entries = db.get_quest_log(qid)
        entry_rows = [self._entry_row(q, en) for en in entries] or [
            ft.Text("No entries yet — a line per session is enough.", size=12, color=ft.Colors.GREY_500, italic=True)]
        controls = []
        if q["status"] != "Complete":
            controls += [text_f, ft.Row([ft.Container(content=next_f, expand=True),
                                         ft.Button(f"Log (+{XP_QUEST_LOG:g} XP)", icon=ft.Icons.ADD, on_click=log)],
                                        spacing=8), msg]
        controls += entry_rows
        return section(f"QUEST LOG ({len(entries)})", controls)

    def _entry_row(self, q, en):
        unit = q["metric_unit"]
        head = [ft.Text(fmt_day(en["entry_date"]), size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200,
                        expand=True)]
        if en["value"] is not None:
            head.insert(1, badge(f"{fmt_num(en['value'])} {unit}".strip(), GOLD, size=11))
        head += [
            ft.IconButton(ft.Icons.EDIT, icon_size=14, tooltip="Edit entry", on_click=lambda e: self._edit_entry(q, en)),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=14, icon_color=ft.Colors.RED_300, tooltip="Delete entry",
                          on_click=lambda e: confirm_action(self.app_page, "Delete log entry?",
                                                            f"The entry from {fmt_day(en['entry_date'])} will be removed.",
                                                            lambda: (db.delete_quest_log(en["id"]), self._changed()))),
        ]
        lines = [ft.Row(head, spacing=6)]
        if en["text"]:
            lines.append(ft.Text(en["text"], size=13, selectable=True))
        return ft.Container(content=ft.Column(lines, spacing=2), bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
                            border_radius=8, padding=ft.Padding.only(left=10, right=4, top=2, bottom=8))

    def _edit_entry(self, q, en):
        text_f = ft.TextField(label="Entry", value=en["text"], multiline=True, min_lines=3, max_lines=10)
        value_f = ft.TextField(label=f"Value ({q['metric_unit']})", value=fmt_num(en["value"]) if en["value"] is not None
                               else "", dense=True, width=160, visible=q["has_metric"] or en["value"] is not None)
        date_f = ft.TextField(label="Date", value=f"{date.fromisoformat(en['entry_date']):%d/%m/%Y}", dense=True,
                              width=140)
        error = ft.Text("", size=12, color=ft.Colors.RED_ACCENT)

        def save(e):
            d = db.parse_flexible_date(date_f.value or "")
            value = parse_number(value_f.value) if (value_f.value or "").strip() else None
            if not d or ((value_f.value or "").strip() and value is None) or \
                    (not (text_f.value or "").strip() and value is None):
                error.value = "Check the date (DD/MM/YYYY), the value, and that the entry isn't empty."
                self._update()
                return
            db.update_quest_log(en["id"], (text_f.value or "").strip(), value, d.isoformat())
            self.app_page.pop_dialog()
            self._changed()

        self.app_page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Edit log entry", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=500, content=ft.Column([text_f, ft.Row([value_f, date_f], spacing=10), error],
                                                              spacing=12, tight=True,
                                                              horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.app_page.pop_dialog()),
                     ft.Button("Save", icon=ft.Icons.CHECK, on_click=save)]))

    # ------------------------------------------------------------ description
    def _description_card(self, q):
        field = ft.TextField(value=q["notes"], hint_text="Why this quest matters, links, references, ideas…",
                             multiline=True, min_lines=3, max_lines=None, text_size=13)
        field.on_blur = lambda e: self._save(q["id"], notes=e.control.value or "") \
            if (e.control.value or "") != q["notes"] else None
        return section("DESCRIPTION & NOTES", [field], color=ft.Colors.GREY_400)
