import flet as ft
import json
import subprocess
from datetime import datetime, date
import database as db
from wallpaper import update_desktop_wallpaper

CATEGORIES = ["All", "Identity", "Vehicles", "Housing & Finance", "Other"]

DOC_TYPE_PRESETS = {
    "Identity": ["CPF", "RG / CIN", "Passaporte", "Título de Eleitor", "Certidão", "Outro"],
    "Vehicles": ["CNH", "CRLV / Carro", "CRLV / Moto", "Seguro Auto", "Outro"],
    "Housing & Finance": ["IPTU", "Contrato de Aluguel", "Seguro Residencial", "Escritura", "Outro"],
    "Other": ["Cartão de Vacina", "Exame Médico", "Certificado", "Outro"]
}

CATEGORY_COLORS = {
    "Identity": ft.Colors.BLUE_400,
    "Vehicles": ft.Colors.AMBER_400,
    "Housing & Finance": ft.Colors.PURPLE_300,
    "Other": ft.Colors.GREY_400
}

def copy_to_windows_clipboard(text: str):
    """Native Windows clipboard utility - 100% synchronous and zero dependencies."""
    if not text:
        return
    try:
        subprocess.run("clip", input=text.encode("utf-16"), check=True, creationflags=0x08000000)
    except Exception:
        try:
            import tkinter as tk
            r = tk.Tk()
            r.withdraw()
            r.clipboard_clear()
            r.clipboard_append(text)
            r.update()
            r.destroy()
        except Exception:
            pass

def parse_flexible_date(date_str: str):
    """Parses date string supporting dd-mm-yy, dd-mm-yyyy, dd/mm/yy, yyyy-mm-dd."""
    if not date_str or not date_str.strip():
        return None
    clean = date_str.strip().replace("/", "-")
    for fmt in ("%d-%m-%y", "%d-%m-%Y", "%Y-%m-%d"):
        try:
            return datetime.strptime(clean, fmt).date()
        except ValueError:
            continue
    return None

def format_to_dd_mm_yy(date_str: str) -> str:
    """Converts any recognized date string to dd-mm-yy format."""
    d = parse_flexible_date(date_str)
    if d:
        return d.strftime("%d-%m-%y")
    return date_str.strip()

def mask_number(val: str) -> str:
    clean = val.strip()
    if not clean:
        return ""
    if len(clean) <= 4:
        return "••••"
    visible = 3 if len(clean) > 8 else 2
    return clean[:visible] + "•" * (len(clean) - visible * 2) + clean[-visible:]

class DocumentsView(ft.Column):
    def __init__(self, page: ft.Page):
        super().__init__(scroll=ft.ScrollMode.AUTO, expand=True, visible=False)
        self.app_page = page
        self.current_filter = "All"
        self.unmasked_doc_ids = set()

        # Inline Editor State
        self.show_editor = False
        self.editing_doc_id = None
        self.custom_fields = []

        # Form controls with dd-mm-yy labels
        self.cat_dropdown = ft.Dropdown(
            label="Category",
            value="Identity",
            options=[ft.DropdownOption(c) for c in CATEGORIES if c != "All"],
            dense=True,
            width=200
        )
        self.type_dropdown = ft.Dropdown(
            label="Document Type",
            value="CPF",
            options=[ft.DropdownOption(t) for t in DOC_TYPE_PRESETS["Identity"]],
            dense=True,
            width=200
        )
        self.title_input = ft.TextField(label="Title / Name * (Required)", hint_text="e.g. Minha CNH, Civic 2020", dense=True, expand=True)
        self.number_input = ft.TextField(label="Main Document Number / Code (Optional)", dense=True, expand=True)
        self.issue_input = ft.TextField(label="Issue Date (DD-MM-YY, Optional)", hint_text="e.g. 14-05-22", dense=True, width=240)
        self.expiration_input = ft.TextField(label="Expiration Date (DD-MM-YY, Optional)", hint_text="e.g. 20-11-26", dense=True, width=240)
        self.notes_input = ft.TextField(label="General Notes & Emergency Instructions (Optional)", multiline=True, min_lines=2, max_lines=4, dense=True)

        def on_cat_change(e):
            types = DOC_TYPE_PRESETS.get(self.cat_dropdown.value, ["Outro"])
            self.type_dropdown.options = [ft.DropdownOption(t) for t in types]
            self.type_dropdown.value = types[0]
            if self.app_page:
                self.app_page.update()

        self.cat_dropdown.on_select = on_cat_change
        self.render()

    def set_filter(self, cat: str):
        self.current_filter = cat
        self.render()

    def toggle_mask(self, doc_id: int):
        if doc_id in self.unmasked_doc_ids:
            self.unmasked_doc_ids.remove(doc_id)
        else:
            self.unmasked_doc_ids.add(doc_id)
        self.render()

    def handle_copy(self, val: str, btn: ft.IconButton):
        copy_to_windows_clipboard(val)
        btn.icon = ft.Icons.CHECK
        btn.icon_color = ft.Colors.GREEN_ACCENT
        if self.app_page:
            self.app_page.update()

    def delete_doc(self, doc_id: int):
        db.delete_document(doc_id)
        if self.editing_doc_id == doc_id:
            self.show_editor = False
        self.render()
        update_desktop_wallpaper()

    def open_create_studio(self, e=None):
        self.show_editor = True
        self.editing_doc_id = None
        self.custom_fields = []

        self.cat_dropdown.value = "Identity"
        self.type_dropdown.options = [ft.DropdownOption(t) for t in DOC_TYPE_PRESETS["Identity"]]
        self.type_dropdown.value = "CPF"
        self.title_input.value = ""
        self.title_input.error_text = None
        self.number_input.value = ""
        self.issue_input.value = ""
        self.expiration_input.value = ""
        self.notes_input.value = ""
        self.render()

    def open_edit_studio(self, d_data):
        self.show_editor = True
        self.editing_doc_id = d_data[0]

        self.cat_dropdown.value = d_data[1]
        types = DOC_TYPE_PRESETS.get(d_data[1], ["Outro"])
        self.type_dropdown.options = [ft.DropdownOption(t) for t in types]
        self.type_dropdown.value = d_data[2]
        self.title_input.value = d_data[3]
        self.title_input.error_text = None
        self.number_input.value = d_data[4] or ""
        self.issue_input.value = format_to_dd_mm_yy(d_data[6]) if d_data[6] else ""
        self.expiration_input.value = format_to_dd_mm_yy(d_data[7]) if d_data[7] else ""
        self.notes_input.value = d_data[8] or ""

        try:
            self.custom_fields = json.loads(d_data[9]) if (len(d_data) > 9 and d_data[9]) else []
        except Exception:
            self.custom_fields = []

        self.render()

    def cancel_studio(self, e=None):
        self.show_editor = False
        self.editing_doc_id = None
        self.render()

    def add_custom_field(self, e=None):
        self.custom_fields.append({"label": "", "value": ""})
        self.render()

    def remove_custom_field(self, idx: int):
        if 0 <= idx < len(self.custom_fields):
            self.custom_fields.pop(idx)
            self.render()

    def save_studio(self, e=None):
        title = self.title_input.value.strip()
        doc_num = self.number_input.value.strip()

        if not title:
            self.title_input.error_text = "Title / Name is required"
            if self.app_page:
                self.app_page.update()
            return
        else:
            self.title_input.error_text = None

        # Clean custom fields
        clean_fields = [
            {"label": f["label"].strip(), "value": f["value"].strip()} 
            for f in self.custom_fields 
            if f["label"].strip() or f["value"].strip()
        ]
        extra_fields_json = json.dumps(clean_fields)

        # Standardize dates
        issue_clean = format_to_dd_mm_yy(self.issue_input.value) if self.issue_input.value.strip() else ""
        exp_clean = format_to_dd_mm_yy(self.expiration_input.value) if self.expiration_input.value.strip() else ""

        if self.editing_doc_id is not None:
            db.update_document(
                doc_id=self.editing_doc_id,
                category=self.cat_dropdown.value,
                doc_type=self.type_dropdown.value,
                title=title,
                doc_number=doc_num,
                secondary_info="",
                issue_date=issue_clean,
                expiration_date=exp_clean,
                notes=self.notes_input.value.strip(),
                extra_fields=extra_fields_json
            )
        else:
            db.add_document(
                category=self.cat_dropdown.value,
                doc_type=self.type_dropdown.value,
                title=title,
                doc_number=doc_num,
                secondary_info="",
                issue_date=issue_clean,
                expiration_date=exp_clean,
                notes=self.notes_input.value.strip(),
                extra_fields=extra_fields_json
            )

        self.show_editor = False
        self.editing_doc_id = None
        self.render()
        update_desktop_wallpaper()

    def render(self):
        self.controls.clear()
        docs = db.get_documents(self.current_filter)
        expiring = db.get_expiring_documents(days_ahead=60)
        today = date.today()

        # 1. Header Banner
        urgent_count = sum(1 for _, _, _, days in expiring if days <= 30)
        warning_count = len(expiring) - urgent_count

        stats_items = [
            ft.Row([
                ft.Icon(ft.Icons.FOLDER_SPECIAL, color=ft.Colors.CYAN_ACCENT, size=30),
                ft.Column([
                    ft.Text("Personal Documents Vault", size=18, weight=ft.FontWeight.BOLD),
                    ft.Text(f"{len(docs)} documents registered securely in AppData", size=12, color=ft.Colors.GREY_400)
                ], spacing=2)
            ])
        ]

        if expiring:
            alert_color = ft.Colors.RED_ACCENT if urgent_count > 0 else ft.Colors.AMBER_ACCENT
            alert_txt = f"{urgent_count} Urgent (<30d)" if urgent_count > 0 else f"{warning_count} Expiring soon"
            stats_items.append(
                ft.Container(
                    content=ft.Row([
                        ft.Icon(ft.Icons.WARNING_AMBER_ROUNDED, color=alert_color, size=18),
                        ft.Text(f"Attention: {alert_txt}", color=alert_color, size=12, weight=ft.FontWeight.BOLD)
                    ], spacing=6),
                    bgcolor=ft.Colors.with_opacity(0.12, alert_color),
                    border=ft.Border.all(1, alert_color),
                    border_radius=8,
                    padding=ft.Padding.symmetric(horizontal=10, vertical=6)
                )
            )

        header_banner = ft.Container(
            content=ft.Row(stats_items, alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
            border_radius=12,
            padding=15,
            margin=ft.Margin.symmetric(horizontal=20, vertical=10)
        )
        self.controls.append(header_banner)

        # 2. Filter Bar & Add Button
        filter_buttons = []
        for cat in CATEGORIES:
            is_active = (cat == self.current_filter)
            filter_buttons.append(
                ft.Button(
                    content=cat,
                    style=ft.ButtonStyle(
                        bgcolor=ft.Colors.CYAN_ACCENT if is_active else ft.Colors.SURFACE_CONTAINER_HIGH,
                        color=ft.Colors.BLACK if is_active else ft.Colors.WHITE
                    ),
                    on_click=lambda e, c=cat: self.set_filter(c)
                )
            )

        action_bar = ft.Container(
            content=ft.Row([
                ft.Row(filter_buttons, spacing=8),
                ft.Button(
                    content="Add Document",
                    icon=ft.Icons.ADD_CARD,
                    on_click=self.open_create_studio
                )
            ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
            padding=ft.Padding.symmetric(horizontal=20, vertical=5)
        )
        self.controls.append(action_bar)

        # 3. INLINE DOCUMENT STUDIO
        if self.show_editor:
            custom_field_rows = []
            for i, field_data in enumerate(self.custom_fields):
                lbl_field = ft.TextField(
                    label="Field Title / Label",
                    hint_text="e.g. Placa, Renavam, SSP/SP...",
                    value=field_data["label"],
                    width=260,
                    dense=True,
                    on_change=lambda e, idx=i: self.custom_fields[idx].update({"label": e.control.value})
                )
                val_field = ft.TextField(
                    label="Value",
                    hint_text="e.g. ABC-1234, 123456789...",
                    value=field_data["value"],
                    expand=True,
                    dense=True,
                    on_change=lambda e, idx=i: self.custom_fields[idx].update({"value": e.control.value})
                )
                del_btn = ft.IconButton(
                    icon=ft.Icons.DELETE_OUTLINE,
                    icon_color=ft.Colors.RED_400,
                    tooltip="Remove Field",
                    on_click=lambda e, idx=i: self.remove_custom_field(idx)
                )
                custom_field_rows.append(ft.Row([lbl_field, val_field, del_btn], spacing=10))

            editor_card = ft.Container(
                content=ft.Column([
                    ft.Row([
                        ft.Row([
                            ft.Icon(ft.Icons.EDIT_DOCUMENT if self.editing_doc_id else ft.Icons.ADD_CARD, color=ft.Colors.CYAN_ACCENT),
                            ft.Text("Edit Document" if self.editing_doc_id else "Add New Document", size=16, weight=ft.FontWeight.BOLD, color=ft.Colors.CYAN_ACCENT)
                        ], spacing=8),
                        ft.IconButton(ft.Icons.CLOSE, icon_color=ft.Colors.GREY_400, on_click=self.cancel_studio)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Divider(color=ft.Colors.GREY_800, height=1),
                    ft.Row([self.cat_dropdown, self.type_dropdown, self.title_input], spacing=10),
                    self.number_input,
                    ft.Row([self.issue_input, self.expiration_input], spacing=10),
                    ft.Divider(color=ft.Colors.GREY_800, height=1),
                    ft.Row([
                        ft.Text("Extra Information & Custom Fields (Optional):", size=13, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_300),
                        ft.Button(content="Add Field", icon=ft.Icons.ADD, on_click=self.add_custom_field)
                    ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN),
                    ft.Column(custom_field_rows, spacing=8) if custom_field_rows else ft.Text("No extra fields added. Click '+ Add Field' to store Placa, Renavam, Pix, etc.", color=ft.Colors.GREY_500, size=12, italic=True),
                    ft.Divider(color=ft.Colors.GREY_800, height=1),
                    self.notes_input,
                    ft.Row([
                        ft.Button(content="Save Document", icon=ft.Icons.CHECK, on_click=self.save_studio),
                        ft.Button(content="Cancel", on_click=self.cancel_studio)
                    ], spacing=10)
                ], spacing=10),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border=ft.Border.all(1, ft.Colors.CYAN_ACCENT),
                border_radius=12,
                padding=20,
                margin=ft.Margin.symmetric(horizontal=20, vertical=10)
            )
            self.controls.append(editor_card)

        # 4. Document Cards List
        if not docs:
            self.controls.append(
                ft.Container(
                    content=ft.Column([
                        ft.Icon(ft.Icons.DESCRIPTION_OUTLINED, size=48, color=ft.Colors.GREY_600),
                        ft.Text(f"No documents registered in '{self.current_filter}'. Click 'Add Document' above!", color=ft.Colors.GREY_500, size=14)
                    ], horizontal_alignment=ft.CrossAxisAlignment.CENTER, spacing=10),
                    alignment=ft.Alignment.CENTER,
                    padding=60
                )
            )

        cards_column = ft.Column(spacing=8)

        for d in docs:
            doc_id = d[0]
            category = d[1]
            doc_type = d[2]
            title = d[3]
            doc_num = d[4] or ""
            issue_d = d[6] or ""
            exp_d = d[7] or ""
            notes = d[8] or ""
            extra_fields_raw = d[9] if len(d) > 9 else "[]"

            is_unmasked = (doc_id in self.unmasked_doc_ids)
            display_num = doc_num if is_unmasked else mask_number(doc_num)
            cat_color = CATEGORY_COLORS.get(category, ft.Colors.GREY_400)

            # Expiration Status Badge (dd-mm-yy aware)
            status_chip = None
            if exp_d and exp_d.strip():
                exp_date = parse_flexible_date(exp_d)
                if exp_date:
                    delta_days = (exp_date - today).days
                    is_passport = ("passaporte" in doc_type.lower() or "passport" in doc_type.lower())

                    if delta_days < 0:
                        status_chip = ft.Container(
                            content=ft.Text(f"Expired {abs(delta_days)}d ago", size=11, color=ft.Colors.RED_ACCENT, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.RED),
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2)
                        )
                    elif delta_days <= 30:
                        status_chip = ft.Container(
                            content=ft.Text(f"Expires in {delta_days}d!", size=11, color=ft.Colors.RED_400, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.RED),
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2)
                        )
                    elif delta_days <= 60 or (is_passport and delta_days <= 180):
                        label = f"Passport: {delta_days}d left (<6m)" if is_passport and delta_days <= 180 else f"Expires in {delta_days}d"
                        status_chip = ft.Container(
                            content=ft.Text(label, size=11, color=ft.Colors.AMBER_ACCENT, weight=ft.FontWeight.BOLD),
                            bgcolor=ft.Colors.with_opacity(0.15, ft.Colors.AMBER),
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2)
                        )
                    else:
                        status_chip = ft.Container(
                            content=ft.Text(f"Valid ({delta_days}d left)", size=11, color=ft.Colors.GREEN_ACCENT),
                            bgcolor=ft.Colors.with_opacity(0.12, ft.Colors.GREEN),
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2)
                        )

            # Main Number Row
            number_row_controls = []
            if doc_num:
                copy_btn = ft.IconButton(icon=ft.Icons.COPY_ALL_ROUNDED, icon_color=ft.Colors.CYAN_ACCENT, icon_size=18, tooltip="Copy Main Number")
                copy_btn.on_click = lambda e, val=doc_num, b=copy_btn: self.handle_copy(val, b)

                mask_btn = ft.IconButton(
                    icon=ft.Icons.VISIBILITY if is_unmasked else ft.Icons.VISIBILITY_OFF,
                    icon_color=ft.Colors.GREY_400,
                    icon_size=18,
                    tooltip="Toggle Privacy Mask",
                    on_click=lambda e, did=doc_id: self.toggle_mask(did)
                )
                number_row_controls.extend([
                    ft.Text(display_num, size=16, weight=ft.FontWeight.W_500, font_family="Consolas"),
                    copy_btn,
                    mask_btn
                ])

            # Dates row formatted as dd-mm-yy
            details_items = []
            if issue_d:
                details_items.append(ft.Text(f"Emitted: {format_to_dd_mm_yy(issue_d)}", size=11, color=ft.Colors.GREY_500))
            if exp_d:
                details_items.append(ft.Text(f"Expires: {format_to_dd_mm_yy(exp_d)}", size=11, color=ft.Colors.GREY_500))

            if details_items:
                if number_row_controls:
                    number_row_controls.append(ft.VerticalDivider(width=20))
                number_row_controls.extend(details_items)

            # Custom Fields with Copy Buttons
            custom_chips = []
            try:
                fields_list = json.loads(extra_fields_raw) if extra_fields_raw else []
                for field in fields_list:
                    lbl = field.get("label", "")
                    val = field.get("value", "")
                    if lbl or val:
                        field_copy_btn = ft.IconButton(icon=ft.Icons.COPY, icon_size=14, icon_color=ft.Colors.CYAN_ACCENT, tooltip=f"Copy {lbl}")
                        field_copy_btn.on_click = lambda e, v=val, b=field_copy_btn: self.handle_copy(v, b)

                        custom_chips.append(
                            ft.Container(
                                content=ft.Row([
                                    ft.Text(f"{lbl}:", size=12, weight=ft.FontWeight.BOLD, color=ft.Colors.GREY_400),
                                    ft.Text(val, size=12, weight=ft.FontWeight.W_500, font_family="Consolas"),
                                    field_copy_btn
                                ], spacing=4, tight=True),
                                bgcolor=ft.Colors.with_opacity(0.05, ft.Colors.WHITE),
                                border=ft.Border.all(1, ft.Colors.GREY_800),
                                border_radius=6,
                                padding=ft.Padding.only(left=8, right=4, top=2, bottom=2)
                            )
                        )
            except Exception:
                pass

            card_content = [
                ft.Row([
                    ft.Row([
                        ft.Container(
                            content=ft.Text(doc_type, size=11, weight=ft.FontWeight.BOLD, color=cat_color),
                            border=ft.Border.all(1, cat_color),
                            border_radius=4,
                            padding=ft.Padding.symmetric(horizontal=6, vertical=2)
                        ),
                        ft.Text(title, size=15, weight=ft.FontWeight.BOLD),
                        status_chip if status_chip else ft.Container()
                    ], spacing=10),
                    ft.Row([
                        ft.IconButton(
                            icon=ft.Icons.EDIT_OUTLINED,
                            icon_size=18,
                            icon_color=ft.Colors.GREY_400,
                            tooltip="Edit Document",
                            on_click=lambda e, d_data=d: self.open_edit_studio(d_data)
                        ),
                        ft.IconButton(
                            icon=ft.Icons.DELETE_OUTLINE,
                            icon_size=18,
                            icon_color=ft.Colors.RED_400,
                            tooltip="Delete Document",
                            on_click=lambda e, did=doc_id: self.delete_doc(did)
                        )
                    ], spacing=0)
                ], alignment=ft.MainAxisAlignment.SPACE_BETWEEN)
            ]

            if number_row_controls:
                card_content.append(ft.Row(number_row_controls, spacing=5))
            if custom_chips:
                card_content.append(ft.Row(custom_chips, spacing=8, wrap=True))
            if notes:
                card_content.append(ft.Text(notes, size=12, color=ft.Colors.GREY_400, italic=True))

            card = ft.Container(
                content=ft.Column(card_content, spacing=6),
                bgcolor=ft.Colors.SURFACE_CONTAINER_HIGHEST,
                border_radius=8,
                padding=12,
                margin=ft.Margin.symmetric(horizontal=20, vertical=3)
            )
            cards_column.controls.append(card)

        self.controls.append(cards_column)

        if self.app_page:
            self.app_page.update()