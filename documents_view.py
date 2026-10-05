"""Documents: a lean expiration tracker. Only name, type and expiration date are required; the number
and notes are optional, encrypted, and (with a PIN) hidden until unlocked."""
import subprocess
import threading
import time
from datetime import date

import flet as ft

import database as db
from ui_helpers import confirm_action
from wallpaper import request_wallpaper_update as update_desktop_wallpaper

CATEGORY_ICONS = {
    "Identity": (ft.Icons.BADGE_OUTLINED, ft.Colors.BLUE_300),
    "Vehicle": (ft.Icons.DIRECTIONS_CAR_OUTLINED, ft.Colors.AMBER_300),
    "Home": (ft.Icons.HOME_OUTLINED, ft.Colors.PURPLE_200),
    "Health": (ft.Icons.HEALTH_AND_SAFETY_OUTLINED, ft.Colors.GREEN_300),
    "Other": (ft.Icons.DESCRIPTION_OUTLINED, ft.Colors.GREY_400),
}
STATUS_STYLE = {
    "expired": (ft.Colors.RED_ACCENT, ft.Icons.ERROR_OUTLINE),
    "soon": (ft.Colors.AMBER_ACCENT, ft.Icons.SCHEDULE),
    "ok": (ft.Colors.GREEN_ACCENT, ft.Icons.CHECK_CIRCLE_OUTLINE),
}
WARN_OPTIONS = [7, 15, 30, 60, 90, 180, 365]
UNLOCK_MINUTES = 5
CLIPBOARD_CLEAR_SECONDS = 30


# ---------------------------------------------------------------- helpers
def copy_to_windows_clipboard(text: str):
    if not text:
        return
    try:
        subprocess.run("clip", input=text.encode("utf-16"), check=True, creationflags=0x08000000)
    except Exception:
        pass


def clear_clipboard_if_unchanged(text: str):
    """Wipes the clipboard after a while (only if it still holds what we copied)."""
    try:
        cur = subprocess.run(["powershell", "-NoProfile", "-Command", "Get-Clipboard -Raw"],
                             capture_output=True, text=True, timeout=10, creationflags=0x08000000).stdout.strip()
        if cur == text.strip():
            subprocess.run("clip", input=b"", creationflags=0x08000000)
    except Exception:
        pass


def mask_number(val: str) -> str:
    clean = (val or "").strip()
    if len(clean) <= 4:
        return "••••"
    return "•" * min(8, len(clean) - 4) + clean[-4:]


def status_text(doc) -> str:
    days = doc["days_left"]
    exp = date.fromisoformat(doc["expiration_date"])
    if doc["status"] == "expired":
        return f"Expired {abs(days)} day{'s' if abs(days) != 1 else ''} ago"
    if days == 0:
        return "Expires today"
    if doc["status"] == "soon":
        return f"Expires in {days} day{'s' if days != 1 else ''}"
    return f"Valid until {exp:%d/%m/%Y}"


def type_options():
    return [ft.DropdownOption(key=t, text=f"{cat} · {t}") for cat, types in db.DOC_TYPES.items() for t, _, _ in types]


def warn_label(days: int) -> str:
    if days % 365 == 0 and days:
        return f"{days // 365} year{'s' if days > 365 else ''} before"
    if days >= 60 and days % 30 == 0:
        return f"{days // 30} months before"
    return f"{days} days before"


class _Lock:
    """Session unlock for numbers/notes when a PIN is set (re-locks after UNLOCK_MINUTES)."""

    def __init__(self):
        self.until = 0.0

    def unlocked(self) -> bool:
        return not db.has_doc_pin() or time.monotonic() < self.until

    def unlock(self):
        self.until = time.monotonic() + UNLOCK_MINUTES * 60

    def lock(self):
        self.until = 0.0


LOCK = _Lock()


def ask_pin(page: ft.Page, on_ok, title="Unlock documents"):
    """Asks for the PIN (if one is set) and calls on_ok() when it matches."""
    if LOCK.unlocked():
        on_ok()
        return
    pin_f = ft.TextField(label="PIN", password=True, can_reveal_password=True, autofocus=True, dense=True,
                         keyboard_type=ft.KeyboardType.NUMBER)
    error = ft.Text("", size=12, color=ft.Colors.RED_ACCENT)

    def submit(e=None):
        if db.check_doc_pin(pin_f.value or ""):
            LOCK.unlock()
            page.pop_dialog()
            on_ok()
        else:
            error.value = "Wrong PIN."
            pin_f.value = ""
            page.update()

    pin_f.on_submit = submit
    page.show_dialog(ft.AlertDialog(
        modal=True, title=ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE), ft.Text(title, weight=ft.FontWeight.BOLD)]),
        content=ft.Container(width=320, content=ft.Column(
            [ft.Text(f"Numbers and notes stay visible for {UNLOCK_MINUTES} minutes.", size=12,
                     color=ft.Colors.GREY_400), pin_f, error], spacing=10, tight=True)),
        actions=[ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                 ft.Button("Unlock", icon=ft.Icons.LOCK_OPEN, on_click=submit)]))


def open_renew_dialog(page: ft.Page, doc: dict, on_done=None):
    """'Renewed': records the new expiration date (and completes the renewal quest, if any)."""
    suggested = db.suggested_renewal_date(doc)
    date_f = ft.TextField(label="New expiration date (DD/MM/YYYY)", value=f"{suggested:%d/%m/%Y}", dense=True,
                          autofocus=True)
    error = ft.Text("", size=12, color=ft.Colors.RED_ACCENT)
    old = date.fromisoformat(doc["expiration_date"])

    def plus_years(n):
        def handler(e):
            try:
                new = old.replace(year=old.year + n)
            except ValueError:
                new = old.replace(year=old.year + n, day=28)
            date_f.value = f"{new:%d/%m/%Y}"
            page.update()
        return handler

    def save(e=None):
        new = db.parse_flexible_date(date_f.value or "")
        if not new:
            error.value = "Use DD/MM/YYYY."
            page.update()
            return
        if new <= date.today():
            error.value = "The new expiration date should be in the future."
            page.update()
            return
        xp = db.renew_doc(doc["id"], new.isoformat())
        page.pop_dialog()
        update_desktop_wallpaper()
        if on_done:
            on_done(xp)

    date_f.on_submit = save
    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Row([ft.Icon(ft.Icons.AUTORENEW, color=ft.Colors.GREEN_ACCENT),
                      ft.Text(f"Renewed: {doc['title']}", weight=ft.FontWeight.BOLD, expand=True)]),
        content=ft.Container(width=420, content=ft.Column([
            ft.Text(f"Previous expiration: {old:%d/%m/%Y}" + (" • renews every year" if doc["annual"] else ""),
                    size=12, color=ft.Colors.GREY_400),
            date_f,
            ft.Row([ft.OutlinedButton(f"+{n} year{'s' if n > 1 else ''}", on_click=plus_years(n)) for n in (1, 5, 10)],
                   spacing=6),
            ft.Text("If a renewal quest is open for it, it will be completed (+XP).", size=11,
                    color=ft.Colors.GREY_500),
            error,
        ], spacing=10, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
        actions=[ft.TextButton("Cancel", on_click=lambda e: page.pop_dialog()),
                 ft.Button("Save", icon=ft.Icons.CHECK, on_click=save)]))


def open_doc_summary(page: ft.Page, doc: dict, on_done=None):
    """Compact view used by the Calendar: status + 'Renewed'."""
    color, icon = STATUS_STYLE[doc["status"]]
    exp = date.fromisoformat(doc["expiration_date"])

    def renew(e):
        page.pop_dialog()
        open_renew_dialog(page, doc, on_done=lambda xp: on_done and on_done())

    page.show_dialog(ft.AlertDialog(
        title=ft.Row([ft.Icon(CATEGORY_ICONS.get(doc["category"], CATEGORY_ICONS["Other"])[0]),
                      ft.Text(doc["title"], weight=ft.FontWeight.BOLD, expand=True)]),
        content=ft.Container(width=400, content=ft.Column([
            ft.Row([ft.Icon(icon, color=color, size=18), ft.Text(status_text(doc), color=color,
                                                                 weight=ft.FontWeight.BOLD)]),
            ft.Text(f"{doc['doc_type']} • expires {exp:%d/%m/%Y}" + (" • yearly" if doc["annual"] else ""), size=13),
            ft.Text(f"Reminder starts {date.fromisoformat(doc['warn_start']):%d/%m/%Y} "
                    f"({warn_label(doc['warn_days'])})", size=12, color=ft.Colors.GREY_400),
        ], spacing=8, tight=True)),
        actions=[ft.TextButton("Close", on_click=lambda e: page.pop_dialog()),
                 ft.Button("Renewed", icon=ft.Icons.AUTORENEW, on_click=renew)]))


# ---------------------------------------------------------------- view
class DocumentsView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.AUTO, expand=True, visible=False, spacing=12)
        self.app_page = page
        self.revealed = set()   # doc ids whose number is shown
        self.feedback = ""
        self.render()

    def _update(self):
        if self.app_page:
            self.app_page.update()

    def _changed(self, message: str = ""):
        self.feedback = message
        self.render()
        update_desktop_wallpaper()

    # ------------------------------------------------------------ render
    def render(self):
        created = db.sync_renewal_quests()
        if created and not self.feedback:
            self.feedback = f"{len(created)} renewal quest{'s' if len(created) != 1 else ''} added to your Quest Log."
        docs = db.get_tracked_docs()
        attention = [d for d in docs if d["status"] != "ok"]
        good = [d for d in docs if d["status"] == "ok"]
        controls = [self._header()]
        legacy = db.count_legacy_documents()
        if legacy:
            controls.append(self._legacy_banner(legacy))
        if self.feedback:
            controls.append(ft.Container(content=ft.Text(self.feedback, color=ft.Colors.GREEN_ACCENT, size=13),
                                         padding=ft.Padding.symmetric(horizontal=20)))
            self.feedback = ""
        if not docs:
            controls.append(ft.Container(content=ft.Column([
                ft.Icon(ft.Icons.FOLDER_OPEN_OUTLINED, size=48, color=ft.Colors.GREY_600),
                ft.Text("Track what expires: CNH, passport, IPVA, insurance…", color=ft.Colors.GREY_400),
                ft.Text("Only a name, type and expiration date are needed.", size=12, color=ft.Colors.GREY_500),
            ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=8), alignment=ft.Alignment.CENTER,
                padding=40))
        if attention:
            controls.append(self._group("NEEDS ATTENTION", attention, ft.Colors.AMBER_ACCENT))
        if good:
            controls.append(self._group("ALL GOOD", good, ft.Colors.GREEN_ACCENT))
        self.controls = controls
        self._update()

    def _header(self):
        pin = db.has_doc_pin()
        lock_btn = ft.IconButton(
            ft.Icons.LOCK_OPEN if LOCK.unlocked() else ft.Icons.LOCK_OUTLINE,
            icon_color=ft.Colors.GREEN_ACCENT if LOCK.unlocked() else ft.Colors.AMBER_ACCENT,
            tooltip=("Lock now" if LOCK.unlocked() else "Unlock numbers & notes") if pin else "No PIN set",
            on_click=lambda e: self._toggle_lock(), visible=pin)
        return ft.Container(content=ft.Row([
            ft.Icon(ft.Icons.FOLDER_SHARED, color=ft.Colors.CYAN_ACCENT, size=28),
            ft.Text("Documents", size=22, weight=ft.FontWeight.BOLD, expand=True),
            lock_btn,
            ft.IconButton(ft.Icons.SETTINGS_OUTLINED, tooltip="PIN & renewal quests", on_click=lambda e: self._settings()),
            ft.Button("Add document", icon=ft.Icons.ADD, on_click=lambda e: self.open_editor()),
        ], spacing=8), padding=ft.Padding.only(left=20, right=20, top=18))

    def _toggle_lock(self):
        if LOCK.unlocked():
            LOCK.lock()
            self.revealed.clear()
            self.render()
        else:
            ask_pin(self.app_page, self._unlocked)

    def _unlocked(self):
        """Redraws with numbers available and re-hides them when the unlock window ends."""
        self.render()
        timer = threading.Timer(UNLOCK_MINUTES * 60 + 1, self._relock_if_expired)
        timer.daemon = True
        timer.start()

    def _relock_if_expired(self):
        if db.has_doc_pin() and not LOCK.unlocked():
            self.revealed.clear()
            try:
                self.render()
            except Exception:
                pass

    def _group(self, title, docs, color):
        return ft.Container(content=ft.Column(
            [ft.Text(f"{title} ({len(docs)})", size=11, weight=ft.FontWeight.BOLD, color=color),
             *[self._card(d) for d in docs]], spacing=8), padding=ft.Padding.symmetric(horizontal=20))

    def _card(self, doc):
        cicon, ccolor = CATEGORY_ICONS.get(doc["category"], CATEGORY_ICONS["Other"])
        scolor, sicon = STATUS_STYLE[doc["status"]]
        badges = [ft.Container(content=ft.Text(doc["doc_type"], size=11, color=ccolor, weight=ft.FontWeight.BOLD),
                               border=ft.Border.all(1, ccolor), border_radius=4,
                               padding=ft.Padding.symmetric(horizontal=6, vertical=1))]
        if doc["annual"]:
            badges.append(ft.Container(content=ft.Text("Yearly", size=11, color=ft.Colors.CYAN_200),
                                       border=ft.Border.all(1, ft.Colors.CYAN_200), border_radius=4,
                                       padding=ft.Padding.symmetric(horizontal=6, vertical=1)))
        info = [ft.Text(f"Reminder from {date.fromisoformat(doc['warn_start']):%d/%m/%Y} "
                        f"({warn_label(doc['warn_days'])})", size=11, color=ft.Colors.GREY_500)]
        if doc["quest_id"] and doc["status"] != "ok":
            info.append(ft.Row([ft.Icon(ft.Icons.MAP_OUTLINED, size=13, color=ft.Colors.AMBER_200),
                                ft.Text("Renewal quest in your Quest Log", size=11, color=ft.Colors.AMBER_200)],
                               spacing=4))
        if doc["has_number"]:
            info.append(self._number_row(doc))
        if doc["has_notes"]:
            info.append(self._notes_row(doc))

        renew_btn = ft.Button("Renewed", icon=ft.Icons.AUTORENEW,
                              on_click=lambda e, d=doc: open_renew_dialog(self.app_page, d, self._renewed),
                              bgcolor=ft.Colors.GREEN_ACCENT if doc["status"] != "ok" else None,
                              color=ft.Colors.BLACK if doc["status"] != "ok" else None)
        history = db.get_doc_renewals(doc["id"])
        actions = [renew_btn]
        if history:
            actions.append(ft.IconButton(ft.Icons.HISTORY, icon_size=18, tooltip="Renewal history",
                                         on_click=lambda e, d=doc, h=history: self._history(d, h)))
        actions += [
            ft.IconButton(ft.Icons.EDIT_OUTLINED, icon_size=18, tooltip="Edit",
                          on_click=lambda e, d=doc: self.open_editor(d)),
            ft.IconButton(ft.Icons.DELETE_OUTLINE, icon_size=18, icon_color=ft.Colors.RED_300, tooltip="Delete",
                          on_click=lambda e, d=doc: confirm_action(
                              self.app_page, "Delete document?",
                              f"'{d['title']}' and its renewal history will be removed permanently.",
                              lambda: (db.delete_tracked_doc(d["id"]), self._changed()))),
        ]
        return ft.Container(
            content=ft.Row([
                ft.Icon(cicon, color=ccolor, size=26),
                ft.Column([
                    ft.Row([ft.Text(doc["title"], size=15, weight=ft.FontWeight.BOLD), *badges], spacing=8, wrap=True),
                    ft.Row([ft.Icon(sicon, color=scolor, size=16),
                            ft.Text(status_text(doc), color=scolor, weight=ft.FontWeight.BOLD, size=13)], spacing=6),
                    *info,
                ], spacing=4, expand=True),
                ft.Row(actions, spacing=0),
            ], spacing=14, vertical_alignment=ft.CrossAxisAlignment.START),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST, border_radius=10, padding=14,
            border=ft.Border.only(left=ft.BorderSide(4, scolor)),
        )

    def _number_row(self, doc):
        if not LOCK.unlocked():
            return ft.Row([ft.Icon(ft.Icons.LOCK_OUTLINE, size=14, color=ft.Colors.GREY_500),
                           ft.Text("Number saved • unlock to view", size=12, color=ft.Colors.GREY_500)], spacing=6)
        number, _ = db.get_doc_secrets(doc["id"])
        shown = doc["id"] in self.revealed
        copy_btn = ft.IconButton(ft.Icons.COPY, icon_size=16, tooltip=f"Copy (clipboard clears in {CLIPBOARD_CLEAR_SECONDS}s)")
        copy_btn.on_click = lambda e, n=number, b=copy_btn: self._copy(n, b)
        return ft.Row([
            ft.Text(number if shown else mask_number(number), size=13, font_family="Consolas", selectable=shown),
            ft.IconButton(ft.Icons.VISIBILITY_OFF if shown else ft.Icons.VISIBILITY, icon_size=16,
                          tooltip="Hide" if shown else "Show", on_click=lambda e, i=doc["id"]: self._toggle_reveal(i)),
            copy_btn,
        ], spacing=0)

    def _notes_row(self, doc):
        if not LOCK.unlocked():
            return ft.Text("Notes saved • unlock to view", size=12, color=ft.Colors.GREY_500)
        _, notes = db.get_doc_secrets(doc["id"])
        return ft.Text(notes, size=12, color=ft.Colors.GREY_300, selectable=True)

    def _toggle_reveal(self, doc_id):
        self.revealed.symmetric_difference_update({doc_id})
        self.render()

    def _copy(self, number, btn):
        copy_to_windows_clipboard(number)
        btn.icon, btn.icon_color = ft.Icons.CHECK, ft.Colors.GREEN_ACCENT
        self._update()

        def restore():
            btn.icon, btn.icon_color = ft.Icons.COPY, None
            try:
                self._update()
            except Exception:
                pass

        for delay, fn, args in ((2.0, restore, ()), (CLIPBOARD_CLEAR_SECONDS, clear_clipboard_if_unchanged, (number,))):
            t = threading.Timer(delay, fn, args=args)
            t.daemon = True
            t.start()

    def _renewed(self, xp):
        self._changed(f"Renewed! +{xp:g} XP from the renewal quest 🎉" if xp else "Renewed — reminders reset.")

    def _history(self, doc, history):
        rows = [ft.Text(f"{date.fromisoformat(h['renewed_on']):%d/%m/%Y}: "
                        f"{date.fromisoformat(h['old_expiration']):%d/%m/%Y} → "
                        f"{date.fromisoformat(h['new_expiration']):%d/%m/%Y}", size=13) for h in history]
        self.app_page.show_dialog(ft.AlertDialog(
            title=ft.Text(f"Renewals: {doc['title']}", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=380, content=ft.Column(rows, spacing=6, tight=True)),
            actions=[ft.TextButton("Close", on_click=lambda e: self.app_page.pop_dialog())]))

    # ------------------------------------------------------------ editor
    def open_editor(self, doc=None):
        if doc and (doc["has_number"] or doc["has_notes"]) and not LOCK.unlocked():
            ask_pin(self.app_page, lambda: (self._unlocked(), self.open_editor(doc)), title="Unlock to edit")
            return
        editing = doc is not None
        number, notes = db.get_doc_secrets(doc["id"]) if editing else ("", "")
        first_type = db.DOC_TYPES["Identity"][1][0]
        type_dd = ft.Dropdown(label="Type", value=doc["doc_type"] if editing else first_type, dense=True,
                              options=type_options(), menu_height=360, expand=True)
        title_f = ft.TextField(label="Name (e.g. My CNH, Honda Civic IPVA)", value=doc["title"] if editing else "",
                               dense=True, autofocus=not editing)
        exp_f = ft.TextField(label="Expiration date (DD/MM/YYYY)", dense=True, expand=True,
                             value=f"{date.fromisoformat(doc['expiration_date']):%d/%m/%Y}" if editing else "")
        warn = doc["warn_days"] if editing else db.doc_type_defaults(first_type)[1]
        warn_dd = ft.Dropdown(label="Remind me", value=str(warn), dense=True, width=210,
                              options=[ft.DropdownOption(key=str(d), text=warn_label(d))
                                       for d in sorted(set(WARN_OPTIONS + [warn]))])
        annual_cb = ft.Checkbox(label="Renews every year (IPVA, licensing, IPTU, insurance…)",
                                value=doc["annual"] if editing else db.doc_type_defaults(first_type)[2])
        number_f = ft.TextField(label="Number (optional — encrypted)", value=number, dense=True,
                                password=True, can_reveal_password=True)
        notes_f = ft.TextField(label="Notes (optional — encrypted)", value=notes, dense=True, multiline=True,
                               min_lines=1, max_lines=4)
        error = ft.Text("", size=12, color=ft.Colors.RED_ACCENT)

        def on_type(e):
            _, w, ann = db.doc_type_defaults(type_dd.value)
            if str(w) not in [o.key for o in warn_dd.options]:
                warn_dd.options = [ft.DropdownOption(key=str(d), text=warn_label(d))
                                   for d in sorted(set(WARN_OPTIONS + [w]))]
            warn_dd.value, annual_cb.value = str(w), ann
            if not (title_f.value or "").strip():
                title_f.value = type_dd.value
            self._update()

        type_dd.on_select = on_type

        def save(e=None):
            title = (title_f.value or "").strip()
            exp = db.parse_flexible_date(exp_f.value or "")
            if not title or not exp:
                error.value = "A name and a valid expiration date (DD/MM/YYYY) are required."
                self._update()
                return
            fields = dict(title=title, doc_type=type_dd.value, category=db.doc_type_defaults(type_dd.value)[0],
                          expiration_date=exp.isoformat(), warn_days=int(warn_dd.value), annual=bool(annual_cb.value),
                          number=number_f.value or "", notes=notes_f.value or "")
            if editing:
                if fields["expiration_date"] == doc["expiration_date"]:
                    fields.pop("expiration_date")  # keep reminders already sent
                db.update_tracked_doc(doc["id"], **fields)
            else:
                db.add_tracked_doc(fields.pop("title"), fields.pop("doc_type"), fields.pop("expiration_date"), **fields)
            self.app_page.pop_dialog()
            self._changed("Saved.")

        self.app_page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Edit document" if editing else "Add document", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=520, content=ft.Column([
                ft.Row([type_dd]), title_f, ft.Row([exp_f, warn_dd], spacing=10), annual_cb,
                ft.Divider(height=1, color=ft.Colors.GREY_800),
                ft.Text("Optional — only if you really need it here:", size=12, color=ft.Colors.GREY_400),
                number_f, notes_f, error,
            ], spacing=12, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
            actions=[ft.TextButton("Cancel", on_click=lambda e: self.app_page.pop_dialog()),
                     ft.Button("Save", icon=ft.Icons.CHECK, on_click=save)]))

    # ------------------------------------------------------------ settings (PIN, renewal quests)
    def _settings(self):
        page = self.app_page
        has_pin = db.has_doc_pin()
        quests_cb = ft.Checkbox(label="Create a renewal quest when a document needs attention",
                                value=db.renewal_quests_enabled(),
                                on_change=lambda e: db.set_hud_setting(db.SETTING_DOC_QUESTS,
                                                                       "true" if e.control.value else "false"))
        current_f = ft.TextField(label="Current PIN", password=True, dense=True, visible=has_pin,
                                 keyboard_type=ft.KeyboardType.NUMBER)
        new_f = ft.TextField(label="New PIN (4-8 digits)", password=True, dense=True, keyboard_type=ft.KeyboardType.NUMBER)
        confirm_f = ft.TextField(label="Repeat new PIN", password=True, dense=True, keyboard_type=ft.KeyboardType.NUMBER)
        msg = ft.Text("", size=12)

        def show(text, ok):
            msg.value, msg.color = text, ft.Colors.GREEN_ACCENT if ok else ft.Colors.RED_ACCENT
            page.update()

        def save_pin(e):
            if has_pin and not db.check_doc_pin(current_f.value or ""):
                return show("Current PIN is wrong.", False)
            pin = (new_f.value or "").strip()
            if not (pin.isdigit() and 4 <= len(pin) <= 8):
                return show("The PIN must have 4 to 8 digits.", False)
            if pin != (confirm_f.value or "").strip():
                return show("The two PINs don't match.", False)
            db.set_doc_pin(pin)
            LOCK.lock()
            page.pop_dialog()
            self._changed("PIN saved — numbers and notes are now locked.")

        def remove_pin(e):
            if not db.check_doc_pin(current_f.value or ""):
                return show("Type the current PIN to remove it.", False)
            db.remove_doc_pin()
            page.pop_dialog()
            self._changed("PIN removed.")

        def forgot(e):
            page.pop_dialog()
            confirm_action(page, "Forgot the PIN?",
                           "The PIN is removed AND every saved number and note is erased (names and dates stay). "
                           "This can't be undone.",
                           lambda: (db.reset_doc_pin_and_wipe_secrets(), LOCK.lock(),
                                    self._changed("PIN reset — saved numbers and notes were erased.")),
                           confirm_label="Erase and reset")

        pin_actions = [ft.Button("Change PIN" if has_pin else "Set PIN", icon=ft.Icons.PIN, on_click=save_pin)]
        if has_pin:
            pin_actions += [ft.TextButton("Remove PIN", on_click=remove_pin),
                            ft.TextButton("Forgot PIN", on_click=forgot)]
        page.show_dialog(ft.AlertDialog(
            modal=True, title=ft.Text("Documents settings", weight=ft.FontWeight.BOLD),
            content=ft.Container(width=460, content=ft.Column([
                quests_cb,
                ft.Divider(height=1, color=ft.Colors.GREY_800),
                ft.Text("PIN lock", weight=ft.FontWeight.BOLD),
                ft.Text("Hides numbers and notes until you type the PIN (they are already encrypted on disk; the PIN "
                        "keeps them off the screen).", size=12, color=ft.Colors.GREY_400),
                current_f, new_f, confirm_f, ft.Row(pin_actions, spacing=6, wrap=True), msg,
            ], spacing=10, tight=True, horizontal_alignment=ft.CrossAxisAlignment.STRETCH)),
            actions=[ft.TextButton("Close", on_click=lambda e: (page.pop_dialog(), self.render()))]))

    # ------------------------------------------------------------ old format
    def _legacy_banner(self, count):
        def run(import_safe):
            n = db.remove_legacy_documents(import_safe_fields=import_safe)
            self._changed(f"Old documents removed — {n} imported (name, type and date only)." if import_safe
                          else "Old documents deleted.")

        return ft.Container(content=ft.Column([
            ft.Row([ft.Icon(ft.Icons.INFO_OUTLINE, color=ft.Colors.AMBER_ACCENT),
                    ft.Text(f"{count} document{'s' if count != 1 else ''} from the old format (with numbers and extra "
                            "fields) are still stored.", weight=ft.FontWeight.BOLD, expand=True)]),
            ft.Text("Import keeps only the name, type and expiration date; the old rows (numbers included) are then "
                    "deleted for good. Daily backups keep a copy for up to 14 days.", size=12, color=ft.Colors.GREY_400),
            ft.Row([
                ft.Button("Import without numbers", icon=ft.Icons.DOWNLOAD_DONE, on_click=lambda e: confirm_action(
                    self.app_page, "Import and delete old documents?",
                    "Names, types and expiration dates are imported; numbers, notes and extra fields are deleted.",
                    lambda: run(True), confirm_label="Import")),
                ft.TextButton("Delete all", icon=ft.Icons.DELETE_FOREVER, icon_color=ft.Colors.RED_300,
                              on_click=lambda e: confirm_action(
                                  self.app_page, "Delete old documents?",
                                  f"All {count} old-format documents are deleted permanently.", lambda: run(False),
                                  confirm_label="Delete all")),
            ], spacing=8),
        ], spacing=8), bgcolor=ft.Colors.with_opacity(0.08, ft.Colors.AMBER), border_radius=10, padding=14,
            margin=ft.Margin.symmetric(horizontal=20))
