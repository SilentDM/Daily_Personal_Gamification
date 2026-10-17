import asyncio

import flet as ft

from i18n import tr


def _noop():
    pass


def wake_ui(page: ft.Page):
    """Makes changes made from a background thread reach the screen now.

    In the desktop app Flet queues outgoing patches on an asyncio queue; a page.update() from our own
    threads (previews, AI results, reminders, the Telegram assistant) enqueues the patch but doesn't wake
    the event loop, so it only showed up after the next click. Poking the loop thread-safely sends it.
    """
    try:
        loop = page.session.connection.loop
    except Exception:
        return  # not connected (tests, fake pages)
    try:
        if asyncio.get_running_loop() is loop:
            return  # already on the event loop: it will flush by itself
    except RuntimeError:
        pass  # no loop in this thread: a background thread
    try:
        loop.call_soon_threadsafe(_noop)
    except RuntimeError:
        pass  # loop closed (app quitting)


def update_ui(page: ft.Page):
    """page.update() that also works from background threads (see wake_ui)."""
    page.update()
    wake_ui(page)


def confirm_action(page: ft.Page, title: str, message: str, on_confirm, confirm_label: str = None,
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
            ft.TextButton(tr("Cancel"), on_click=cancelled),
            ft.Button(confirm_label or tr("Delete"), icon=ft.Icons.DELETE_OUTLINE, color=ft.Colors.RED_300, on_click=confirmed),
        ],
    ))
