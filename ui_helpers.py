import flet as ft


def confirm_action(page: ft.Page, title: str, message: str, on_confirm, confirm_label: str = "Delete",
                   on_cancel=None):
    """Shows a Yes/No dialog and runs on_confirm() only if the user confirms (on_cancel() otherwise)."""
    def close(e=None):
        page.pop_dialog()

    def cancelled(e):
        close()
        if on_cancel:
            on_cancel()

    def confirmed(e):
        close()
        on_confirm()

    page.show_dialog(ft.AlertDialog(
        modal=True,
        title=ft.Text(title, weight=ft.FontWeight.BOLD),
        content=ft.Text(message),
        actions=[
            ft.TextButton("Cancel", on_click=cancelled),
            ft.Button(confirm_label, icon=ft.Icons.DELETE_OUTLINE, color=ft.Colors.RED_300, on_click=confirmed),
        ],
    ))
