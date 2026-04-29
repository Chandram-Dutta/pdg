from __future__ import annotations

import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, simpledialog, ttk

from pdg.analysis import analyze_section
from pdg.generator import generate_report
from pdg.models import ReportDef, SectionDef, SectionState
from pdg.preview import render_report_markdown
from pdg.reports import REPORT_REGISTRY


class ReportApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Report Builder")
        self.geometry("1024x900")

        self._current_report: ReportDef | None = None
        self._section_states: dict[str, SectionState] = {}
        self._csv_listboxes: dict[str, tk.Listbox] = {}
        self.template_path: Path | None = None
        self.output_path: Path | None = None

        # analysis widgets keyed by section key
        self._analysis_texts: dict[str, tk.Text] = {}
        self._analyze_btns: dict[str, ttk.Button] = {}
        self._approve_btns: dict[str, ttk.Button] = {}
        self._disapprove_btns: dict[str, ttk.Button] = {}
        self._status_labels: dict[str, ttk.Label] = {}

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

        action_row = ttk.Frame(self)
        action_row.pack(anchor="e", padx=14, pady=10)
        ttk.Button(action_row, text="Preview", command=self._preview).pack(
            side="left", padx=(0, 8)
        )
        ttk.Button(action_row, text="Generate Report", command=self._generate).pack(
            side="left"
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
        self._analysis_texts.clear()
        self._analyze_btns.clear()
        self._approve_btns.clear()
        self._disapprove_btns.clear()
        self._status_labels.clear()

        for tab in self._notebook.tabs():
            self._notebook.forget(tab)

        for section in report.sections:
            self._add_section_tab(section)

    def _add_section_tab(self, section: SectionDef) -> None:
        frame = ttk.Frame(self._notebook)
        self._notebook.add(frame, text=section.key)

        # Vertical paned window: top = CSV management, bottom = AI analysis
        paned = ttk.PanedWindow(frame, orient=tk.VERTICAL)
        paned.pack(fill="both", expand=True, padx=5, pady=5)

        # ── top pane: CSV management ─────────────────────────────────────
        csv_frame = ttk.Frame(paned)
        paned.add(csv_frame, weight=1)

        ttk.Label(csv_frame, text=section.title, font=("Helvetica", 12, "bold")).pack(
            anchor="w", padx=10, pady=(8, 2)
        )
        ttk.Label(csv_frame, text=section.description, wraplength=920).pack(
            anchor="w", padx=10, pady=(0, 6)
        )

        if section.loading_levels:
            count = len(section.loading_levels)
            ttk.Label(
                csv_frame,
                text=f"Upload exactly {count} CSVs (ordered {section.loading_levels[0]} \u2192 {section.loading_levels[-1]})",
                foreground="gray",
            ).pack(anchor="w", padx=10)

        btn_row = ttk.Frame(csv_frame)
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

        listbox = tk.Listbox(csv_frame, height=8, selectmode=tk.EXTENDED)
        listbox.pack(fill="both", expand=True, padx=10, pady=(0, 8))
        self._csv_listboxes[key] = listbox

        # ── bottom pane: AI analysis ─────────────────────────────────────
        analysis_lf = ttk.LabelFrame(paned, text="AI Analysis")
        paned.add(analysis_lf, weight=1)

        # button row
        abtn_row = ttk.Frame(analysis_lf)
        abtn_row.pack(fill="x", padx=10, pady=(6, 4))

        analyze_btn = ttk.Button(
            abtn_row, text="Analyze", command=lambda k=key: self._run_analysis(k)
        )
        analyze_btn.pack(side="left", padx=4)
        self._analyze_btns[key] = analyze_btn

        approve_btn = ttk.Button(
            abtn_row,
            text="Approve",
            state="disabled",
            command=lambda k=key: self._approve(k),
        )
        approve_btn.pack(side="left", padx=4)
        self._approve_btns[key] = approve_btn

        disapprove_btn = ttk.Button(
            abtn_row,
            text="Disapprove & Regenerate",
            state="disabled",
            command=lambda k=key: self._disapprove_and_regenerate(k),
        )
        disapprove_btn.pack(side="left", padx=4)
        self._disapprove_btns[key] = disapprove_btn

        status_lbl = ttk.Label(abtn_row, text="")
        status_lbl.pack(side="left", padx=10)
        self._status_labels[key] = status_lbl

        # text widget (read-only, scrollable)
        text_frame = ttk.Frame(analysis_lf)
        text_frame.pack(fill="both", expand=True, padx=10, pady=(0, 8))

        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")

        text_widget = tk.Text(
            text_frame,
            wrap="word",
            state="disabled",
            height=8,
            yscrollcommand=scrollbar.set,
        )
        text_widget.pack(fill="both", expand=True)
        scrollbar.config(command=text_widget.yview)
        self._analysis_texts[key] = text_widget

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
        if paths:
            self._invalidate_analysis(key)

    def _remove_csvs(self, key: str) -> None:
        selection = self._csv_listboxes[key].curselection()
        if not selection:
            return
        for idx in reversed(selection):
            self._csv_listboxes[key].delete(idx)
            del self._section_states[key].csv_files[idx]
        self._invalidate_analysis(key)

    def _clear_csvs(self, key: str) -> None:
        self._section_states[key].csv_files.clear()
        self._csv_listboxes[key].delete(0, tk.END)
        self._invalidate_analysis(key)

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

    # ── analysis ─────────────────────────────────────────────────────────

    def _invalidate_analysis(self, key: str) -> None:
        """Reset analysis state when CSVs change."""
        state = self._section_states[key]
        state.analysis_text = ""
        state.analysis_approved = None

        # clear text widget
        tw = self._analysis_texts[key]
        tw.config(state="normal")
        tw.delete("1.0", tk.END)
        tw.config(state="disabled")

        # reset buttons
        self._approve_btns[key].config(state="disabled")
        self._disapprove_btns[key].config(state="disabled")
        self._analyze_btns[key].config(state="normal")
        self._status_labels[key].config(
            text="CSVs changed \u2013 re-analyze", foreground="orange"
        )

    def _run_analysis(
        self, key: str, previous_text: str = "", feedback: str = ""
    ) -> None:
        state = self._section_states[key]
        if not state.csv_files:
            messagebox.showwarning("No CSVs", "Add CSV files before analyzing.")
            return

        section = self._section_for(key)
        if section is None:
            return

        # disable button, show progress
        self._analyze_btns[key].config(state="disabled")
        self._approve_btns[key].config(state="disabled")
        self._disapprove_btns[key].config(state="disabled")
        status_msg = "Regenerating..." if feedback else "Analyzing..."
        self._status_labels[key].config(text=status_msg, foreground="blue")

        def _worker() -> None:
            try:
                result = analyze_section(
                    section, state.csv_files, previous_text, feedback
                )
                self.after(0, lambda: self._on_analysis_complete(key, result))
            except Exception as exc:  # noqa: BLE001
                self.after(0, lambda e=exc: self._on_analysis_error(key, e))

        thread = threading.Thread(target=_worker, daemon=True)
        thread.start()

    def _on_analysis_complete(self, key: str, text: str) -> None:
        state = self._section_states[key]
        state.analysis_text = text
        state.analysis_approved = None

        tw = self._analysis_texts[key]
        tw.config(state="normal")
        tw.delete("1.0", tk.END)
        tw.insert("1.0", text)
        tw.config(state="disabled")

        self._analyze_btns[key].config(state="normal")
        self._approve_btns[key].config(state="normal")
        self._disapprove_btns[key].config(state="normal")
        self._status_labels[key].config(
            text="Review and approve/disapprove", foreground="black"
        )

    def _on_analysis_error(self, key: str, error: Exception) -> None:
        self._analyze_btns[key].config(state="normal")
        self._status_labels[key].config(text="Analysis failed", foreground="red")
        messagebox.showerror("Analysis Error", str(error))

    def _approve(self, key: str) -> None:
        state = self._section_states[key]
        state.analysis_approved = True
        self._status_labels[key].config(text="APPROVED", foreground="green")
        self._approve_btns[key].config(state="disabled")
        self._disapprove_btns[key].config(state="normal")

    def _disapprove_and_regenerate(self, key: str) -> None:
        state = self._section_states[key]
        feedback = simpledialog.askstring(
            "Regenerate analysis",
            "What should the model fix or change?",
            parent=self,
        )
        if not feedback or not feedback.strip():
            return
        state.analysis_approved = False
        self._run_analysis(key, previous_text=state.analysis_text, feedback=feedback.strip())

    def _section_for(self, key: str) -> SectionDef | None:
        if not self._current_report:
            return None
        return next((s for s in self._current_report.sections if s.key == key), None)

    # ── preview ──────────────────────────────────────────────────────────

    def _preview(self) -> None:
        if not self._current_report:
            messagebox.showerror("No report", "Select a report type.")
            return
        if not any(s.csv_files for s in self._section_states.values()):
            messagebox.showerror("No CSVs", "Add CSVs to at least one section.")
            return

        markdown = render_report_markdown(self._current_report, self._section_states)

        win = tk.Toplevel(self)
        win.title(f"Preview – {self._current_report.name}")
        win.geometry("900x700")

        toolbar = ttk.Frame(win)
        toolbar.pack(fill="x", padx=8, pady=6)
        ttk.Label(
            toolbar,
            text="Markdown approximation of the docx output. "
            "Tables are truncated to 10 rows; charts are placeholders.",
            foreground="gray",
        ).pack(side="left")
        ttk.Button(
            toolbar, text="Refresh", command=lambda: self._refresh_preview(text)
        ).pack(side="right")

        text_frame = ttk.Frame(win)
        text_frame.pack(fill="both", expand=True, padx=8, pady=(0, 8))
        scrollbar = ttk.Scrollbar(text_frame)
        scrollbar.pack(side="right", fill="y")
        text = tk.Text(
            text_frame,
            wrap="word",
            font=("Menlo", 11),
            yscrollcommand=scrollbar.set,
        )
        text.pack(fill="both", expand=True)
        scrollbar.config(command=text.yview)
        text.insert("1.0", markdown)
        text.config(state="disabled")

    def _refresh_preview(self, text_widget: tk.Text) -> None:
        if not self._current_report:
            return
        markdown = render_report_markdown(self._current_report, self._section_states)
        text_widget.config(state="normal")
        text_widget.delete("1.0", tk.END)
        text_widget.insert("1.0", markdown)
        text_widget.config(state="disabled")

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

        unapproved = [
            self._section_for(k).title
            for k, s in self._section_states.items()
            if s.csv_files and s.analysis_approved is not True
        ]
        if unapproved:
            messagebox.showerror(
                "Analysis not approved",
                "Run and approve the analysis for these sections before generating:\n\n"
                + "\n".join(f"• {t}" for t in unapproved),
            )
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

        self.status_label.config(text=f"Saved \u2192 {self.output_path}")
        messagebox.showinfo("Done", "Report generated successfully.")
