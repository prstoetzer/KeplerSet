from __future__ import annotations

import sys
from pathlib import Path
from typing import Any

from .paths import user_documents_dir


def _normalized_filetypes(filetypes: Any) -> Any:
    if sys.platform != "darwin" or not filetypes:
        return filetypes
    normalized = []
    for label, pattern in filetypes:
        if pattern == "*.*":
            pattern = "*"
        normalized.append((label, pattern))
    return normalized


def _save_dialog_options(options: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(options)
    parent = prepared.get("parent")
    raw_output = ""
    if parent is not None:
        output_var = getattr(parent, "output_var", None)
        getter = getattr(output_var, "get", None)
        if callable(getter):
            raw_output = str(getter()).strip()

    current = Path(raw_output).expanduser() if raw_output else None
    if "initialdir" not in prepared:
        if current is not None and current.is_absolute() and current.parent.exists():
            prepared["initialdir"] = str(current.parent)
        else:
            prepared["initialdir"] = str(user_documents_dir())
    if "initialfile" not in prepared:
        if current is not None and current.name:
            prepared["initialfile"] = current.name
        else:
            ext = str(prepared.get("defaultextension", ".txt"))
            prepared["initialfile"] = "elements" + (ext if ext.startswith(".") else f".{ext}")

    if "filetypes" in prepared:
        prepared["filetypes"] = _normalized_filetypes(prepared["filetypes"])
    return prepared


def _open_dialog_options(options: dict[str, Any]) -> dict[str, Any]:
    prepared = dict(options)
    prepared.setdefault("initialdir", str(user_documents_dir()))
    if "filetypes" in prepared:
        prepared["filetypes"] = _normalized_filetypes(prepared["filetypes"])
    return prepared


def install_dialog_fixes() -> None:
    """Wrap Tk file dialogs with desktop-safe defaults.

    Tk uses the native save/open panels on macOS. The wrapper supplies an
    explicit user Documents starting directory, carries the current output file
    into Save As, normalizes the Unix all-files pattern, and retries without
    filters if a bundled Tcl/Tk rejects the filter specification.
    """
    import tkinter as tk
    from tkinter import filedialog

    if getattr(filedialog, "_keplerset_fixed", False):
        return

    original_save = filedialog.asksaveasfilename
    original_open = filedialog.askopenfilename

    def save_as(**options: Any) -> str:
        prepared = _save_dialog_options(options)
        try:
            return original_save(**prepared)
        except tk.TclError:
            prepared.pop("filetypes", None)
            return original_save(**prepared)

    def open_file(**options: Any) -> str:
        prepared = _open_dialog_options(options)
        try:
            return original_open(**prepared)
        except tk.TclError:
            prepared.pop("filetypes", None)
            return original_open(**prepared)

    filedialog.asksaveasfilename = save_as
    filedialog.askopenfilename = open_file
    filedialog._keplerset_fixed = True


def main() -> None:
    install_dialog_fixes()
    from .gui import main as gui_main

    gui_main()
