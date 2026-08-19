from __future__ import annotations

import queue
import threading
import tkinter as tk
from datetime import datetime
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Callable

from .exporters import parse_satellite_list
from .models import DEFAULT_EXTENSIONS, SUPPORTED_FORMATS, ElementSetProfile, SatelliteEntry
from .satcat import SatcatRecord, SatcatSearch, search_satcat
from .service import export_profile
from .spacetrack import SpaceTrackClient, redact_space_track_url
from .storage import (
    load_profiles,
    load_satcat_cache,
    load_settings,
    save_profiles,
    save_satcat_cache,
    save_settings,
)


class SatcatBrowserDialog(tk.Toplevel):
    DISPLAY_LIMIT = 2000

    def __init__(
        self,
        parent: "KeplerSetApp",
        *,
        identity_getter: Callable[[], str],
        password_getter: Callable[[], str],
        add_callback: Callable[[list[SatcatRecord], bool], tuple[int, int]],
        log_callback: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self.title("Space-Track SATCAT Browser")
        self.geometry("1120x720")
        self.minsize(900, 600)
        self.transient(parent)

        self.identity_getter = identity_getter
        self.password_getter = password_getter
        self.add_callback = add_callback
        self.log_callback = log_callback
        self.records, self.metadata = load_satcat_cache()
        self.visible_records: dict[str, SatcatRecord] = {}
        self.worker_queue: queue.Queue[tuple[str, object]] = queue.Queue()

        self._build_ui()
        self._update_cache_status()
        self._rebuild_filter_values()
        self._apply_filters()
        self.after(100, self._drain_worker_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        cache = ttk.LabelFrame(self, text="Local SATCAT Cache")
        cache.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        cache.columnconfigure(0, weight=1)
        self.cache_status_var = tk.StringVar()
        ttk.Label(cache, textvariable=self.cache_status_var).grid(
            row=0, column=0, sticky="w", padx=8, pady=7
        )
        self.refresh_button = ttk.Button(
            cache, text="Refresh from Space-Track", command=self._refresh_satcat
        )
        self.refresh_button.grid(row=0, column=1, padx=8, pady=7)
        ttk.Label(
            cache,
            text="Space-Track recommends retrieving SATCAT no more than once per day; searches below use the local cache.",
            wraplength=850,
        ).grid(row=1, column=0, columnspan=2, sticky="w", padx=8, pady=(0, 7))

        filters = ttk.LabelFrame(self, text="Search / Filters")
        filters.grid(row=1, column=0, sticky="ew", padx=10, pady=5)
        for col in range(8):
            filters.columnconfigure(col, weight=1 if col in (1, 3, 5, 7) else 0)

        ttk.Label(filters, text="Search:").grid(row=0, column=0, sticky="e", padx=4, pady=4)
        self.search_var = tk.StringVar()
        search_entry = ttk.Entry(filters, textvariable=self.search_var)
        search_entry.grid(row=0, column=1, sticky="ew", padx=4, pady=4)
        search_entry.bind("<Return>", lambda _e: self._apply_filters())

        ttk.Label(filters, text="Object type:").grid(row=0, column=2, sticky="e", padx=4, pady=4)
        self.type_var = tk.StringVar(value="All")
        self.type_combo = ttk.Combobox(filters, textvariable=self.type_var, state="readonly")
        self.type_combo.grid(row=0, column=3, sticky="ew", padx=4, pady=4)

        ttk.Label(filters, text="Country code:").grid(row=0, column=4, sticky="e", padx=4, pady=4)
        self.country_var = tk.StringVar()
        ttk.Entry(filters, textvariable=self.country_var).grid(row=0, column=5, sticky="ew", padx=4, pady=4)

        self.on_orbit_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(filters, text="On-orbit only", variable=self.on_orbit_var).grid(
            row=0, column=6, sticky="w", padx=4, pady=4
        )
        ttk.Button(filters, text="Apply", command=self._apply_filters).grid(
            row=0, column=7, sticky="e", padx=4, pady=4
        )

        ttk.Label(filters, text="Launch years:").grid(row=1, column=0, sticky="e", padx=4, pady=4)
        years = ttk.Frame(filters)
        years.grid(row=1, column=1, sticky="ew", padx=4, pady=4)
        self.launch_from_var = tk.StringVar()
        self.launch_to_var = tk.StringVar()
        ttk.Entry(years, textvariable=self.launch_from_var, width=7).pack(side="left")
        ttk.Label(years, text=" to ").pack(side="left")
        ttk.Entry(years, textvariable=self.launch_to_var, width=7).pack(side="left")

        ttk.Label(filters, text="Inclination °:").grid(row=1, column=2, sticky="e", padx=4, pady=4)
        inc = ttk.Frame(filters)
        inc.grid(row=1, column=3, sticky="ew", padx=4, pady=4)
        self.inc_min_var = tk.StringVar()
        self.inc_max_var = tk.StringVar()
        ttk.Entry(inc, textvariable=self.inc_min_var, width=7).pack(side="left")
        ttk.Label(inc, text=" to ").pack(side="left")
        ttk.Entry(inc, textvariable=self.inc_max_var, width=7).pack(side="left")

        ttk.Label(filters, text="Period min:").grid(row=1, column=4, sticky="e", padx=4, pady=4)
        period = ttk.Frame(filters)
        period.grid(row=1, column=5, sticky="ew", padx=4, pady=4)
        self.period_min_var = tk.StringVar()
        self.period_max_var = tk.StringVar()
        ttk.Entry(period, textvariable=self.period_min_var, width=7).pack(side="left")
        ttk.Label(period, text=" to ").pack(side="left")
        ttk.Entry(period, textvariable=self.period_max_var, width=7).pack(side="left")

        ttk.Button(filters, text="Clear", command=self._clear_filters).grid(
            row=1, column=7, sticky="e", padx=4, pady=4
        )

        results_frame = ttk.LabelFrame(self, text="Catalog Results")
        results_frame.grid(row=2, column=0, sticky="nsew", padx=10, pady=5)
        results_frame.columnconfigure(0, weight=1)
        results_frame.rowconfigure(0, weight=1)

        columns = ("cat", "name", "id", "type", "country", "launch", "decay", "inc", "period")
        self.results = ttk.Treeview(
            results_frame, columns=columns, show="headings", selectmode="extended"
        )
        headings = {
            "cat": "NORAD",
            "name": "Object Name",
            "id": "Intl Designator",
            "type": "Type",
            "country": "Country",
            "launch": "Launch",
            "decay": "Decay",
            "inc": "Inclination",
            "period": "Period (min)",
        }
        widths = {
            "cat": 80,
            "name": 220,
            "id": 110,
            "type": 105,
            "country": 70,
            "launch": 90,
            "decay": 90,
            "inc": 85,
            "period": 90,
        }
        for col in columns:
            self.results.heading(col, text=headings[col])
            self.results.column(col, width=widths[col], stretch=col == "name")
        self.results.grid(row=0, column=0, sticky="nsew")
        ybar = ttk.Scrollbar(results_frame, orient="vertical", command=self.results.yview)
        ybar.grid(row=0, column=1, sticky="ns")
        xbar = ttk.Scrollbar(results_frame, orient="horizontal", command=self.results.xview)
        xbar.grid(row=1, column=0, sticky="ew")
        self.results.configure(yscrollcommand=ybar.set, xscrollcommand=xbar.set)
        self.results.bind("<Double-1>", lambda _e: self._add_selected())

        controls = ttk.Frame(self)
        controls.grid(row=3, column=0, sticky="ew", padx=10, pady=(5, 10))
        controls.columnconfigure(2, weight=1)
        self.result_status_var = tk.StringVar()
        ttk.Label(controls, textvariable=self.result_status_var).grid(row=0, column=0, sticky="w")
        ttk.Button(controls, text="Select All Shown", command=self._select_all_shown).grid(
            row=0, column=1, padx=(10, 5)
        )
        self.use_name_var = tk.BooleanVar(value=True)
        ttk.Checkbutton(
            controls, text="Use object name as alias", variable=self.use_name_var
        ).grid(row=0, column=2, sticky="e", padx=5)
        ttk.Button(controls, text="Add Selected", command=self._add_selected).grid(
            row=0, column=3, padx=5
        )
        ttk.Button(controls, text="Close", command=self.destroy).grid(row=0, column=4, padx=(5, 0))

    @staticmethod
    def _optional_int(text: str, field: str) -> int | None:
        value = text.strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be an integer.") from exc

    @staticmethod
    def _optional_float(text: str, field: str) -> float | None:
        value = text.strip()
        if not value:
            return None
        try:
            return float(value)
        except ValueError as exc:
            raise ValueError(f"{field} must be a number.") from exc

    def _criteria(self) -> SatcatSearch:
        return SatcatSearch(
            text=self.search_var.get(),
            object_type=self.type_var.get(),
            country=self.country_var.get(),
            on_orbit_only=self.on_orbit_var.get(),
            launch_year_from=self._optional_int(self.launch_from_var.get(), "Launch year from"),
            launch_year_to=self._optional_int(self.launch_to_var.get(), "Launch year to"),
            inclination_min=self._optional_float(self.inc_min_var.get(), "Minimum inclination"),
            inclination_max=self._optional_float(self.inc_max_var.get(), "Maximum inclination"),
            period_min=self._optional_float(self.period_min_var.get(), "Minimum period"),
            period_max=self._optional_float(self.period_max_var.get(), "Maximum period"),
        )

    def _apply_filters(self) -> None:
        try:
            criteria = self._criteria()
        except ValueError as exc:
            messagebox.showerror("SATCAT Filters", str(exc), parent=self)
            return

        all_matches = search_satcat(self.records, criteria, limit=None)
        total = len(all_matches)
        limited = all_matches[: self.DISPLAY_LIMIT]
        self.results.delete(*self.results.get_children())
        self.visible_records.clear()
        for record in limited:
            iid = self.results.insert(
                "",
                tk.END,
                values=(
                    record.norad_cat_id,
                    record.object_name,
                    record.object_id,
                    record.object_type,
                    record.country,
                    record.launch,
                    record.decay,
                    "" if record.inclination is None else f"{record.inclination:.2f}",
                    "" if record.period is None else f"{record.period:.2f}",
                ),
            )
            self.visible_records[iid] = record
        if total > self.DISPLAY_LIMIT:
            self.result_status_var.set(
                f"{total:,} matches; showing first {self.DISPLAY_LIMIT:,}. Narrow the filters to see others."
            )
        else:
            self.result_status_var.set(f"{total:,} match(es).")

    def _clear_filters(self) -> None:
        self.search_var.set("")
        self.type_var.set("All")
        self.country_var.set("")
        self.on_orbit_var.set(True)
        self.launch_from_var.set("")
        self.launch_to_var.set("")
        self.inc_min_var.set("")
        self.inc_max_var.set("")
        self.period_min_var.set("")
        self.period_max_var.set("")
        self._apply_filters()

    def _rebuild_filter_values(self) -> None:
        types = sorted({r.object_type for r in self.records if r.object_type})
        self.type_combo["values"] = ["All", *types]
        if self.type_var.get() not in self.type_combo["values"]:
            self.type_var.set("All")

    def _update_cache_status(self) -> None:
        if not self.records:
            self.cache_status_var.set("No local SATCAT cache. Enter Space-Track credentials and refresh once.")
            return
        fetched = self.metadata.get("fetched_at", "")
        shown = fetched
        if fetched:
            try:
                shown = datetime.fromisoformat(fetched).astimezone().strftime("%Y-%m-%d %H:%M %Z")
            except ValueError:
                pass
        self.cache_status_var.set(
            f"Cached objects: {len(self.records):,}" + (f" • Refreshed: {shown}" if shown else "")
        )

    def _refresh_satcat(self) -> None:
        identity = self.identity_getter().strip()
        password = self.password_getter()
        if not identity or not password:
            messagebox.showerror(
                "Refresh SATCAT",
                "Enter your Space-Track identity and password in the main window first.",
                parent=self,
            )
            return

        if self.metadata.get("fetched_at"):
            if not messagebox.askyesno(
                "Refresh SATCAT",
                "Space-Track recommends downloading SATCAT only once per day. Refresh the cache now?",
                parent=self,
            ):
                return

        self.refresh_button.state(["disabled"])
        self.cache_status_var.set("Authenticating and downloading current SATCAT…")

        def worker() -> None:
            try:
                client = SpaceTrackClient(identity, password)
                records, result = client.fetch_satcat_current()
                save_satcat_cache(records, result.request_url)
                self.worker_queue.put(("satcat_done", (records, result.request_url)))
            except Exception as exc:
                self.worker_queue.put(("satcat_error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_worker_queue(self) -> None:
        if not self.winfo_exists():
            return
        try:
            while True:
                kind, value = self.worker_queue.get_nowait()
                if kind == "satcat_done":
                    records, request_url = value
                    self.records = records
                    self.records, self.metadata = load_satcat_cache()
                    self.refresh_button.state(["!disabled"])
                    self._update_cache_status()
                    self._rebuild_filter_values()
                    self._apply_filters()
                    self.log_callback(
                        f"SATCAT cache refreshed: {len(self.records):,} current objects. Request: "
                        f"{redact_space_track_url(request_url)}"
                    )
                elif kind == "satcat_error":
                    self.refresh_button.state(["!disabled"])
                    self._update_cache_status()
                    messagebox.showerror("SATCAT Refresh Failed", str(value), parent=self)
        except queue.Empty:
            pass
        if self.winfo_exists():
            self.after(100, self._drain_worker_queue)

    def _select_all_shown(self) -> None:
        items = self.results.get_children()
        if items:
            self.results.selection_set(*items)

    def _add_selected(self) -> None:
        selected = self.results.selection()
        if not selected:
            messagebox.showinfo("Add from SATCAT", "Select one or more catalog objects.", parent=self)
            return
        records = [self.visible_records[iid] for iid in selected if iid in self.visible_records]
        added, skipped = self.add_callback(records, self.use_name_var.get())
        self.result_status_var.set(
            f"Added {added} object(s) to the current profile"
            + (f"; skipped {skipped} already present." if skipped else ".")
        )


class KeplerSetApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("KeplerSet 0.2 — Space-Track Element Set Builder")
        self.geometry("1040x720")
        self.minsize(860, 600)

        self.settings = load_settings()
        self.profiles = load_profiles()
        if not self.profiles:
            self.profiles = [ElementSetProfile()]
        self.current_index = 0
        self.worker_queue: queue.Queue[tuple[str, object]] = queue.Queue()

        self._build_ui()
        self._load_profile(0)
        self.after(100, self._drain_worker_queue)

    def _build_ui(self) -> None:
        self.columnconfigure(0, weight=1)
        self.rowconfigure(1, weight=1)

        credentials = ttk.LabelFrame(self, text="Space-Track Account")
        credentials.grid(row=0, column=0, sticky="ew", padx=10, pady=(10, 5))
        credentials.columnconfigure(1, weight=1)
        credentials.columnconfigure(3, weight=1)

        ttk.Label(credentials, text="Identity:").grid(row=0, column=0, padx=6, pady=6, sticky="e")
        self.identity_var = tk.StringVar(value=str(self.settings.get("identity", "")))
        ttk.Entry(credentials, textvariable=self.identity_var).grid(row=0, column=1, padx=6, pady=6, sticky="ew")
        ttk.Label(credentials, text="Password:").grid(row=0, column=2, padx=6, pady=6, sticky="e")
        self.password_var = tk.StringVar()
        ttk.Entry(credentials, textvariable=self.password_var, show="•").grid(row=0, column=3, padx=6, pady=6, sticky="ew")
        ttk.Label(credentials, text="Password is not saved.").grid(row=1, column=1, columnspan=3, padx=6, pady=(0, 6), sticky="w")

        body = ttk.Frame(self)
        body.grid(row=1, column=0, sticky="nsew", padx=10, pady=5)
        body.columnconfigure(1, weight=1)
        body.rowconfigure(0, weight=1)

        left = ttk.LabelFrame(body, text="Element Set Profiles")
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 5))
        left.rowconfigure(0, weight=1)
        self.profile_list = tk.Listbox(left, width=25, exportselection=False)
        self.profile_list.grid(row=0, column=0, columnspan=3, sticky="nsew", padx=6, pady=6)
        self.profile_list.bind("<<ListboxSelect>>", self._on_profile_select)
        ttk.Button(left, text="New", command=self._new_profile).grid(row=1, column=0, padx=3, pady=6)
        ttk.Button(left, text="Save", command=self._save_current_profile).grid(row=1, column=1, padx=3, pady=6)
        ttk.Button(left, text="Delete", command=self._delete_profile).grid(row=1, column=2, padx=3, pady=6)

        editor = ttk.LabelFrame(body, text="Profile")
        editor.grid(row=0, column=1, sticky="nsew", padx=(5, 0))
        editor.columnconfigure(1, weight=1)
        editor.rowconfigure(4, weight=1)

        ttk.Label(editor, text="Name:").grid(row=0, column=0, sticky="e", padx=6, pady=5)
        self.name_var = tk.StringVar()
        ttk.Entry(editor, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", padx=6, pady=5)

        ttk.Label(editor, text="Format:").grid(row=1, column=0, sticky="e", padx=6, pady=5)
        self.format_var = tk.StringVar()
        self.format_combo = ttk.Combobox(editor, textvariable=self.format_var, state="readonly")
        self.format_combo["values"] = [f"{key} — {label}" for key, label in SUPPORTED_FORMATS.items()]
        self.format_combo.grid(row=1, column=1, sticky="ew", padx=6, pady=5)
        self.format_combo.bind("<<ComboboxSelected>>", self._format_changed)

        ttk.Label(editor, text="Output:").grid(row=2, column=0, sticky="e", padx=6, pady=5)
        output_frame = ttk.Frame(editor)
        output_frame.grid(row=2, column=1, sticky="ew", padx=6, pady=5)
        output_frame.columnconfigure(0, weight=1)
        self.output_var = tk.StringVar()
        ttk.Entry(output_frame, textvariable=self.output_var).grid(row=0, column=0, sticky="ew")
        ttk.Button(output_frame, text="Browse…", command=self._browse_output).grid(row=0, column=1, padx=(6, 0))

        self.alias_var = tk.BooleanVar(value=True)
        self.alias_check = ttk.Checkbutton(
            editor,
            text="Apply aliases to 3LE line 0 names",
            variable=self.alias_var,
        )
        self.alias_check.grid(row=3, column=1, sticky="w", padx=6, pady=3)

        sats = ttk.Frame(editor)
        sats.grid(row=4, column=0, columnspan=2, sticky="nsew", padx=6, pady=6)
        sats.columnconfigure(0, weight=1)
        sats.rowconfigure(0, weight=1)
        self.tree = ttk.Treeview(sats, columns=("cat", "alias"), show="headings", selectmode="extended")
        self.tree.heading("cat", text="NORAD Catalog ID")
        self.tree.heading("alias", text="Alias / Display Name")
        self.tree.column("cat", width=150, anchor="e", stretch=False)
        self.tree.column("alias", width=400, anchor="w")
        self.tree.grid(row=0, column=0, columnspan=6, sticky="nsew")
        scrollbar = ttk.Scrollbar(sats, orient="vertical", command=self.tree.yview)
        scrollbar.grid(row=0, column=6, sticky="ns")
        self.tree.configure(yscrollcommand=scrollbar.set)
        ttk.Button(sats, text="Catalog…", command=self._browse_satcat).grid(row=1, column=0, padx=3, pady=6, sticky="w")
        ttk.Button(sats, text="Add…", command=self._add_satellite).grid(row=1, column=1, padx=3, pady=6, sticky="w")
        ttk.Button(sats, text="Edit…", command=self._edit_satellite).grid(row=1, column=2, padx=3, pady=6, sticky="w")
        ttk.Button(sats, text="Remove", command=self._remove_satellites).grid(row=1, column=3, padx=3, pady=6, sticky="w")
        ttk.Button(sats, text="Paste/List…", command=self._paste_list).grid(row=1, column=4, padx=3, pady=6, sticky="w")
        ttk.Button(sats, text="Import…", command=self._import_list).grid(row=1, column=5, padx=3, pady=6, sticky="w")

        bottom = ttk.Frame(self)
        bottom.grid(row=2, column=0, sticky="ew", padx=10, pady=(5, 10))
        bottom.columnconfigure(0, weight=1)
        self.status_var = tk.StringVar(value="Ready.")
        ttk.Label(bottom, textvariable=self.status_var).grid(row=0, column=0, sticky="w")
        self.export_button = ttk.Button(bottom, text="Fetch && Export", command=self._start_export)
        self.export_button.grid(row=0, column=1, padx=(8, 0))

        log_frame = ttk.LabelFrame(self, text="Activity")
        log_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 10))
        log_frame.columnconfigure(0, weight=1)
        self.log = tk.Text(log_frame, height=7, wrap="word", state="disabled")
        self.log.grid(row=0, column=0, sticky="ew", padx=6, pady=6)

        self._refresh_profile_list()

    def _refresh_profile_list(self) -> None:
        self.profile_list.delete(0, tk.END)
        for profile in self.profiles:
            self.profile_list.insert(tk.END, profile.name)
        if self.profiles:
            self.profile_list.selection_clear(0, tk.END)
            self.profile_list.selection_set(self.current_index)

    def _capture_profile(self) -> ElementSetProfile:
        fmt = self.format_var.get().split(" — ", 1)[0].strip() or "3le"
        satellites = []
        for iid in self.tree.get_children():
            cat, alias = self.tree.item(iid, "values")
            satellites.append(SatelliteEntry(int(cat), str(alias)))
        previous = self.profiles[self.current_index]
        return ElementSetProfile(
            name=self.name_var.get().strip(),
            format=fmt,
            output_path=self.output_var.get().strip(),
            satellites=satellites,
            apply_aliases=self.alias_var.get(),
            order_by=previous.order_by,
            empty_result_show=previous.empty_result_show,
        )

    def _load_profile(self, index: int) -> None:
        self.current_index = index
        p = self.profiles[index]
        self.name_var.set(p.name)
        self.format_var.set(f"{p.format} — {SUPPORTED_FORMATS[p.format]}")
        self.output_var.set(p.output_path)
        self.alias_var.set(p.apply_aliases)
        self.tree.delete(*self.tree.get_children())
        for sat in p.satellites:
            self.tree.insert("", tk.END, values=(sat.norad_cat_id, sat.alias))
        self._format_changed()
        self._refresh_profile_list()

    def _on_profile_select(self, _event=None) -> None:
        selection = self.profile_list.curselection()
        if selection and int(selection[0]) != self.current_index:
            self._load_profile(int(selection[0]))

    def _new_profile(self) -> None:
        self._save_current_profile(silent=True)
        self.profiles.append(ElementSetProfile(name=f"Element Set {len(self.profiles) + 1}"))
        self._load_profile(len(self.profiles) - 1)

    def _save_current_profile(self, silent: bool = False) -> None:
        try:
            p = self._capture_profile()
            if not p.name:
                raise ValueError("Profile name cannot be empty.")
            self.profiles[self.current_index] = p
            save_profiles(self.profiles)
            save_settings({"identity": self.identity_var.get().strip()})
            self._refresh_profile_list()
            if not silent:
                self.status_var.set("Profile saved.")
        except Exception as exc:
            if not silent:
                messagebox.showerror("Save Profile", str(exc), parent=self)

    def _delete_profile(self) -> None:
        if len(self.profiles) == 1:
            messagebox.showinfo("Delete Profile", "At least one profile must remain.", parent=self)
            return
        if not messagebox.askyesno("Delete Profile", "Delete the current profile?", parent=self):
            return
        del self.profiles[self.current_index]
        self.current_index = min(self.current_index, len(self.profiles) - 1)
        save_profiles(self.profiles)
        self._load_profile(self.current_index)

    def _format_changed(self, _event=None) -> None:
        fmt = self.format_var.get().split(" — ", 1)[0].strip()
        if fmt != "3le":
            self.alias_check.state(["disabled"])
        else:
            self.alias_check.state(["!disabled"])

    def _browse_output(self) -> None:
        fmt = self.format_var.get().split(" — ", 1)[0].strip() or "3le"
        ext = DEFAULT_EXTENSIONS.get(fmt, ".txt")
        path = filedialog.asksaveasfilename(
            parent=self,
            title="Element Set Output",
            defaultextension=ext,
            filetypes=[("Selected format", f"*{ext}"), ("All files", "*.*")],
        )
        if path:
            self.output_var.set(path)

    def _browse_satcat(self) -> None:
        SatcatBrowserDialog(
            self,
            identity_getter=lambda: self.identity_var.get(),
            password_getter=lambda: self.password_var.get(),
            add_callback=self._add_catalog_records,
            log_callback=self._append_log,
        )

    def _add_catalog_records(self, records: list[SatcatRecord], use_name: bool) -> tuple[int, int]:
        existing = {int(self.tree.item(i, "values")[0]) for i in self.tree.get_children()}
        added = 0
        skipped = 0
        for record in records:
            if record.norad_cat_id in existing:
                skipped += 1
                continue
            alias = record.object_name if use_name else ""
            self.tree.insert("", tk.END, values=(record.norad_cat_id, alias))
            existing.add(record.norad_cat_id)
            added += 1
        if added:
            self.status_var.set(f"Added {added} object(s) from SATCAT.")
        return added, skipped

    def _add_satellite(self) -> None:
        cat = simpledialog.askinteger(
            "Add Satellite", "NORAD catalog ID:", parent=self, minvalue=1, maxvalue=999_999_999
        )
        if cat is None:
            return
        if any(int(self.tree.item(i, "values")[0]) == cat for i in self.tree.get_children()):
            messagebox.showerror("Add Satellite", f"NORAD ID {cat} is already in this set.", parent=self)
            return
        alias = simpledialog.askstring("Add Satellite", "Alias/display name (optional):", parent=self) or ""
        self.tree.insert("", tk.END, values=(cat, alias.strip()))

    def _edit_satellite(self) -> None:
        selected = self.tree.selection()
        if len(selected) != 1:
            messagebox.showinfo("Edit Satellite", "Select exactly one satellite.", parent=self)
            return
        iid = selected[0]
        cat, alias = self.tree.item(iid, "values")
        new_alias = simpledialog.askstring(
            "Edit Satellite", f"Alias/display name for NORAD {cat}:", initialvalue=alias, parent=self
        )
        if new_alias is not None:
            self.tree.item(iid, values=(cat, new_alias.strip()))

    def _remove_satellites(self) -> None:
        for iid in self.tree.selection():
            self.tree.delete(iid)

    def _paste_list(self) -> None:
        dialog = tk.Toplevel(self)
        dialog.title("Paste Satellite List")
        dialog.geometry("580x420")
        dialog.transient(self)
        dialog.grab_set()
        ttk.Label(
            dialog,
            text="One satellite per line: NORAD_ID [alias]. Comma, semicolon, tab, or whitespace separators are accepted.",
            wraplength=540,
        ).pack(fill="x", padx=10, pady=10)
        text = tk.Text(dialog, wrap="none")
        text.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        def apply() -> None:
            try:
                rows = parse_satellite_list(text.get("1.0", "end"))
                existing = {int(self.tree.item(i, "values")[0]) for i in self.tree.get_children()}
                duplicates = [cat for cat, _ in rows if cat in existing]
                if duplicates:
                    raise ValueError(f"Already present: {', '.join(map(str, duplicates))}")
                for cat, alias in rows:
                    self.tree.insert("", tk.END, values=(cat, alias))
                dialog.destroy()
            except Exception as exc:
                messagebox.showerror("Paste Satellite List", str(exc), parent=dialog)

        ttk.Button(dialog, text="Add List", command=apply).pack(pady=(0, 10))

    def _import_list(self) -> None:
        path = filedialog.askopenfilename(
            parent=self,
            title="Import Satellite List",
            filetypes=[("Text/CSV", "*.txt *.csv *.lst"), ("All files", "*.*")],
        )
        if not path:
            return
        try:
            rows = parse_satellite_list(Path(path).read_text(encoding="utf-8-sig"))
            existing = {int(self.tree.item(i, "values")[0]) for i in self.tree.get_children()}
            for cat, alias in rows:
                if cat not in existing:
                    self.tree.insert("", tk.END, values=(cat, alias))
                    existing.add(cat)
        except Exception as exc:
            messagebox.showerror("Import Satellite List", str(exc), parent=self)

    def _append_log(self, text: str) -> None:
        self.log.configure(state="normal")
        self.log.insert("end", text + "\n")
        self.log.see("end")
        self.log.configure(state="disabled")
        self.status_var.set(text)

    def _start_export(self) -> None:
        identity = self.identity_var.get().strip()
        password = self.password_var.get()
        try:
            profile = self._capture_profile()
            profile.validate()
            if not identity or not password:
                raise ValueError("Enter your Space-Track identity and password.")
        except Exception as exc:
            messagebox.showerror("Fetch & Export", str(exc), parent=self)
            return

        self.profiles[self.current_index] = profile
        save_profiles(self.profiles)
        save_settings({"identity": identity})
        self.export_button.state(["disabled"])
        self._append_log(f"Starting export: {profile.name}")

        def worker() -> None:
            try:
                outcome = export_profile(
                    profile,
                    identity,
                    password,
                    progress=lambda msg: self.worker_queue.put(("log", msg)),
                )
                self.worker_queue.put(("done", outcome))
            except Exception as exc:
                self.worker_queue.put(("error", exc))

        threading.Thread(target=worker, daemon=True).start()

    def _drain_worker_queue(self) -> None:
        try:
            while True:
                kind, value = self.worker_queue.get_nowait()
                if kind == "log":
                    self._append_log(str(value))
                elif kind == "done":
                    self.export_button.state(["!disabled"])
                    self._append_log(f"Request: {redact_space_track_url(value.request_url)}")
                    messagebox.showinfo(
                        "Export Complete",
                        f"Saved {value.bytes_written:,} bytes to:\n{value.output_path}",
                        parent=self,
                    )
                elif kind == "error":
                    self.export_button.state(["!disabled"])
                    self._append_log(f"ERROR: {value}")
                    messagebox.showerror("Export Failed", str(value), parent=self)
        except queue.Empty:
            pass
        self.after(100, self._drain_worker_queue)


def main() -> None:
    app = KeplerSetApp()
    app.mainloop()


if __name__ == "__main__":
    main()
