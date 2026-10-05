import re
from datetime import date, timedelta

import flet as ft

import ai_gemini
import ai_review
import database as db
from constants import XP_STUDY, XP_STUDY_LOG, XP_REVIEW, STUDY_STAGES, REVIEW_DAYS, DAY_NAMES
from ui_helpers import confirm_action
from wallpaper import request_wallpaper_update as update_desktop_wallpaper

SOURCES = ["FIAP", "Alura", "Nano Courses", "Documentation / Book", "Self-Study"]
STAGE_COLORS = {
    "Not started": ft.Colors.BLUE_GREY_400,
    "Studying": ft.Colors.ORANGE_ACCENT,
    "Reviewing": ft.Colors.AMBER_ACCENT,
    "Mastered": ft.Colors.GREEN_ACCENT,
}
STAGE_ICONS = {
    "Not started": ft.Icons.RADIO_BUTTON_UNCHECKED,
    "Studying": ft.Icons.MENU_BOOK,
    "Reviewing": ft.Icons.FACT_CHECK,
    "Mastered": ft.Icons.MILITARY_TECH,
}
MINUTE_OPTIONS = [0, 15, 30, 45, 60, 90, 120, 180, 240]
FILTERS = ("active", "mastered", "all")
REVIEW_COLOR = ft.Colors.TEAL_ACCENT_400

DEFAULT_ELI5 = """• What is it?
->

• What problem does it solve?
->

• Real-world analogy / Simple metaphor:
-> """

DEFAULT_CODE = """# 2. Minimal Proof of Work Example
# (Write from scratch from memory, not copied from the video)

def proof_of_work():
    pass
"""

DEFAULT_BREAK = """• If I remove or change [X], what error happens?
->

• When should I NOT use this?
->

• Common edge cases & pitfalls:
-> """

DEFAULT_RECALL = """Q1:
A1:

Q2:
A2: """

WRAP_UP_FIELDS = [
    ("eli5", "1. The ELI5 Summary (explain it simply, no jargon)", DEFAULT_ELI5, 6, None),
    ("code_sandbox", "2. The Toy Sandbox (proof-of-work code example)", DEFAULT_CODE, 7, "Consolas"),
    ("break_test", "3. The Break-It Test (edge cases & common failures)", DEFAULT_BREAK, 6, None),
    ("recall_questions", "4. Active Recall Flashcards (Q1: … / A1: …) — used in your reviews", DEFAULT_RECALL, 6, None),
]


# ---------------------------------------------------------------- helpers
def fmt_minutes(total: int) -> str:
    if not total:
        return "0 min"
    h, m = divmod(int(total), 60)
    return f"{h}h {m:02d}min" if h else f"{m} min"


def fmt_day(iso: str) -> str:
    try:
        d = date.fromisoformat(iso)
    except (TypeError, ValueError):
        return iso or ""
    return f"{DAY_NAMES[d.weekday()]}, {d:%d/%m/%Y}"


def is_filled(value: str, template: str) -> bool:
    """True when a wrap-up box holds more than its template prompts."""
    text = (value or "").strip()
    if not text or text == template.strip():
        return False
    stripped = re.sub(r"(?m)^\s*(•.*|->\s*|Q\d*:\s*|A\d*:\s*|#.*|def proof_of_work\(\):|pass)\s*$", "", text)
    return bool(stripped.strip())


def parse_flashcards(text: str):
    """Splits 'Q1: … / A1: …' text into [(question, answer)]; free text becomes one card."""
    cards, q, a, current = [], None, [], None
    for line in (text or "").splitlines():
        mq = re.match(r"^\s*Q\d*\s*[:.)-]\s*(.*)$", line, re.I)
        ma = re.match(r"^\s*A\d*\s*[:.)-]\s*(.*)$", line, re.I)
        if mq:
            if q is not None:
                cards.append((q, "\n".join(a).strip()))
            q, a, current = mq.group(1).strip(), [], "q"
        elif ma and q is not None:
            a, current = [ma.group(1)], "a"
        elif current == "a":
            a.append(line)
        elif current == "q" and line.strip():
            q += " " + line.strip()
    if q is not None:
        cards.append((q, "\n".join(a).strip()))
    cards = [(qq, aa) for qq, aa in cards if qq or aa]
    if not cards and is_filled(text, DEFAULT_RECALL):
        cards = [("What do you remember about this chapter?", text.strip())]
    return cards


def review_status(review: dict, today: date):
    if review["done_date"]:
        if review["remembered"]:
            return "Done", ft.Colors.GREEN_ACCENT
        return "Struggled — repeated", ft.Colors.ORANGE_ACCENT
    due = date.fromisoformat(review["due_date"])
    if due < today:
        return f"Overdue ({(today - due).days}d)", ft.Colors.RED_ACCENT
    if due == today:
        return "Due today", REVIEW_COLOR
    return f"In {(due - today).days} day(s)", ft.Colors.GREY_400


STAGE_FOCUS = {1: "recall", 2: "application", 3: "scenarios & edge cases", 4: "synthesis — teach it back"}
VERDICT_STYLE = {
    "correct": ("Correct", ft.Colors.GREEN_ACCENT, ft.Icons.CHECK_CIRCLE),
    "partial": ("Partially correct", ft.Colors.AMBER_ACCENT, ft.Icons.ADJUST),
    "incorrect": ("Not quite", ft.Colors.RED_ACCENT, ft.Icons.CANCEL),
}


def _section_title(text, color=ft.Colors.CYAN_ACCENT):
    return ft.Text(text, size=11, weight=ft.FontWeight.BOLD, color=color)


def _ai_question_card(page, topic, index, q, reveal_list):
    """One AI question: type an answer, check it with Gemini, or just reveal the model answer."""
    answer_f = ft.TextField(hint_text="Your answer…", multiline=True, min_lines=2, max_lines=8, dense=True,
                            text_size=13)
    model_answer = ft.Text(q.get("answer", ""), size=13, color=ft.Colors.GREEN_200, selectable=True)
    answer_box = ft.Container(content=ft.Column([_section_title("MODEL ANSWER", ft.Colors.GREEN_200), model_answer],
                                                spacing=2, tight=True), visible=False)
    reveal_list.append(answer_box)
    result = ft.Column(spacing=4, tight=True, visible=False)
    check_btn = ft.TextButton("Check with AI", icon=ft.Icons.AUTO_AWESOME)

    def show_answer(e):
        answer_box.visible = True
        page.update()

    def check(e):
        text = (answer_f.value or "").strip()
        if not text:
            result.controls = [ft.Text("Type an answer first.", size=12, color=ft.Colors.GREY_400)]
            result.visible = True
            page.update()
            return
        check_btn.disabled = True
        result.controls = [ft.Row([ft.ProgressRing(width=14, height=14, stroke_width=2),
                                   ft.Text("Gemini is checking your answer…", size=12, color=ft.Colors.GREY_400)])]
        result.visible = True
        page.update()

        def work():
            import ai_review
            try:
                grade = ai_review.grade_answer(topic, q.get("question", ""), q.get("answer", ""), text)
                label, color, icon = VERDICT_STYLE.get(grade.verdict.lower().strip(), VERDICT_STYLE["partial"])
                controls = [ft.Row([ft.Icon(icon, color=color, size=18),
                                    ft.Text(label, color=color, weight=ft.FontWeight.BOLD)], spacing=6),
                            ft.Text(grade.feedback, size=13, selectable=True)]
                controls += [ft.Text(f"• {m}", size=12, color=ft.Colors.AMBER_200) for m in grade.missing]
                answer_box.visible = True
            except Exception as exc:
                controls = [ft.Text(str(exc), size=12, color=ft.Colors.RED_ACCENT)]
            result.controls = controls
            check_btn.disabled = False
            page.update()

        import threading
        threading.Thread(target=work, daemon=True, name="ai-grade").start()

    check_btn.on_click = check
    import ai_gemini
    check_btn.disabled = not ai_gemini.is_configured()
    if check_btn.disabled:
        check_btn.tooltip = "Set up your Gemini API key in AI settings"

    kind = (q.get("kind") or "").strip()
    return ft.Container(
        content=ft.Column([
            ft.Row([ft.Text(f"Q{index}. {q.get('question', '')}", size=14, weight=ft.FontWeight.W_600,
                            selectable=True, expand=True),
                    ft.Container(content=ft.Text(kind, size=10, color=REVIEW_COLOR),
                                 border=ft.Border.all(1, REVIEW_COLOR), border_radius=4,
                                 padding=ft.Padding.symmetric(horizontal=4, vertical=1)) if kind else ft.Container()],
                   vertical_alignment=ft.CrossAxisAlignment.START),
            answer_f,
            ft.Row([check_btn, ft.TextButton("Show answer", icon=ft.Icons.VISIBILITY, on_click=show_answer)],
                   spacing=4),
            result,
            answer_box,
        ], spacing=6, tight=True),
        bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=8, padding=10,
    )


def _pack_summary_controls(pack):
    controls = [_section_title("WHAT THE LESSON WAS ABOUT"), ft.Text(pack.get("summary", ""), size=13, selectable=True)]
    concepts = pack.get("key_concepts") or []
    if concepts:
        controls.append(_section_title("KEY CONCEPTS"))
        controls += [ft.Text(spans=[ft.TextSpan(f"{c.get('name', '')}: ", ft.TextStyle(weight=ft.FontWeight.BOLD)),
                                    ft.TextSpan(c.get("explanation", ""))], size=13, selectable=True)
                     for c in concepts]
    gaps = pack.get("gaps") or []
    if gaps:
        controls.append(_section_title("GAPS IN YOUR NOTES", ft.Colors.AMBER_ACCENT))
        controls += [ft.Column([ft.Text(f"⚠ {g.get('issue', '')}", size=13, color=ft.Colors.AMBER_200, selectable=True),
                                ft.Text(f"→ {g.get('correction', '')}", size=13, selectable=True)], spacing=2, tight=True)
                     for g in gaps]
    return controls


def open_review_dialog(page: ft.Page, review: dict, on_done=None):
    """Spaced-repetition review. With an AI pack: harder questions per stage, answer checking by
    Gemini and the lesson summary / gaps; without one: the chapter's own flashcards.

    `review` needs id, session_id and review_no (as returned by db.get_pending_reviews).
    """
    chapter = db.get_study_session(review["session_id"])
    if not chapter:
        return
    stage = max(1, min(review["review_no"], len(REVIEW_DAYS)))
    pack_row = db.get_ai_pack(chapter["id"])
    # a failed *re*generation keeps the previous content, so use whatever content exists
    pack = pack_row["content"] if pack_row and pack_row["content"] else None
    reveal = []
    body = []

    if pack:
        import ai_review
        body.append(ft.Text(f"Stage {stage}: {STAGE_FOCUS.get(stage, '')}. Answer from memory — type it and "
                            "let Gemini check it, or reveal the model answer.", size=12, color=ft.Colors.GREY_400))
        body += [_ai_question_card(page, chapter["topic"], i, q, reveal)
                 for i, q in enumerate(ai_review.questions_for_stage(pack, stage), 1)]
    else:
        status = pack_row["status"] if pack_row else ""
        note = {"pending": "AI review pack is queued — these are your own flashcards for now.",
                "generating": "AI review pack is being generated — these are your own flashcards for now.",
                "failed": f"AI review pack failed ({pack_row['error'] if pack_row else ''}) — using your flashcards."
                }.get(status, "Try to answer each question from memory, then reveal the answers.")
        body.append(ft.Text(note, size=12, color=ft.Colors.GREY_400))

    cards = parse_flashcards(chapter["recall_questions"])
    own = []
    for i, (q, a) in enumerate(cards, 1):
        ans = ft.Text(a or "(no answer written)", size=13, color=ft.Colors.GREEN_200, visible=False, selectable=True)
        reveal.append(ans)
        own.append(ft.Container(
            content=ft.Column([ft.Text(f"Q{i}. {q}", size=14, weight=ft.FontWeight.W_600, selectable=True), ans],
                              spacing=4, tight=True),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=8, padding=10,
        ))
    if own:
        if pack:
            body.append(_section_title("YOUR FLASHCARDS", ft.Colors.GREY_400))
        body += own
    elif not pack:
        body.append(ft.Text("No flashcards yet — try to explain the topic out loud, then check the summary below.",
                            color=ft.Colors.GREY_400))

    summary_controls = _pack_summary_controls(pack) if pack else [
        _section_title("ELI5 SUMMARY"),
        ft.Text(chapter["eli5"] if is_filled(chapter["eli5"], DEFAULT_ELI5) else "(empty)", size=13, selectable=True)]
    summary = ft.Container(content=ft.Column(summary_controls, spacing=6, tight=True),
                           visible=False, padding=ft.Padding.only(top=6))
    reveal.append(summary)

    def reveal_all(e):
        for ctl in reveal:
            ctl.visible = True
        e.control.visible = False
        page.update()

    def finish(remembered: bool):
        def handler(e):
            db.complete_review(review["id"], remembered=remembered)
            page.pop_dialog()
            update_desktop_wallpaper()
            if on_done:
                on_done()
        return handler

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Column([
            ft.Text(f"Review {review['review_no']} of {len(REVIEW_DAYS)}" + (" • AI deep review" if pack else ""),
                    size=12, color=REVIEW_COLOR),
            ft.Text(chapter["topic"], weight=ft.FontWeight.BOLD),
        ], spacing=2, tight=True),
        content=ft.Container(
            width=620,
            content=ft.Column([
                *body,
                ft.OutlinedButton("Show all answers & summary", icon=ft.Icons.VISIBILITY, on_click=reveal_all),
                summary,
            ], spacing=10, tight=True, scroll=ft.ScrollMode.AUTO,
                horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
        ),
        actions=[
            ft.TextButton("Later", on_click=lambda e: page.pop_dialog()),
            ft.TextButton(f"Struggled — repeat tomorrow (+{XP_REVIEW} XP)", on_click=finish(False)),
            ft.Button(f"Remembered (+{XP_REVIEW} XP)", icon=ft.Icons.CHECK, on_click=finish(True)),
        ],
    ))


def open_ai_settings(page: ft.Page, on_change=None):
    """Gemini key (kept in the Windows Credential Manager), model preference and auto-generation."""
    import ai_gemini
    import ai_review

    settings = db.get_hud_settings()
    status = ft.Text(ai_gemini.status_text(), size=13,
                     color=ft.Colors.GREEN_ACCENT if ai_gemini.is_configured() else ft.Colors.AMBER_ACCENT)
    key_f = ft.TextField(label="Gemini API key", password=True, can_reveal_password=True, dense=True,
                         hint_text="Paste a key to save or replace it (the saved key is never shown)")
    model_f = ft.TextField(label="Preferred model (optional)", dense=True,
                           value=settings.get(ai_gemini.SETTING_PREFERRED, ""),
                           hint_text="e.g. gemini-2.5-flash — empty = automatic")
    auto_cb = ft.Checkbox(label="Generate an AI review pack automatically when I master a chapter",
                          value=ai_review.auto_enabled())
    result = ft.Text("", size=12)
    missing = db.get_chapters_missing_ai_pack()

    def refresh_status():
        status.value = ai_gemini.status_text()
        status.color = ft.Colors.GREEN_ACCENT if ai_gemini.is_configured() else ft.Colors.AMBER_ACCENT

    def save(e):
        if (key_f.value or "").strip():
            ai_gemini.set_api_key(key_f.value)
            key_f.value = ""
        db.set_hud_setting(ai_gemini.SETTING_PREFERRED, (model_f.value or "").strip().removeprefix("models/"))
        ai_review.set_auto_enabled(bool(auto_cb.value))
        refresh_status()
        result.value, result.color = "Saved.", ft.Colors.GREEN_ACCENT
        ai_review.retry_pending(on_done=on_change, force=True)
        page.update()

    def remove(e):
        ai_gemini.set_api_key("")
        refresh_status()
        result.value, result.color = "Key removed from the Credential Manager.", ft.Colors.GREY_400
        page.update()

    def test(e):
        result.value, result.color = "Testing…", ft.Colors.GREY_400
        page.update()

        def work():
            ok, msg = ai_gemini.test_connection(key_f.value)
            result.value, result.color = msg, ft.Colors.GREEN_ACCENT if ok else ft.Colors.RED_ACCENT
            page.update()

        import threading
        threading.Thread(target=work, daemon=True, name="ai-test").start()

    def generate_missing(e):
        if not ai_gemini.is_configured():
            result.value, result.color = "Save an API key first.", ft.Colors.RED_ACCENT
            page.update()
            return
        for sid in missing:
            db.set_ai_pack(sid, "pending", reset_attempts=True)
        ai_review.start_generation(missing, on_change)
        result.value, result.color = f"Generating {len(missing)} pack(s) in the background…", ft.Colors.GREEN_ACCENT
        e.control.disabled = True
        page.update()

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.AUTO_AWESOME, color=REVIEW_COLOR), ft.Text("AI review settings",
                                                                                weight=ft.FontWeight.BOLD)]),
        content=ft.Container(width=560, content=ft.Column([
            status,
            key_f,
            ft.Row([ft.TextButton("Test connection", icon=ft.Icons.WIFI_TETHERING, on_click=test),
                    ft.TextButton("Remove saved key", icon=ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_300,
                                  on_click=remove)], spacing=4),
            model_f,
            auto_cb,
            ft.Button(f"Generate missing packs ({len(missing)})", icon=ft.Icons.AUTO_AWESOME,
                      on_click=generate_missing, disabled=not missing),
            result,
            ft.Text("Get a free key at Google AI Studio (aistudio.google.com → Get API key). When a pack is "
                    "generated, the chapter's journal and wrap-up are sent to Google's Gemini API; on the free "
                    "tier Google may use that content to improve its products.", size=11, color=ft.Colors.GREY_500),
        ], spacing=12, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
        actions=[ft.TextButton("Close", on_click=lambda e: (page.pop_dialog(), on_change and on_change(None))),
                 ft.Button("Save", icon=ft.Icons.CHECK, on_click=save)],
    ))


# ---------------------------------------------------------------- view
class StudyView(ft.Row):
    def __init__(self, page: ft.Page):
        super().__init__(expand=True, spacing=0, visible=False,
                         vertical_alignment=ft.CrossAxisAlignment.STRETCH)
        self.app_page = page
        self.selected_session_id = None
        self.filter = "active"
        self.pane = "journal"
        self.drafts = {}          # session_id -> {"notes", "minutes", "next_step"} of the unsent journal entry
        self.feedback = {}        # session_id -> last journal feedback message

        self.sidebar = ft.Column(spacing=8, expand=True)
        self.workspace = ft.Column(spacing=14, expand=True, scroll=ft.ScrollMode.AUTO,
                                   horizontal_alignment=ft.CrossAxisAlignment.STRETCH)
        self.controls = [
            ft.Container(content=self.sidebar, width=330, padding=15, bgcolor=ft.Colors.SURFACE_CONTAINER_LOW),
            ft.VerticalDivider(width=1, color=ft.Colors.GREY_800),
            ft.Container(content=self.workspace, expand=True,
                         padding=ft.Padding.only(left=20, right=30, top=15, bottom=30)),
        ]
        self.refresh_list()

    # ------------------------------------------------------------ data helpers
    def _chapters(self):
        chapters = db.get_study_sessions()
        if self.filter == "active":
            return chapters, [c for c in chapters if c["status"] != "Mastered" or c["reviews_due"]]
        if self.filter == "mastered":
            return chapters, [c for c in chapters if c["status"] == "Mastered"]
        return chapters, chapters

    def _selected(self, chapters):
        return next((c for c in chapters if c["id"] == self.selected_session_id), None)

    def _changed(self):
        self.refresh_list()
        update_desktop_wallpaper()

    def _update(self):
        if self.app_page:
            self.app_page.update()

    def _ai_done(self, session_id=None):
        """An AI pack finished (background thread): redraw only if it is on screen."""
        if session_id is None or (self.visible and self.selected_session_id == session_id
                                  and self.pane == "reviews"):
            self.refresh_list()

    # ------------------------------------------------------------ public (used by main.py)
    def refresh_list(self):
        ai_review.retry_pending(on_done=self._ai_done)
        chapters, visible = self._chapters()
        if self._selected(chapters) is None:
            pick = visible[0] if visible else (chapters[0] if chapters else None)
            self.selected_session_id = pick["id"] if pick else None
        self._render_sidebar(chapters, visible)
        self._render_workspace(self._selected(chapters))
        self._update()

    def select_chapter(self, session_id: int):
        self.selected_session_id = session_id
        self.refresh_list()

    # ------------------------------------------------------------ sidebar
    def _render_sidebar(self, chapters, visible):
        new_topic = ft.TextField(hint_text="New chapter / topic…", expand=True, dense=True, text_size=13)

        def add(e=None):
            topic = (new_topic.value or "").strip()
            if topic:
                self.selected_session_id = db.add_study_session(topic)
                self.filter = "active"
                self.pane = "journal"
                self._changed()

        new_topic.on_submit = add
        due = db.get_pending_reviews(until=date.today())

        controls = [
            ft.Row([ft.Icon(ft.Icons.SCHOOL, color=ft.Colors.CYAN_ACCENT, size=24),
                    ft.Text("Study Chapters", size=18, weight=ft.FontWeight.BOLD, expand=True),
                    ft.IconButton(ft.Icons.AUTO_AWESOME, icon_color=REVIEW_COLOR if ai_gemini.is_configured()
                                  else ft.Colors.GREY_500, tooltip="AI review settings (Gemini)",
                                  on_click=lambda e: open_ai_settings(self.app_page, on_change=self._ai_done))]),
            ft.Row([new_topic, ft.IconButton(ft.Icons.ADD_CIRCLE, icon_color=ft.Colors.CYAN_ACCENT,
                                             tooltip="Add chapter", on_click=add)]),
        ]
        if due:
            controls.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.REPLAY, color=ft.Colors.BLACK, size=18),
                    ft.Text(f"{len(due)} review{'s' if len(due) != 1 else ''} due — start", color=ft.Colors.BLACK,
                            weight=ft.FontWeight.BOLD, expand=True),
                ]),
                bgcolor=REVIEW_COLOR, border_radius=8, padding=10, ink=True,
                tooltip=", ".join(r["topic"] for r in due[:5]),
                on_click=lambda e: open_review_dialog(self.app_page, due[0], on_done=self._changed),
            ))
        n_active = sum(1 for c in chapters if c["status"] != "Mastered")
        n_mastered = len(chapters) - n_active
        controls.append(ft.SegmentedButton(
            segments=[ft.Segment(value="active", label=ft.Text(f"Active {n_active}", size=12, no_wrap=True)),
                      ft.Segment(value="mastered", label=ft.Text(f"Mastered {n_mastered}", size=12, no_wrap=True)),
                      ft.Segment(value="all", label=ft.Text("All", size=12, no_wrap=True))],
            selected=[self.filter], show_selected_icon=False,
            on_change=lambda e: self._set_filter(e.control.selected[0]) if e.control.selected else None,
        ))
        controls.append(ft.Divider(color=ft.Colors.GREY_800, height=1))

        tiles = [self._tile(c) for c in visible]
        if not tiles:
            tiles = [ft.Text("No chapters here yet.\nAdd one above!" if self.filter != "mastered"
                             else "Nothing mastered yet — keep going!", color=ft.Colors.GREY_500, size=13)]
        controls.append(ft.Column(tiles, spacing=6, scroll=ft.ScrollMode.AUTO, expand=True))
        self.sidebar.controls = controls

    def _set_filter(self, value):
        self.filter = value
        _, visible = self._chapters()
        if visible and self.selected_session_id not in {c["id"] for c in visible}:
            self.selected_session_id = visible[0]["id"]  # keep the editor in sync with the list
        self.refresh_list()

    def _tile(self, c):
        selected = c["id"] == self.selected_session_id
        color = STAGE_COLORS.get(c["status"], ft.Colors.GREY_400)
        if c["reviews_due"]:
            hint, hint_color = f"Review due ({c['reviews_due']})", REVIEW_COLOR
        elif c["status"] == "Mastered":
            if not c["needs_review"]:
                hint, hint_color = "No reviews (project)", ft.Colors.GREY_500
            elif c["next_review"]:
                hint, hint_color = f"Next review {date.fromisoformat(c['next_review']):%d/%m}", ft.Colors.GREY_400
            else:
                hint, hint_color = "Reviews complete", ft.Colors.GREY_500
        elif c["next_step"]:
            hint, hint_color = f"→ {c['next_step']}", ft.Colors.GREY_300
        else:
            hint, hint_color = c["source"], ft.Colors.GREY_500
        stats = f"{c['sessions']} session{'s' if c['sessions'] != 1 else ''} • {fmt_minutes(c['minutes'])}"

        return ft.Container(
            content=ft.Column([
                ft.Row([
                    ft.Text(c["topic"], size=14, weight=ft.FontWeight.BOLD if selected else ft.FontWeight.W_500,
                            expand=True, max_lines=2, overflow=ft.TextOverflow.ELLIPSIS),
                    ft.Container(
                        content=ft.Text(c["status"], size=10, color=color, weight=ft.FontWeight.BOLD),
                        border=ft.Border.all(1, color), border_radius=4,
                        padding=ft.Padding.symmetric(horizontal=4, vertical=1),
                    ),
                ]),
                ft.Text(hint, size=11, color=hint_color, max_lines=1, overflow=ft.TextOverflow.ELLIPSIS),
                ft.Text(stats, size=10, color=ft.Colors.GREY_600),
            ], spacing=2),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST if selected else ft.Colors.TRANSPARENT,
            border=ft.Border.only(left=ft.BorderSide(3, REVIEW_COLOR if c["reviews_due"] else color)),
            border_radius=8, padding=10, ink=True,
            on_click=lambda e, sid=c["id"]: self.select_chapter(sid),
        )

    # ------------------------------------------------------------ workspace
    def _render_workspace(self, ch):
        if ch is None:
            self.workspace.controls = [ft.Container(
                content=ft.Column([
                    ft.Icon(ft.Icons.MENU_BOOK_ROUNDED, size=48, color=ft.Colors.GREY_600),
                    ft.Text("Add a chapter on the left to start your study journal.", color=ft.Colors.GREY_400),
                ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                alignment=ft.Alignment.CENTER, padding=50,
            )]
            return

        sid = ch["id"]
        topic_f = ft.TextField(value=ch["topic"], label="Topic / Chapter", dense=True, expand=True, text_size=15)
        topic_f.on_blur = lambda e: self._save_field(sid, "topic", (e.control.value or "").strip() or "Untitled",
                                                     ch["topic"])
        source_dd = ft.Dropdown(
            label="Course / Source", value=ch["source"] if ch["source"] in SOURCES else None, width=200, dense=True,
            options=[ft.DropdownOption(s) for s in SOURCES + ([ch["source"]] if ch["source"] and ch["source"] not in SOURCES else [])],
            on_select=lambda e: self._save_field(sid, "source", e.control.value, ch["source"]),
        )
        if ch["source"] and ch["source"] not in SOURCES:
            source_dd.value = ch["source"]

        header = ft.Row([
            topic_f, source_dd,
            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_color=ft.Colors.RED_400, tooltip="Delete chapter",
                          on_click=lambda e: confirm_action(
                              self.app_page, "Delete chapter?",
                              f"'{ch['topic']}', its journal and its pending reviews will be removed.",
                              lambda: (db.delete_study_session(sid), self._clear_selection(), self._changed()))),
        ], spacing=10)

        pane_switch = ft.SegmentedButton(
            segments=[
                ft.Segment(value="journal", label=ft.Text(f"Journal ({ch['sessions']})"), icon=ft.Icon(ft.Icons.EDIT_NOTE)),
                ft.Segment(value="wrapup", label=ft.Text("Wrap-up"), icon=ft.Icon(ft.Icons.FACT_CHECK)),
                ft.Segment(value="reviews", label=ft.Text("Reviews" + (f" ({ch['reviews_due']} due)" if ch["reviews_due"] else "")),
                           icon=ft.Icon(ft.Icons.REPLAY)),
            ],
            selected=[self.pane], show_selected_icon=False,
            on_change=lambda e: self._set_pane(e.control.selected[0]) if e.control.selected else None,
        )
        body = {"journal": self._journal_pane, "wrapup": self._wrapup_pane, "reviews": self._reviews_pane}[self.pane](ch)
        self.workspace.controls = [header, self._stage_bar(ch), pane_switch, *body]

    def _clear_selection(self):
        self.selected_session_id = None

    def _set_pane(self, pane):
        self.pane = pane
        self.refresh_list()

    def _save_field(self, sid, field, value, old):
        if value != old:
            db.update_study_session(sid, **{field: value})
            self._changed()

    # ------------------------------------------------------------ stages
    def _stage_bar(self, ch):
        current = STUDY_STAGES.index(ch["status"]) if ch["status"] in STUDY_STAGES else 0
        pills = []
        for i, stage in enumerate(STUDY_STAGES):
            reached = i <= current
            color = STAGE_COLORS[stage]
            pills.append(ft.Container(
                content=ft.Row([ft.Icon(STAGE_ICONS[stage], size=16, color=color if reached else ft.Colors.GREY_600),
                                ft.Text(stage, size=12, weight=ft.FontWeight.BOLD if i == current else None,
                                        color=ft.Colors.WHITE if reached else ft.Colors.GREY_600)], spacing=6, tight=True),
                bgcolor=ft.Colors.with_opacity(0.18, color) if i == current else None,
                border=ft.Border.all(1, color if i == current else ft.Colors.with_opacity(0.2, ft.Colors.GREY)),
                border_radius=16, padding=ft.Padding.symmetric(horizontal=10, vertical=4),
                ink=True, tooltip=f"Set stage: {stage}",
                on_click=lambda e, s=stage: self.change_stage(ch, s),
            ))
            if i < len(STUDY_STAGES) - 1:
                pills.append(ft.Icon(ft.Icons.CHEVRON_RIGHT, size=16, color=ft.Colors.GREY_600))

        next_action = {
            "Not started": ("Start studying", "Studying", ft.Icons.PLAY_ARROW),
            "Studying": ("Ready to wrap up", "Reviewing", ft.Icons.FACT_CHECK),
            "Reviewing": (f"Mark as mastered (+{XP_STUDY} XP)", "Mastered", ft.Icons.MILITARY_TECH),
        }.get(ch["status"])
        action_btn = ft.Button(next_action[0], icon=next_action[2],
                               on_click=lambda e: self.change_stage(ch, next_action[1])) if next_action else \
            ft.Text(f"Mastered on {date.fromisoformat(ch['mastered_at']):%d/%m/%Y}" if ch["mastered_at"] else "Mastered",
                    color=ft.Colors.GREEN_ACCENT, weight=ft.FontWeight.BOLD)

        review_cb = ft.Checkbox(
            label="Spaced-repetition reviews after mastery (turn off for projects)",
            value=ch["needs_review"],
            on_change=lambda e: self._toggle_reviews(ch, bool(e.control.value)),
        )
        return ft.Container(
            content=ft.Column([
                ft.Row([ft.Row(pills, spacing=4, wrap=True), action_btn],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN, wrap=True),
                review_cb,
            ], spacing=6),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=12,
        )

    def _toggle_reviews(self, ch, on: bool):
        db.set_study_needs_review(ch["id"], on)
        pack = db.get_ai_pack(ch["id"])
        if on and ch["status"] == "Mastered" and not (pack and pack["status"] == "ready"):
            ai_review.queue_on_mastery(ch["id"], on_done=self._ai_done)
        self._changed()

    def change_stage(self, ch, stage):
        if stage == ch["status"]:
            return
        if stage == "Mastered":
            missing = [label.split("(")[0].strip() for key, label, template, _, _ in WRAP_UP_FIELDS
                       if key in ("eli5", "recall_questions") and not is_filled(ch[key], template)]
            if missing:
                confirm_action(self.app_page, "Wrap-up incomplete",
                               "These parts of the wrap-up are still empty: " + "; ".join(missing) +
                               ".\nYour reviews use them. Master the chapter anyway?",
                               lambda: self._apply_stage(ch, stage), confirm_label="Master anyway")
                return
        if ch["status"] == "Mastered":
            confirm_action(self.app_page, "Reopen chapter?",
                           f"Leaving 'Mastered' removes its +{XP_STUDY} XP and pending reviews "
                           "(you get them back when you master it again).",
                           lambda: self._apply_stage(ch, stage), confirm_label="Reopen")
            return
        self._apply_stage(ch, stage)

    def _apply_stage(self, ch, stage):
        db.set_study_status(ch["id"], stage)
        if stage == "Mastered" and ch["needs_review"]:
            ai_review.queue_on_mastery(ch["id"], on_done=self._ai_done)
        if stage == "Reviewing":
            self.pane = "wrapup"
        elif stage == "Mastered":
            self.pane = "reviews" if ch["needs_review"] else "journal"
        self._changed()

    # ------------------------------------------------------------ journal pane
    def _journal_pane(self, ch):
        sid = ch["id"]
        draft = self.drafts.setdefault(sid, {"notes": "", "minutes": 0, "next_step": ""})

        next_step_f = ft.TextField(value=ch["next_step"], hint_text="Where did you stop? What's next?",
                                   dense=True, text_size=14, border=ft.InputBorder.NONE, expand=True)
        next_step_f.on_blur = lambda e: self._save_field(sid, "next_step", (e.control.value or "").strip(),
                                                         ch["next_step"])
        stopped_card = ft.Container(
            content=ft.Row([
                ft.Icon(ft.Icons.BOOKMARK, color=ft.Colors.ORANGE_ACCENT),
                ft.Column([
                    ft.Text("WHERE I STOPPED / NEXT STEP", size=11, weight=ft.FontWeight.BOLD,
                            color=ft.Colors.ORANGE_ACCENT),
                    next_step_f,
                ], spacing=0, expand=True),
                ft.Column([
                    ft.Text(f"{ch['sessions']} sessions", size=12, color=ft.Colors.GREY_400),
                    ft.Text(fmt_minutes(ch["minutes"]), size=12, color=ft.Colors.GREY_400),
                    ft.Text(f"last: {date.fromisoformat(ch['last_studied']):%d/%m}" if ch["last_studied"] else "",
                            size=12, color=ft.Colors.GREY_400),
                ], spacing=0, horizontal_alignment=ft.CrossAxisAlignment.END),
            ], spacing=12),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.ORANGE), border_radius=10, padding=12,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.ORANGE)),
        )

        notes_f = ft.TextField(value=draft["notes"], label="What did you study? Notes, insights, doubts, code…",
                               multiline=True, min_lines=5, max_lines=14, text_size=13)
        notes_f.on_change = lambda e: draft.update(notes=e.control.value or "")
        minutes_dd = ft.Dropdown(label="Time spent", dense=True, width=150, value=str(draft["minutes"]),
                                 options=[ft.DropdownOption(key=str(m), text=fmt_minutes(m) if m else "—")
                                          for m in MINUTE_OPTIONS],
                                 on_select=lambda e: draft.update(minutes=int(e.control.value or 0)))
        date_f = ft.TextField(label="Date", value=f"{date.today():%d/%m/%Y}", dense=True, width=140)
        new_next_f = ft.TextField(label="Next step (updates the bookmark)", value=draft["next_step"],
                                  dense=True, expand=True)
        new_next_f.on_change = lambda e: draft.update(next_step=e.control.value or "")
        feedback = ft.Text(self.feedback.pop(sid, ""), size=12, color=ft.Colors.GREEN_ACCENT)

        def log(e):
            notes = (notes_f.value or "").strip()
            d = db.parse_flexible_date(date_f.value or "")
            if not notes:
                feedback.value, feedback.color = "Write something about this session first.", ft.Colors.RED_ACCENT
                self._update()
                return
            if not d:
                feedback.value, feedback.color = "Invalid date (use DD/MM/YYYY).", ft.Colors.RED_ACCENT
                self._update()
                return
            xp = db.add_journal_entry(sid, notes, minutes=int(minutes_dd.value or 0),
                                      next_step=(new_next_f.value or "").strip(), entry_date=d.isoformat())
            self.drafts.pop(sid, None)
            if xp:
                self.feedback[sid] = f"Session logged! +{xp:.0f} XP 🔥"
            elif len(notes) < db.STUDY_LOG_MIN_CHARS:
                self.feedback[sid] = f"Session logged (write {db.STUDY_LOG_MIN_CHARS}+ characters to earn XP)."
            else:
                self.feedback[sid] = "Session logged (today's XP for this chapter already earned)."
            self._changed()

        composer = ft.Container(
            content=ft.Column([
                ft.Text("NEW JOURNAL ENTRY", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_ACCENT),
                notes_f,
                ft.Row([minutes_dd, date_f, new_next_f], spacing=10),
                ft.Row([feedback, ft.Button(f"Log session (+{XP_STUDY_LOG:.0f} XP)", icon=ft.Icons.ADD,
                                            on_click=log)],
                       alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            ], spacing=10, horizontal_alignment=ft.CrossAxisAlignment.STRETCH),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=14,
        )

        entries = db.get_journal(sid)
        entry_controls = [self._entry_card(e) for e in entries] or [
            ft.Text("No entries yet. Log what you study as you go — the wrap-up comes at the end.",
                    color=ft.Colors.GREY_500, italic=True)]
        return [stopped_card, composer,
                ft.Text(f"JOURNAL ({len(entries)})", size=11, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400),
                *entry_controls]

    def _entry_card(self, entry):
        meta = fmt_day(entry["entry_date"]) + (f" • {fmt_minutes(entry['minutes'])}" if entry["minutes"] else "")
        lines = [
            ft.Row([
                ft.Text(meta, size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_200, expand=True),
                ft.IconButton(ft.Icons.EDIT, icon_size=16, tooltip="Edit entry",
                              on_click=lambda e, en=entry: self._edit_entry(en)),
                ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=16, icon_color=ft.Colors.RED_300, tooltip="Delete entry",
                              on_click=lambda e, en=entry: confirm_action(
                                  self.app_page, "Delete journal entry?", f"The entry from {fmt_day(en['entry_date'])} "
                                  "will be removed.", lambda: (db.delete_journal_entry(en["id"]), self._changed()))),
            ], spacing=0),
            ft.Text(entry["notes"], size=13, selectable=True),
        ]
        if entry["next_step"]:
            lines.append(ft.Text(f"→ {entry['next_step']}", size=12, color=ft.Colors.ORANGE_200, italic=True))
        return ft.Container(content=ft.Column(lines, spacing=4), bgcolor=ft.Colors.with_opacity(0.04, ft.Colors.WHITE),
                            border_radius=8, padding=ft.Padding.only(left=12, right=4, top=4, bottom=10))

    def _edit_entry(self, entry):
        notes_f = ft.TextField(value=entry["notes"], label="Notes", multiline=True, min_lines=5, max_lines=14)
        minutes_dd = ft.Dropdown(label="Time spent", dense=True, width=150, value=str(entry["minutes"] or 0),
                                 options=[ft.DropdownOption(key=str(m), text=fmt_minutes(m) if m else "—")
                                          for m in sorted(set(MINUTE_OPTIONS + [entry["minutes"] or 0]))])
        date_f = ft.TextField(label="Date", value=f"{date.fromisoformat(entry['entry_date']):%d/%m/%Y}",
                              dense=True, width=140)
        next_f = ft.TextField(label="Next step", value=entry["next_step"], dense=True)
        error = ft.Text("", color=ft.Colors.RED_ACCENT, size=12)

        def save(e):
            d = db.parse_flexible_date(date_f.value or "")
            if not (notes_f.value or "").strip() or not d:
                error.value = "Notes can't be empty and the date must be DD/MM/YYYY."
                self._update()
                return
            db.update_journal_entry(entry["id"], notes_f.value.strip(), int(minutes_dd.value or 0),
                                    (next_f.value or "").strip(), d.isoformat())
            self.app_page.pop_dialog()
            self._changed()

        self.app_page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Edit journal entry", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=520, content=ft.Column(
                [notes_f, ft.Row([minutes_dd, date_f], spacing=10), next_f, error],
                spacing=12, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.app_page.pop_dialog()),
                     ft.Button("Save", icon=ft.Icons.CHECK, on_click=save)],
        ))

    # ------------------------------------------------------------ wrap-up pane
    def _wrapup_pane(self, ch):
        sid = ch["id"]
        checks = []
        boxes = []
        for key, label, template, min_lines, font in WRAP_UP_FIELDS:
            filled = is_filled(ch[key], template)
            checks.append(ft.Row([
                ft.Icon(ft.Icons.CHECK_CIRCLE if filled else ft.Icons.RADIO_BUTTON_UNCHECKED, size=16,
                        color=ft.Colors.GREEN_ACCENT if filled else ft.Colors.GREY_600),
                ft.Text(label.split("(")[0].strip()[3:], size=12,
                        color=ft.Colors.WHITE if filled else ft.Colors.GREY_500),
            ], spacing=6, tight=True))
            field = ft.TextField(
                label=label, value=ch[key] if (ch[key] or "").strip() else template,
                multiline=True, min_lines=min_lines, max_lines=None, text_size=12 if font else 13,
                text_style=ft.TextStyle(font_family=font) if font else None,
            )
            field.on_blur = lambda e, k=key, old=ch[key], tpl=template: self._save_wrapup(sid, k, e.control.value, old, tpl)
            boxes.append(field)

        intro = ft.Container(
            content=ft.Column([
                ft.Text("Fill this in when you finish studying — it's your proof of understanding and what your "
                        "spaced-repetition reviews will quiz you on.", size=12, color=ft.Colors.GREY_400),
                ft.Row(checks, spacing=16, wrap=True),
            ], spacing=6),
            bgcolor=ft.Colors.with_opacity(0.06, ft.Colors.AMBER), border_radius=10, padding=12,
        )
        return [intro, *boxes]

    def _save_wrapup(self, sid, key, value, old, template):
        value = value or ""
        if value.strip() == template.strip():
            value = ""  # an untouched template is stored as empty
        if value != (old or ""):
            db.update_study_session(sid, **{key: value})
            self._changed()

    # ------------------------------------------------------------ reviews pane
    def _reviews_pane(self, ch):
        today = date.today()
        schedule_txt = ", ".join(str(d) for d in REVIEW_DAYS)
        info = ft.Text(f"After mastery you review the flashcards on day {schedule_txt}. Each review gives "
                       f"+{XP_REVIEW} XP; if you struggle, the same review repeats the next day.",
                       size=12, color=ft.Colors.GREY_400)
        if not ch["needs_review"]:
            return [info, ft.Text("Reviews are turned off for this chapter (e.g. a project). "
                                  "Tick the checkbox above to turn them on.", color=ft.Colors.GREY_500)]
        reviews = db.get_study_reviews(ch["id"])
        if ch["status"] != "Mastered" and not reviews:
            return [info, ft.Text("Reviews start once the chapter is mastered.", color=ft.Colors.GREY_500)]

        rows = [self._ai_pack_card(ch)] if ch["status"] == "Mastered" else []
        for r in reviews:
            label, color = review_status(r, today)
            pending = not r["done_date"]
            when = f"due {date.fromisoformat(r['due_date']):%d/%m/%Y}" + (
                f" • done {date.fromisoformat(r['done_date']):%d/%m/%Y}" if r["done_date"] else "")
            rows.append(ft.Container(
                content=ft.Row([
                    ft.Icon(ft.Icons.CHECK_CIRCLE if r["remembered"] else (
                        ft.Icons.REPLAY if r["done_date"] else ft.Icons.SCHEDULE), color=color, size=20),
                    ft.Text(f"Review {r['review_no']}", weight=ft.FontWeight.BOLD, width=80),
                    ft.Text(when, size=12, color=ft.Colors.GREY_400, expand=True),
                    ft.Text(label, size=12, color=color, weight=ft.FontWeight.BOLD),
                    ft.Button("Review now", icon=ft.Icons.PLAY_ARROW,
                              on_click=lambda e, rv=r: open_review_dialog(
                                  self.app_page, dict(rv, session_id=ch["id"]), on_done=self._changed))
                    if pending else ft.Container(width=0),
                ], spacing=12),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=8,
                padding=ft.Padding.symmetric(horizontal=12, vertical=6),
            ))
        # the rest of the series, if every review is done on its due date
        pending = [r for r in reviews if not r["done_date"]]
        if pending:
            last = pending[-1]
            planned = date.fromisoformat(last["due_date"])
            for n in range(last["review_no"] + 1, len(REVIEW_DAYS) + 1):
                planned += timedelta(days=REVIEW_DAYS[n - 1] - REVIEW_DAYS[n - 2])
                rows.append(ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.EVENT_OUTLINED, color=ft.Colors.GREY_600, size=20),
                        ft.Text(f"Review {n}", weight=ft.FontWeight.BOLD, width=80, color=ft.Colors.GREY_500),
                        ft.Text(f"planned ~{planned:%d/%m/%Y}", size=12, color=ft.Colors.GREY_600, expand=True),
                    ], spacing=12),
                    border=ft.Border.all(1, ft.Colors.with_opacity(0.15, ft.Colors.GREY)), border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=12, vertical=10),
                ))
        if ch["status"] == "Mastered" and not pending:
            finished = any(r["review_no"] == len(REVIEW_DAYS) and r["remembered"] for r in reviews)
            rows.append(ft.Text("🎉 All reviews complete — this one is in long-term memory." if finished else
                                "No review scheduled.", color=ft.Colors.GREEN_ACCENT if finished else ft.Colors.GREY_500))
            if not finished:
                rows.append(ft.Button("Start review schedule", icon=ft.Icons.EVENT_REPEAT,
                                      on_click=lambda e: (db.set_study_needs_review(ch["id"], True), self._changed())))
        return [info, *rows]

    def _ai_pack_card(self, ch):
        sid = ch["id"]
        pack = db.get_ai_pack(sid)
        configured = ai_gemini.is_configured()

        def regenerate(e):
            db.set_ai_pack(sid, "pending", reset_attempts=True)
            ai_review.start_generation(sid, self._ai_done)
            self.refresh_list()

        if ai_review.is_generating(sid) or (pack and pack["status"] == "generating"):
            icon, color = ft.ProgressRing(width=18, height=18, stroke_width=2), REVIEW_COLOR
            text, action = "Gemini is writing your deep review…", None
        elif pack and pack["content"]:
            content = pack["content"]
            n_q, n_g = len(content.get("questions") or []), len(content.get("gaps") or [])
            icon, color = ft.Icon(ft.Icons.AUTO_AWESOME, color=REVIEW_COLOR), REVIEW_COLOR
            text = f"AI deep review ready — {n_q} questions across {len(REVIEW_DAYS)} stages" + \
                (f", {n_g} gap(s) found in your notes" if n_g else "") + \
                (f" • {pack['model']}" if pack["model"] else "")
            if pack["status"] == "failed":
                text += f"\nLast regeneration failed: {pack['error']}"
            action = ft.TextButton("Regenerate", icon=ft.Icons.REFRESH, on_click=regenerate, disabled=not configured)
        elif not configured:
            icon, color = ft.Icon(ft.Icons.AUTO_AWESOME_OUTLINED, color=ft.Colors.GREY_500), ft.Colors.GREY_400
            text = "AI deep review: add your Gemini API key to generate harder, stage-by-stage questions."
            action = ft.TextButton("AI settings", icon=ft.Icons.SETTINGS,
                                   on_click=lambda e: open_ai_settings(self.app_page, on_change=self._ai_done))
        elif pack and pack["status"] == "failed":
            icon, color = ft.Icon(ft.Icons.ERROR_OUTLINE, color=ft.Colors.RED_ACCENT), ft.Colors.RED_ACCENT
            text = f"AI deep review failed ({pack['attempts']} attempt(s)): {pack['error']}"
            action = ft.TextButton("Retry now", icon=ft.Icons.REFRESH, on_click=regenerate)
        else:
            icon, color = ft.Icon(ft.Icons.AUTO_AWESOME_OUTLINED, color=REVIEW_COLOR), ft.Colors.GREY_300
            text = "No AI deep review for this chapter yet."
            action = ft.TextButton("Generate now", icon=ft.Icons.AUTO_AWESOME, on_click=regenerate)

        return ft.Container(
            content=ft.Row([icon, ft.Text(text, size=12, color=color, expand=True), action or ft.Container()],
                           spacing=10),
            bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.TEAL), border_radius=8,
            border=ft.Border.all(1, ft.Colors.with_opacity(0.3, ft.Colors.TEAL)),
            padding=ft.Padding.symmetric(horizontal=12, vertical=8),
        )
