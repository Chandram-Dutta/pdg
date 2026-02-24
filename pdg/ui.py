from __future__ import annotations

import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from pdg.generator import generate_report
from pdg.models import ReportDef, SectionDef, SectionState
from pdg.reports import REPORT_REGISTRY


class ReportApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Report Builder")
        self.geometry("920x700")

        self._current_report: ReportDef | None = None
        self._section_states: dict[str, SectionState] = {}
        self._csv_listboxes: dict[str, tk.Listbox] = {}
        self.template_path: Path | None = None
        self.output_path: Path | None = None

        self._build_ui()

    # ── UI construction ──────────────────────────────────────────────────

    def _build_ui(self) -> None:
        pad = {"padx": 10, "pady": 6}

        # ── report type selector ─────────────────────────────────────────
        top = ttk.Frame(self)
        top.pack(fill="x", **pad)

        ttk.Label(top, text="Report Type:", font=("Helvetica", 13, "bold")).pack(
            side="left"
        )
        self._report_var = tk.StringVar()
        report_names = [r.name for r in REPORT_REGISTRY]
        self._report_menu = ttk.OptionMenu(
            top,
            self._report_var,
            report_names[0] if report_names else "",
            *report_names,
            command=self._on_report_changed,
        )
        self._report_menu.pack(side="left", padx=8)

        # ── section notebook (populated on report change) ────────────────
        self._notebook = ttk.Notebook(self)
        self._notebook.pack(fill="both", expand=True, **pad)

        # ── output options ───────────────────────────────────────────────
        opts = ttk.LabelFrame(self, text="Output Options")
        opts.pack(fill="x", **pad)

        tpl_row = ttk.Frame(opts)
        tpl_row.pack(fill="x", padx=10, pady=4)
        ttk.Label(tpl_row, text="Template .docx (optional)").pack(side="left")
        self.template_entry = ttk.Entry(tpl_row)
        self.template_entry.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(tpl_row, text="Browse", command=self._choose_template).pack(
            side="left"
        )

        out_row = ttk.Frame(opts)
        out_row.pack(fill="x", padx=10, pady=4)
        ttk.Label(out_row, text="Output .docx").pack(side="left")
        self.output_entry = ttk.Entry(out_row)
        self.output_entry.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(out_row, text="Save As", command=self._choose_output).pack(
            side="left"
        )

        ttk.Button(self, text="Generate Report", command=self._generate).pack(
            anchor="e", padx=14, pady=10
        )
        self.status_label = ttk.Label(self, text="")
        self.status_label.pack(anchor="w", padx=12)

        # load the first report type
        if report_names:
            self._on_report_changed(report_names[0])

    def _on_report_changed(self, name: str) -> None:
        report = next((r for r in REPORT_REGISTRY if r.name == name), None)
        if not report:
            return

        self._current_report = report
        self._section_states = {s.key: SectionState() for s in report.sections}
        self._csv_listboxes.clear()

        for tab in self._notebook.tabs():
            self._notebook.forget(tab)

        for section in report.sections:
            self._add_section_tab(section)

    def _add_section_tab(self, section: SectionDef) -> None:
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text=section.key)

        ttk.Label(frame, text=section.title, font=("Helvetica", 12, "bold")).pack(
            anchor="w", padx=10, pady=(8, 2)
        )
        ttk.Label(frame, text=section.description, wraplength=820).pack(
            anchor="w", padx=10, pady=(0, 6)
        )

        if section.loading_levels:
            count = len(section.loading_levels)
            ttk.Label(
                frame,
                text=f"Upload exactly {count} CSVs (ordered {section.loading_levels[0]} → {section.loading_levels[-1]})",
                foreground="gray",
            ).pack(anchor="w", padx=10)

        btn_row = ttk.Frame(frame)
        btn_row.pack(fill="x", padx=10, pady=4)
        key = section.key
        ttk.Button(
            btn_row, text="Add CSVs", command=lambda k=key: self._add_csvs(k)
        ).pack(side="left", padx=4)
        ttk.Button(
            btn_row, text="Remove Selected", command=lambda k=key: self._remove_csvs(k)
        ).pack(side="left", padx=4)
        ttk.Button(
            btn_row, text="Clear All", command=lambda k=key: self._clear_csvs(k)
        ).pack(side="left", padx=4)

        listbox = tk.Listbox(frame, height=10, selectmode=tk.EXTENDED)
        listbox.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._csv_listboxes[key] = listbox

    # ── file helpers ─────────────────────────────────────────────────────

    def _add_csvs(self, key: str) -> None:
        paths = filedialog.askopenfilenames(
            title=f"Select CSVs for section {key}",
            filetypes=[("CSV Files", "*.csv")],
        )
        for p in paths:
            path = Path(p)
            if path not in self._section_states[key].csv_files:
                self._section_states[key].csv_files.append(path)
                self._csv_listboxes[key].insert(tk.END, str(path))

    def _remove_csvs(self, key: str) -> None:
        for idx in reversed(self._csv_listboxes[key].curselection()):
            self._csv_listboxes[key].delete(idx)
            del self._section_states[key].csv_files[idx]

    def _clear_csvs(self, key: str) -> None:
        self._section_states[key].csv_files.clear()
        self._csv_listboxes[key].delete(0, tk.END)

    def _choose_template(self) -> None:
        p = filedialog.askopenfilename(
            title="Select Word template", filetypes=[("Word", "*.docx")]
        )
        if p:
            self.template_path = Path(p)
            self.template_entry.delete(0, tk.END)
            self.template_entry.insert(0, p)

    def _choose_output(self) -> None:
        p = filedialog.asksaveasfilename(
            title="Save report as",
            defaultextension=".docx",
            filetypes=[("Word", "*.docx")],
        )
        if p:
            self.output_path = Path(p)
            self.output_entry.delete(0, tk.END)
            self.output_entry.insert(0, p)

    # ── generation ───────────────────────────────────────────────────────

    def _generate(self) -> None:
        if not self._current_report:
            messagebox.showerror("No report", "Select a report type.")
            return
        if not self.output_entry.get().strip():
            messagebox.showerror("Missing output", "Choose where to save the report.")
            return
        if not any(s.csv_files for s in self._section_states.values()):
            messagebox.showerror("No CSVs", "Add CSVs to at least one section.")
            return

        self.output_path = Path(self.output_entry.get().strip())

        try:
            generate_report(
                self._current_report,
                self._section_states,
                self.output_path,
                self.template_path,
            )
        except Exception as exc:  # noqa: BLE001
            messagebox.showerror("Generation failed", str(exc))
            return

        self.status_label.config(text=f"Saved → {self.output_path}")
        messagebox.showinfo("Done", "Report generated successfully.")
