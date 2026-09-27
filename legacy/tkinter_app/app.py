from __future__ import annotations

import queue
import threading
import multiprocessing as mp
import math
import time
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
import tkinter as tk
from tkinter import filedialog, messagebox, ttk

try:
    from matplotlib.backends.backend_tkagg import FigureCanvasTkAgg
    from matplotlib.figure import Figure
except Exception:  # pragma: no cover - the app still runs without charts.
    Figure = None
    FigureCanvasTkAgg = None

from problems.clique import (
    average_degree_clique_problem,
    exact_edges_clique_problem,
    manual_clique_problem,
    random_clique_problem,
)
from problems.dimacs_problem import dimacs_problem_from_text
from problems.graph_coloring import (
    average_degree_graph_coloring_problem,
    exact_edges_graph_coloring_problem,
    manual_graph_coloring_problem,
    random_graph_coloring_problem,
)
from problems.hamiltonian_path import (
    average_degree_hamiltonian_path_problem,
    exact_edges_hamiltonian_path_problem,
    manual_hamiltonian_path_problem,
    random_hamiltonian_path_problem,
)
from problems.independent_set import (
    average_degree_independent_set_problem,
    exact_edges_independent_set_problem,
    manual_independent_set_problem,
    random_independent_set_problem,
)
from problems.n_queens import n_queens_problem
from problems.random_3sat import RANDOM_3SAT_MODES, random_3sat_problem
from problems.sudoku import sudoku_problem
from sat_core.benchmark import SUDOKU_BENCHMARK_SIZES, write_benchmark_csv, write_random_3sat_benchmark_csv
from sat_core.dimacs import clauses_to_dimacs, load_dimacs, save_dimacs
from sat_core.models import BenchmarkRow, ProblemInstance
from sat_core.process_workers import benchmark_process, generate_cnf_process, solve_process
from sat_core.benchmark_presets.random_3sat_presets import (
    RANDOM_3SAT_PRESET_CUSTOM,
    random_3sat_preset_case_count,
    random_3sat_preset_default_solvers,
    random_3sat_preset_names,
    random_3sat_preset_summary,
    random_3sat_preset_ui_values,
)
from sat_core.runtime import (
    EVENT_CANCELLED,
    EVENT_CNF,
    EVENT_DONE,
    EVENT_ERROR,
    EVENT_LOG,
    EVENT_PROGRESS,
    EVENT_RESULT,
    EVENT_ROW,
    RunEvent,
    RunToken,
)
from sat_core.solver_runner import SOLVERS


INPUT_GENERATED = Path("input/generated")
BENCHMARK_OUTPUT = Path("output/benchmarks")
APP_ICON_PATH = Path("assets/logo.png")
SUDOKU_SIZES = (4, 9, 16, 25)
PROBLEM_KINDS = ("Sudoku", "Graph Coloring", "N-Queens", "Random 3-SAT", "Hamiltonian Path", "Independent Set", "Clique", "DIMACS/CNF")
BENCHMARK_PROBLEMS = ("Graph Coloring", "Graph Suite", "Sudoku", "N-Queens", "Random 3-SAT", "Hamiltonian Path", "Independent Set", "Clique")
GRAPH_PROBLEM_KINDS = ("Graph Coloring", "Hamiltonian Path", "Independent Set", "Clique")
SOLVE_SOLVERS = tuple(solver for solver in SOLVERS if solver != "ProbSAT")
CNF_AUTO_DISPLAY_MAX_CHARS = 200_000
FEED_MAX_LINES = 50
BENCHMARK_AUTO_CHART_MAX_ROWS = 120
BENCHMARK_LEFT_PANEL_WIDTH = 415
BENCHMARK_DETAIL_PANEL_WIDTH = 320
UI_EVENT_POLL_MS = 15
UI_EVENT_BATCH_MAX = 25
UI_EVENT_BATCH_SECONDS = 0.006
PROBLEM_DESCRIPTIONS = {
    "Sudoku": "Fill an n x n grid so each row, column, and square box contains every value exactly once.",
    "Graph Coloring": "Assign one of k colors to each node so adjacent nodes never share the same color.",
    "N-Queens": "Place n queens on an n x n chessboard so no two queens attack each other.",
    "Random 3-SAT": "Generate random 3-literal clauses as planted SAT, forced UNSAT, pure random, or a SAT/UNSAT mix.",
    "Hamiltonian Path": "Find a path through an undirected graph that visits every node exactly once.",
    "Independent Set": "Choose at least k graph nodes so no two chosen nodes are connected by an edge.",
    "Clique": "Choose at least k graph nodes so every chosen pair is connected by an edge.",
    "Graph Suite": "Run selected graph problems on the exact same generated graph for fair side-by-side benchmarks.",
    "DIMACS/CNF": "Paste or load SAT clauses directly in DIMACS CNF format.",
}
SOLVER_GUIDE_ROWS = (
    ("CDCL", "Complete; learns clauses, backjumps, strongest default for hard formulas."),
    ("DPLL", "Complete; recursive baseline, simpler and useful for comparison."),
    ("WalkSAT", "Incomplete local search; Classic mixes random/greedy flips, ProbSAT favors low-break repairs, UNKNOWN if no model is found."),
)

WALKSAT_STRATEGIES = ("Classic WalkSAT", "ProbSAT")


@dataclass
class RunJob:
    job_id: str
    label: str
    kind: str
    title: str
    status: str = "Starting"
    progress_current: int | None = None
    progress_total: int | None = None
    token: RunToken | None = None
    thread: threading.Thread | None = None
    process: mp.Process | None = None
    cancel_event: object | None = None
    skip_event: object | None = None
    finished: bool = False
    problem: ProblemInstance | None = None
    dimacs: str = ""
    result: object | None = None
    rows: list[BenchmarkRow] = field(default_factory=list)
    pending_chart_refresh: bool = False


def parse_int_list(text: str) -> list[int]:
    values = [item.strip() for item in text.replace(";", ",").split(",") if item.strip()]
    return [int(value) for value in values]


def parse_float_list(text: str) -> list[float]:
    values = [item.strip() for item in text.replace(";", ",").split(",") if item.strip()]
    return [float(value) for value in values]


def parse_timeout_seconds(text: str) -> float | None:
    raw = text.strip()
    if not raw:
        return None

    timeout = float(raw)
    return timeout if timeout > 0 else None


class SATApp:
    def __init__(self, root: tk.Tk):
        self.root = root
        self.root.title("WizSAT Problem Solver")
        self.root.geometry("1500x900")
        self._configure_window_icon()

        INPUT_GENERATED.mkdir(parents=True, exist_ok=True)
        BENCHMARK_OUTPUT.mkdir(parents=True, exist_ok=True)

        self.current_problem: ProblemInstance | None = None
        self.latest_solve_result = None
        self.current_cnf_dimacs = ""
        self.benchmark_rows: list[BenchmarkRow] = []
        self.benchmark_row_by_item = {}
        self.benchmark_canvas = None
        self.benchmark_figure = None
        self.benchmark_chart_message = None
        self.benchmark_detail_canvas = None
        self.solve_detail_canvas = None
        self.selected_benchmark_row: BenchmarkRow | None = None
        self.event_queue: queue.Queue[RunEvent] = queue.Queue()
        self.jobs: dict[str, RunJob] = {}
        self.next_job_number = 1
        self.selected_job_id: str | None = None
        self.selected_solve_job_id: str | None = None
        self.selected_benchmark_job_id: str | None = None
        self.benchmark_filter_run_label: str | tuple[str, ...] | None = None
        self.pending_benchmark_chart_after_id = None
        self.updating_job_selection = False
        self.batching_run_events = False
        self.job_buttons_refresh_needed = False
        self.feed_entries: list[tuple[str, str | None, str]] = []
        self.pending_feed_messages: list[tuple[str | None, str]] = []
        self.feed_filter_job_id: str | None = None
        self.muted_feed_job_ids: set[str] = set()

        self._configure_styles()
        self._build_layout()
        self.root.bind("<Control-w>", lambda _event: self.root.destroy())
        self.root.after(100, self._poll_run_events)

    def _configure_window_icon(self) -> None:
        if not APP_ICON_PATH.exists():
            return

        try:
            self.app_icon = tk.PhotoImage(file=str(APP_ICON_PATH))
            self.root.iconphoto(True, self.app_icon)
        except (OSError, tk.TclError):
            pass

    def _toolbar_logo_image(self):
        if hasattr(self, "toolbar_logo"):
            return self.toolbar_logo
        if not APP_ICON_PATH.exists():
            self.toolbar_logo = None
            return None

        try:
            logo = tk.PhotoImage(file=str(APP_ICON_PATH))
            scale = max(1, math.ceil(max(logo.width(), logo.height()) / 34))
            self.toolbar_logo = logo.subsample(scale, scale)
        except (OSError, tk.TclError):
            self.toolbar_logo = None
        return self.toolbar_logo

    def _configure_styles(self) -> None:
        self.style = ttk.Style(self.root)
        button_styles = {
            "Primary.TButton": ("#dbeafe", "#1d4ed8", "#bfdbfe"),
            "Generate.TButton": ("#dcfce7", "#166534", "#bbf7d0"),
            "Export.TButton": ("#fef3c7", "#92400e", "#fde68a"),
            "Warning.TButton": ("#ffedd5", "#9a3412", "#fed7aa"),
            "Danger.TButton": ("#fee2e2", "#991b1b", "#fecaca"),
        }

        for style_name, (background, foreground, active_background) in button_styles.items():
            self.style.configure(
                style_name,
                background=background,
                foreground=foreground,
                padding=(8, 4),
            )
            self.style.map(
                style_name,
                background=[
                    ("disabled", "#e5e7eb"),
                    ("pressed", active_background),
                    ("active", active_background),
                    ("!disabled", background),
                ],
                foreground=[
                    ("disabled", "#6b7280"),
                    ("!disabled", foreground),
                ],
            )

    def _build_layout(self) -> None:
        self.root.rowconfigure(0, weight=1)
        self.root.rowconfigure(1, weight=0)
        self.root.columnconfigure(0, weight=1)
        self.notebook = ttk.Notebook(self.root)
        self.solve_tab = self._build_tab("Solve")
        self.benchmark_tab = self._build_tab("Benchmarks")
        self.notebook.grid(row=0, column=0, sticky="nsew")
        self.root.bind_all("<MouseWheel>", self._scroll_local_panel, add="+")
        self.root.bind_class("TCombobox", "<MouseWheel>", self._scroll_page_from_combobox)

        self._build_solve_tab()
        self._build_benchmark_tab()
        self._build_runtime_panel()
        self.notebook.bind("<<NotebookTabChanged>>", self._on_notebook_tab_changed, add="+")

    def _on_notebook_tab_changed(self, _event=None) -> None:
        try:
            selected_tab = self.notebook.nametowidget(self.notebook.select())
        except tk.TclError:
            return
        if selected_tab is self.benchmark_tab:
            self.root.after_idle(self._set_initial_benchmark_sash)

    def _build_tab(self, title: str) -> ttk.Frame:
        tab = ttk.Frame(self.notebook, padding=10)
        tab.rowconfigure(1, weight=1)
        tab.columnconfigure(0, weight=1)
        self.notebook.add(tab, text=title)
        return tab

    def _build_scrollable_tab(self, title: str) -> ttk.Frame:
        tab = ttk.Frame(self.notebook)
        tab.rowconfigure(0, weight=1)
        tab.columnconfigure(0, weight=1)

        canvas = tk.Canvas(tab, highlightthickness=0, borderwidth=0)
        yscroll = ttk.Scrollbar(tab, orient=tk.VERTICAL, command=canvas.yview)
        xscroll = ttk.Scrollbar(tab, orient=tk.HORIZONTAL, command=canvas.xview)
        canvas.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)

        canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")

        content = ttk.Frame(canvas, padding=10)
        content._tab_scroll_canvas = canvas
        content_window = canvas.create_window(0, 0, window=content, anchor="nw")

        def update_scroll_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event) -> None:
            requested_width = content.winfo_reqwidth()
            canvas.itemconfigure(content_window, width=max(event.width, requested_width))
            update_scroll_region()

        def widget_is_inside_scroll_area(widget) -> bool:
            while widget is not None:
                if widget is content or widget is canvas:
                    return True
                widget = getattr(widget, "master", None)
            return False

        def widget_allows_own_scroll(widget) -> bool:
            while widget is not None:
                try:
                    widget_class = widget.winfo_class()
                except tk.TclError:
                    return False
                if widget_class in {"Text", "Treeview", "Entry", "TEntry", "Spinbox", "TSpinbox"}:
                    return True
                if widget is content or widget is canvas:
                    return False
                widget = getattr(widget, "master", None)
            return False

        def scroll_page(event) -> str | None:
            if not widget_is_inside_scroll_area(event.widget):
                return None
            if widget_allows_own_scroll(event.widget):
                return None
            if event.state & 0x0001:
                canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
            else:
                canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
            return "break"

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        canvas.bind_all("<MouseWheel>", scroll_page, add="+")
        self.root.bind_class("TCombobox", "<MouseWheel>", self._scroll_page_from_combobox)

        self.notebook.add(tab, text=title)
        return content

    def _build_top_toolbar(self, parent) -> ttk.Frame:
        toolbar = ttk.Frame(parent, padding=(0, 0, 0, 8))
        toolbar.columnconfigure(99, weight=1)
        logo = self._toolbar_logo_image()
        if logo is not None:
            label = ttk.Label(toolbar, image=logo)
            label.grid(row=0, column=99, sticky="e", padx=(12, 0))
        return toolbar

    def _toolbar_button(self, parent, text: str, command, *, style: str | None = None, state=tk.NORMAL):
        return ttk.Button(parent, text=text, command=command, style=style, state=state)

    def _build_scrollable_panel(self, parent) -> ttk.Frame:
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        canvas = tk.Canvas(parent, highlightthickness=0, borderwidth=0)
        yscroll = ttk.Scrollbar(parent, orient=tk.VERTICAL, command=canvas.yview)
        canvas.configure(yscrollcommand=yscroll.set)
        canvas.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")

        content = ttk.Frame(canvas, padding=(0, 0, 8, 0))
        content._tab_scroll_canvas = canvas
        parent._tab_scroll_canvas = canvas
        content_window = canvas.create_window(0, 0, window=content, anchor="nw")

        def update_scroll_region(_event=None) -> None:
            canvas.configure(scrollregion=canvas.bbox("all"))

        def resize_content(event) -> None:
            canvas.itemconfigure(content_window, width=event.width)
            update_scroll_region()

        content.bind("<Configure>", update_scroll_region)
        canvas.bind("<Configure>", resize_content)
        return content

    def _scroll_page_from_combobox(self, event) -> str:
        widget = event.widget
        while widget is not None:
            canvas = getattr(widget, "_tab_scroll_canvas", None)
            if canvas is not None:
                if event.state & 0x0001:
                    canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
                else:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"
            widget = getattr(widget, "master", None)
        return "break"

    def _scroll_local_panel(self, event) -> str | None:
        widget = event.widget
        while widget is not None:
            try:
                widget_class = widget.winfo_class()
            except tk.TclError:
                return None
            if widget_class in {"Text", "Treeview", "Entry", "TEntry", "Spinbox", "TSpinbox"}:
                return None
            canvas = getattr(widget, "_tab_scroll_canvas", None)
            if canvas is not None:
                if event.state & 0x0001:
                    canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
                else:
                    canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
                return "break"
            widget = getattr(widget, "master", None)
        return None

    def _build_runtime_panel(self) -> None:
        panel = ttk.LabelFrame(self.root, text="Run Feed", padding=8)
        panel.grid(row=1, column=0, sticky="ew", padx=10, pady=(0, 10))
        panel.columnconfigure(0, weight=1)

        self.run_status = tk.StringVar(value="Ready")
        self.progress_value = tk.DoubleVar(value=0)
        self.progress_percent = tk.StringVar(value="0%")
        runtime_header = ttk.Frame(panel)
        runtime_header.grid(row=0, column=0, columnspan=2, sticky="ew")
        runtime_header.columnconfigure(1, weight=1)
        ttk.Label(runtime_header, textvariable=self.run_status).grid(row=0, column=0, sticky="w", padx=(0, 8))
        self.run_progress_bar = ttk.Progressbar(
            runtime_header,
            variable=self.progress_value,
            maximum=100,
            mode="determinate",
        )
        self.run_progress_bar.grid(row=0, column=1, sticky="ew", padx=(0, 8))
        ttk.Label(runtime_header, textvariable=self.progress_percent, width=5, anchor="e").grid(row=0, column=2, sticky="e", padx=(0, 10))
        feed_controls = ttk.Frame(runtime_header)
        feed_controls.grid(row=0, column=3, sticky="e")
        self.feed_show_all_button = ttk.Button(
            feed_controls,
            text="All Logs",
            command=self.show_all_feed_logs,
            state=tk.DISABLED,
        )
        self.feed_show_selected_button = ttk.Button(
            feed_controls,
            text="Selected Logs",
            command=self.show_selected_job_feed_logs,
            state=tk.DISABLED,
        )
        self.feed_mute_selected_button = ttk.Button(
            feed_controls,
            text="Mute Selected",
            command=self.toggle_selected_job_feed_muted,
            state=tk.DISABLED,
        )
        self.feed_unmute_all_button = ttk.Button(
            feed_controls,
            text="Unmute All",
            command=self.unmute_all_feed_logs,
            state=tk.DISABLED,
        )
        self.feed_clear_button = ttk.Button(feed_controls, text="Clear Feed", command=self.clear_feed)
        self.feed_status = tk.StringVar(value="Logs: all visible")
        self.feed_status_label = ttk.Label(feed_controls, textvariable=self.feed_status)
        self.feed_show_all_button.pack(side=tk.LEFT, padx=(0, 4))
        self.feed_show_selected_button.pack(side=tk.LEFT, padx=(0, 4))
        self.feed_mute_selected_button.pack(side=tk.LEFT, padx=(0, 4))
        self.feed_unmute_all_button.pack(side=tk.LEFT, padx=(0, 4))
        self.feed_clear_button.pack(side=tk.LEFT)
        self.feed_status_label.pack(side=tk.LEFT, padx=(8, 0))

        self.feed_text = tk.Text(panel, height=7, wrap="word", state=tk.DISABLED)
        self.feed_text.grid(row=1, column=0, sticky="ew", pady=(8, 0))
        feed_scroll = ttk.Scrollbar(panel, orient=tk.VERTICAL, command=self.feed_text.yview)
        feed_scroll.grid(row=1, column=1, sticky="ns", pady=(8, 0))
        self.feed_text.configure(yscrollcommand=feed_scroll.set)

    def clear_feed(self) -> None:
        self.feed_entries = []
        self.pending_feed_messages = []
        self._render_feed()

    def append_feed(self, message: str, job_id: str | None = None) -> None:
        if job_id is not None and job_id in self.muted_feed_job_ids:
            return
        if self.batching_run_events:
            self.pending_feed_messages.append((job_id, message))
            return
        self._append_feed_entries([(job_id, message)])

    def _append_feed_entries(self, entries: list[tuple[str | None, str]]) -> None:
        timestamp = datetime.now().strftime("%H:%M:%S")
        for job_id, message in entries:
            if job_id is not None and job_id in self.muted_feed_job_ids:
                continue
            self.feed_entries.append((timestamp, job_id, message))
        if len(self.feed_entries) > FEED_MAX_LINES:
            self.feed_entries = self.feed_entries[-FEED_MAX_LINES:]
        self._render_feed()

    def _flush_pending_feed_messages(self) -> None:
        if not self.pending_feed_messages:
            return
        self._append_feed_entries(self.pending_feed_messages[-FEED_MAX_LINES:])
        self.pending_feed_messages = []

    def _render_feed(self) -> None:
        self.feed_text.configure(state=tk.NORMAL)
        self.feed_text.delete("1.0", tk.END)
        for timestamp, job_id, message in self.feed_entries:
            if self.feed_filter_job_id is not None and job_id != self.feed_filter_job_id:
                continue
            self.feed_text.insert(tk.END, f"[{timestamp}] {message}\n")
        self.feed_text.see(tk.END)
        self.feed_text.configure(state=tk.DISABLED)

    def show_all_feed_logs(self) -> None:
        self.feed_filter_job_id = None
        self._render_feed()
        self._refresh_feed_controls()

    def show_selected_job_feed_logs(self) -> None:
        if self.selected_job_id is None:
            return
        self.feed_filter_job_id = self.selected_job_id
        self._render_feed()
        self._refresh_feed_controls()

    def toggle_selected_job_feed_muted(self) -> None:
        jobs = self._selected_feed_jobs()
        if not jobs:
            return
        job_ids = {job.job_id for job in jobs}
        should_unmute = all(job_id in self.muted_feed_job_ids for job_id in job_ids)
        if should_unmute:
            self.muted_feed_job_ids.difference_update(job_ids)
        else:
            self.muted_feed_job_ids.update(job_ids)
            self.feed_entries = [
                entry
                for entry in self.feed_entries
                if entry[1] not in job_ids
            ]
            self.pending_feed_messages = [
                entry
                for entry in self.pending_feed_messages
                if entry[0] not in job_ids
            ]
        for job in jobs:
            self._update_job_row(job)
        self._render_feed()
        self._refresh_feed_controls()

    def unmute_all_feed_logs(self) -> None:
        muted_job_ids = set(self.muted_feed_job_ids)
        self.muted_feed_job_ids.clear()
        for job_id in muted_job_ids:
            job = self.jobs.get(job_id)
            if job is not None:
                self._update_job_row(job)
        self._refresh_feed_controls()

    def _forget_job_feed(self, job_id: str) -> None:
        self.muted_feed_job_ids.discard(job_id)
        if self.feed_filter_job_id == job_id:
            self.feed_filter_job_id = None
        self.feed_entries = [
            entry
            for entry in self.feed_entries
            if entry[1] != job_id
        ]
        self.pending_feed_messages = [
            entry
            for entry in self.pending_feed_messages
            if entry[0] != job_id
        ]
        if hasattr(self, "feed_text"):
            self._render_feed()

    def _refresh_feed_controls(self) -> None:
        if not hasattr(self, "feed_show_all_button"):
            return
        selected = self.selected_job_id in self.jobs if self.selected_job_id else False
        if self.feed_filter_job_id is not None and self.feed_filter_job_id not in self.jobs:
            self.feed_filter_job_id = None
            self._render_feed()
        self.feed_show_all_button.configure(state=tk.NORMAL if self.feed_filter_job_id is not None else tk.DISABLED)
        self.feed_show_selected_button.configure(state=tk.NORMAL if selected else tk.DISABLED)
        self.feed_mute_selected_button.configure(state=tk.NORMAL if selected else tk.DISABLED)
        self.feed_unmute_all_button.configure(state=tk.NORMAL if self.muted_feed_job_ids else tk.DISABLED)
        selected_jobs = self._selected_feed_jobs()
        selected_job_ids = {job.job_id for job in selected_jobs}
        muted = bool(selected_job_ids) and selected_job_ids.issubset(self.muted_feed_job_ids)
        self.feed_mute_selected_button.configure(text="Unmute Selected" if muted else "Mute Selected")
        if self.feed_filter_job_id is not None:
            job = self.jobs.get(self.feed_filter_job_id)
            scope = f"selected {job.label}" if job is not None else "selected job"
        else:
            scope = "all"
        muted_count = len(self.muted_feed_job_ids)
        muted_text = f", {muted_count} muted" if muted_count else ", none muted"
        if len(selected_jobs) > 1:
            selected_text = "selected muted" if muted else "some selected unmuted"
        else:
            selected_text = "selected muted" if muted else "selected unmuted"
        self.feed_status.set(f"Logs: {scope}{muted_text}; {selected_text}" if selected else f"Logs: {scope}{muted_text}")

    def _selected_job(self) -> RunJob | None:
        return self.jobs.get(self.selected_job_id) if self.selected_job_id else None

    def _selected_solve_job(self) -> RunJob | None:
        return self.jobs.get(self.selected_solve_job_id) if self.selected_solve_job_id else None

    def _selected_solve_jobs(self) -> list[RunJob]:
        table = getattr(self, "solve_jobs_table", None)
        if table is None:
            job = self._selected_solve_job()
            return [job] if job is not None else []
        selected_ids = set(table.selection())
        if not selected_ids:
            job = self._selected_solve_job()
            return [job] if job is not None else []
        jobs = []
        for job_id in table.get_children():
            if job_id in selected_ids:
                job = self.jobs.get(job_id)
                if job is not None and self._job_kind_group(job) == "solve":
                    jobs.append(job)
        return jobs

    def _selected_benchmark_job(self) -> RunJob | None:
        return self.jobs.get(self.selected_benchmark_job_id) if self.selected_benchmark_job_id else None

    def _selected_benchmark_jobs(self) -> list[RunJob]:
        table = getattr(self, "benchmark_jobs_table", None)
        if table is None:
            job = self._selected_benchmark_job()
            return [job] if job is not None else []
        selected_ids = set(table.selection())
        if not selected_ids:
            job = self._selected_benchmark_job()
            return [job] if job is not None else []
        jobs = []
        for job_id in table.get_children():
            if job_id in selected_ids:
                job = self.jobs.get(job_id)
                if job is not None and job.kind == "benchmark":
                    jobs.append(job)
        return jobs

    def _selected_feed_jobs(self) -> list[RunJob]:
        selected_job = self.jobs.get(self.selected_job_id) if self.selected_job_id else None
        if selected_job is None:
            return []
        if self._job_kind_group(selected_job) == "benchmark":
            return self._selected_benchmark_jobs()
        return self._selected_solve_jobs()

    def _job_kind_group(self, job: RunJob) -> str:
        return "benchmark" if job.kind == "benchmark" else "solve"

    def _job_table_for_group(self, group: str):
        if group == "benchmark":
            return getattr(self, "benchmark_jobs_table", None)
        return getattr(self, "solve_jobs_table", None)

    def _create_job(self, kind: str, title: str, *, skip_event=None) -> RunJob:
        number = self.next_job_number
        self.next_job_number += 1
        job = RunJob(
            job_id=f"job-{number}",
            label=f"J{number}",
            kind=kind,
            title=title,
            skip_event=skip_event,
        )
        self.jobs[job.job_id] = job
        self._insert_job_row(job)
        self._select_job(job.job_id)
        self._refresh_job_buttons()
        return job

    def _job_display_title(self, job: RunJob) -> str:
        marker = "[M] " if job.job_id in self.muted_feed_job_ids else ""
        return f"{marker}{job.label}: {job.title}"

    def _job_row_tags(self, job: RunJob) -> tuple[str, ...]:
        return ("muted",) if job.job_id in self.muted_feed_job_ids else ()

    def _job_progress_text(self, job: RunJob) -> str:
        if job.progress_total:
            current = job.progress_current or 0
            percent = current * 100 / job.progress_total
            return f"{current}/{job.progress_total} ({percent:.0f}%)"
        return "-"

    def _insert_job_row(self, job: RunJob) -> None:
        table = self._job_table_for_group(self._job_kind_group(job))
        if table is None:
            return
        table.insert(
            "",
            tk.END,
            iid=job.job_id,
            values=(
                self._job_display_title(job),
                job.status,
                self._job_progress_text(job),
            ),
            tags=self._job_row_tags(job),
        )

    def _update_job_row(self, job: RunJob) -> None:
        table = self._job_table_for_group(self._job_kind_group(job))
        if table is None or not table.exists(job.job_id):
            return
        table.item(
            job.job_id,
            values=(
                self._job_display_title(job),
                job.status,
                self._job_progress_text(job),
            ),
            tags=self._job_row_tags(job),
        )
        self._request_job_buttons_refresh()

    def _request_job_buttons_refresh(self) -> None:
        if self.batching_run_events:
            self.job_buttons_refresh_needed = True
        else:
            self._refresh_job_buttons()

    def _select_job(self, job_id: str) -> None:
        if job_id not in self.jobs:
            return
        self.selected_job_id = job_id
        job = self.jobs[job_id]
        group = self._job_kind_group(job)
        if group == "benchmark":
            self.selected_benchmark_job_id = job_id
        else:
            self.selected_solve_job_id = job_id
        table = self._job_table_for_group(group)
        if table is not None and table.exists(job_id):
            self.updating_job_selection = True
            try:
                table.selection_remove(table.selection())
                table.selection_set(job_id)
                table.focus(job_id)
                table.see(job_id)
            finally:
                self.updating_job_selection = False
        if job.kind in {"solve", "generate"} and job.problem is not None:
            self._display_solve_job(job)
        self._refresh_job_buttons()

    def _on_solve_job_selected(self, _event=None) -> None:
        if self.updating_job_selection:
            return

        selected = self.solve_jobs_table.selection()
        if not selected:
            self.selected_solve_job_id = None
            self._refresh_job_buttons()
            return
        focused = self.solve_jobs_table.focus()
        job_id = focused if focused in selected else selected[-1]
        self.selected_solve_job_id = job_id
        self.selected_job_id = job_id
        job = self.jobs.get(job_id)
        if job is not None and job.kind in {"solve", "generate"} and job.problem is not None:
            self._display_solve_job(job)
        self._refresh_job_buttons()

    def _on_benchmark_job_selected(self, _event=None) -> None:
        if self.updating_job_selection:
            return

        selected = self.benchmark_jobs_table.selection()
        if not selected:
            self.selected_benchmark_job_id = None
            self._refresh_job_buttons()
            return
        focused = self.benchmark_jobs_table.focus()
        job_id = focused if focused in selected else selected[-1]
        self.selected_benchmark_job_id = job_id
        self.selected_job_id = job_id
        self._refresh_job_buttons()

    def _refresh_job_buttons(self) -> None:
        solve_job = self._selected_solve_job()
        benchmark_job = self._selected_benchmark_job()
        selected_job = self.jobs.get(self.selected_job_id) if self.selected_job_id else None

        solve_running = solve_job is not None and not solve_job.finished
        benchmark_running = benchmark_job is not None and not benchmark_job.finished
        can_skip = benchmark_running and benchmark_job.skip_event is not None
        has_finished_solve = any(self._job_kind_group(job) == "solve" and job.finished for job in self.jobs.values())
        has_finished_benchmark = any(job.kind == "benchmark" and job.finished for job in self.jobs.values())
        has_benchmark_rows = bool(self.benchmark_rows)
        selected_benchmark_jobs = self._selected_benchmark_jobs()
        selected_run_labels = {job.label for job in selected_benchmark_jobs}
        selected_run_has_rows = any(row.run_label in selected_run_labels for row in self.benchmark_rows)
        can_delete_solve = solve_job is not None and solve_job.finished
        can_delete_benchmark = any(job.finished for job in selected_benchmark_jobs)

        if hasattr(self, "solve_cancel_button"):
            self.solve_cancel_button.configure(state=tk.NORMAL if solve_running else tk.DISABLED)
        if hasattr(self, "solve_toolbar_cancel_button"):
            self.solve_toolbar_cancel_button.configure(state=tk.NORMAL if solve_running else tk.DISABLED)
        if hasattr(self, "solve_load_button"):
            can_load = solve_job is not None and solve_job.problem is not None
            self.solve_load_button.configure(state=tk.NORMAL if can_load else tk.DISABLED)
        if hasattr(self, "solve_clear_finished_button"):
            self.solve_clear_finished_button.configure(state=tk.NORMAL if has_finished_solve else tk.DISABLED)
        if hasattr(self, "solve_delete_button"):
            self.solve_delete_button.configure(state=tk.NORMAL if can_delete_solve else tk.DISABLED)

        if hasattr(self, "benchmark_cancel_button"):
            self.benchmark_cancel_button.configure(state=tk.NORMAL if benchmark_running else tk.DISABLED)
        if hasattr(self, "benchmark_toolbar_cancel_button"):
            self.benchmark_toolbar_cancel_button.configure(state=tk.NORMAL if benchmark_running else tk.DISABLED)
        if hasattr(self, "benchmark_skip_job_button"):
            self.benchmark_skip_job_button.configure(state=tk.NORMAL if can_skip else tk.DISABLED)
        if hasattr(self, "skip_benchmark_button"):
            self.skip_benchmark_button.configure(state=tk.NORMAL if can_skip else tk.DISABLED)
        if hasattr(self, "benchmark_show_selected_button"):
            self.benchmark_show_selected_button.configure(state=tk.NORMAL if selected_run_has_rows else tk.DISABLED)
        if hasattr(self, "benchmark_show_all_button"):
            self.benchmark_show_all_button.configure(state=tk.NORMAL if self.benchmark_filter_run_label is not None else tk.DISABLED)
        if hasattr(self, "benchmark_clear_finished_jobs_button"):
            self.benchmark_clear_finished_jobs_button.configure(state=tk.NORMAL if has_finished_benchmark else tk.DISABLED)
        if hasattr(self, "benchmark_clear_all_results_button"):
            self.benchmark_clear_all_results_button.configure(state=tk.NORMAL if has_benchmark_rows else tk.DISABLED)
        if hasattr(self, "clear_benchmark_table_button"):
            self.clear_benchmark_table_button.configure(state=tk.NORMAL if has_benchmark_rows else tk.DISABLED)
        if hasattr(self, "benchmark_delete_job_button"):
            self.benchmark_delete_job_button.configure(state=tk.NORMAL if can_delete_benchmark else tk.DISABLED)
        self._refresh_feed_controls()

        if selected_job is None:
            self.run_status.set("Ready")
            self._set_runtime_progress(0)
            return

        self.run_status.set(selected_job.status)
        if selected_job.progress_total:
            self._set_runtime_progress((selected_job.progress_current or 0) * 100 / selected_job.progress_total)
        elif selected_job.finished:
            self._set_runtime_progress(100)
        else:
            self._set_runtime_progress(0)

    def _set_runtime_progress(self, percent: float) -> None:
        percent = max(0.0, min(100.0, float(percent)))
        self.progress_value.set(percent)
        self.progress_percent.set(f"{percent:.0f}%")

    def _queue_event(self, event: RunEvent) -> None:
        self.event_queue.put(event)

    def _queue_job_event(self, job_id: str, event: RunEvent) -> None:
        event.payload = dict(event.payload)
        event.payload["_job_id"] = job_id
        self._queue_event(event)

    def _start_worker(self, name: str, target, *, kind: str = "worker") -> RunJob:
        job = self._create_job(kind, name)
        token = RunToken()
        job.token = token
        job.status = "Running"
        self._update_job_row(job)
        self.append_feed(self._job_display_title(job), job.job_id)

        def wrapped() -> None:
            try:
                target(token, lambda event: self._queue_job_event(job.job_id, event))
            except Exception as exc:
                self._queue_job_event(job.job_id, RunEvent(EVENT_ERROR, str(exc)))
            finally:
                if token.is_cancelled():
                    self._queue_job_event(job.job_id, RunEvent(EVENT_CANCELLED, "Run cancelled."))
                else:
                    self._queue_job_event(job.job_id, RunEvent(EVENT_DONE, "Run finished."))

        job.thread = threading.Thread(target=wrapped, daemon=True)
        job.thread.start()
        return job

    def _start_process_worker(
        self,
        name: str,
        process_target,
        *args,
        extra_events=(),
        benchmark_skip_event=None,
        kind: str = "run",
    ) -> RunJob:
        job = self._create_job(kind, name, skip_event=benchmark_skip_event)
        process_queue = mp.Queue()
        cancel_event = mp.Event()
        process = mp.Process(target=process_target, args=(*args, *extra_events, process_queue, cancel_event), daemon=True)

        job.process = process
        job.cancel_event = cancel_event
        job.status = "Running"
        self._update_job_row(job)
        self.append_feed(self._job_display_title(job), job.job_id)

        def supervise() -> None:
            try:
                process.start()

                while process.is_alive() or not process_queue.empty():
                    try:
                        event = process_queue.get(timeout=0.05)
                        self._queue_job_event(job.job_id, event)
                    except queue.Empty:
                        pass

                process.join(timeout=0.2)

                if cancel_event.is_set():
                    self._queue_job_event(job.job_id, RunEvent(EVENT_CANCELLED, "Run cancelled."))
                elif process.exitcode not in (0, None):
                    self._queue_job_event(job.job_id, RunEvent(EVENT_ERROR, f"Worker process exited with code {process.exitcode}"))
                else:
                    self._queue_job_event(job.job_id, RunEvent(EVENT_DONE, "Run finished."))
            except Exception as exc:
                self._queue_job_event(job.job_id, RunEvent(EVENT_ERROR, f"Could not start worker process: {exc}"))

        job.thread = threading.Thread(target=supervise, daemon=True)
        job.thread.start()
        return job

    def cancel_active_run(self) -> None:
        job = self._selected_job()
        self._cancel_job(job)

    def cancel_selected_solve_job(self) -> None:
        self._cancel_job(self._selected_solve_job())

    def cancel_selected_benchmark_job(self) -> None:
        self._cancel_job(self._selected_benchmark_job())

    def _cancel_job(self, job: RunJob | None) -> None:
        if job is None or job.finished:
            return

        if job.token is not None:
            job.token.cancel()
        if job.cancel_event is not None:
            job.cancel_event.set()

        job.status = "Cancelling..."
        self._update_job_row(job)
        self.append_feed(f"{job.label}: Cancel requested; stopping after current solver checkpoint.", job.job_id)
        self.root.after(1500, lambda job_id=job.job_id: self._terminate_process_if_needed(job_id))

    def skip_current_benchmark_case(self) -> None:
        job = self._selected_benchmark_job()
        if job is None or job.finished or job.kind != "benchmark" or job.skip_event is None:
            return

        job.skip_event.set()
        job.status = "Skipping current benchmark case..."
        self._update_job_row(job)
        self.append_feed(f"{job.label}: Skip requested; current benchmark case will be marked SKIPPED at the next solver checkpoint.", job.job_id)

    def _terminate_process_if_needed(self, job_id: str) -> None:
        job = self.jobs.get(job_id)
        process = job.process if job is not None else None
        if process is not None and process.is_alive():
            self.append_feed(f"{job.label}: Worker still running; terminating process.", job.job_id)
            process.terminate()

    def clear_finished_jobs(self) -> None:
        self.clear_finished_solve_jobs()
        self.clear_finished_benchmark_jobs()

    def clear_finished_solve_jobs(self) -> None:
        self._clear_finished_jobs_for_group("solve")

    def clear_finished_benchmark_jobs(self) -> None:
        self._clear_finished_jobs_for_group("benchmark")

    def delete_selected_solve_job(self) -> None:
        job = self._selected_solve_job()
        if job is None or not job.finished:
            return
        self._delete_finished_job(job, remove_benchmark_rows=False)

    def delete_selected_benchmark_job(self) -> None:
        jobs = [job for job in self._selected_benchmark_jobs() if job.finished]
        if not jobs:
            return
        run_labels = {job.label for job in jobs}
        self.benchmark_rows = [
            row
            for row in self.benchmark_rows
            if row.run_label not in run_labels
        ]
        self._remove_benchmark_filter_labels(run_labels)

        table = self._job_table_for_group("benchmark")
        deleted_labels = []
        deleted_ids = {job.job_id for job in jobs}
        for job in jobs:
            deleted_labels.append(job.label)
            if table is not None and table.exists(job.job_id):
                table.delete(job.job_id)
            if job.job_id in self.jobs:
                del self.jobs[job.job_id]
            self._forget_job_feed(job.job_id)

        if self.selected_job_id in deleted_ids:
            self.selected_job_id = None
        if self.selected_benchmark_job_id in deleted_ids:
            self.selected_benchmark_job_id = None
        self._set_benchmark_status(f"Deleted {', '.join(deleted_labels)}.")
        self._fill_benchmark_table()
        self._schedule_benchmark_chart_refresh()
        self._refresh_job_buttons()

    def _delete_finished_job(self, job: RunJob, *, remove_benchmark_rows: bool) -> None:
        if not job.finished:
            return

        group = self._job_kind_group(job)
        if remove_benchmark_rows and job.kind == "benchmark":
            run_label = job.label
            self.benchmark_rows = [
                row
                for row in self.benchmark_rows
                if row.run_label != run_label
            ]
            self._remove_benchmark_filter_labels({run_label})

        table = self._job_table_for_group(group)
        if table is not None and table.exists(job.job_id):
            table.delete(job.job_id)

        if job.job_id == self.selected_job_id:
            self.selected_job_id = None
        if group == "solve" and job.job_id == self.selected_solve_job_id:
            self.selected_solve_job_id = None
            self._clear_solve_view()
        if group == "benchmark" and job.job_id == self.selected_benchmark_job_id:
            self.selected_benchmark_job_id = None
            self._set_benchmark_status(f"Deleted {job.label}.")

        del self.jobs[job.job_id]
        self._forget_job_feed(job.job_id)

        if remove_benchmark_rows:
            self._fill_benchmark_table()
            self._schedule_benchmark_chart_refresh()
        self._refresh_job_buttons()

    def _clear_finished_jobs_for_group(self, group: str) -> None:
        removed_selected = False
        removed_benchmark_labels = set()
        removed_selected_solve = False
        for job_id, job in list(self.jobs.items()):
            if not job.finished or self._job_kind_group(job) != group:
                continue
            removed_selected = removed_selected or job_id == self.selected_job_id
            if group == "solve" and job_id == self.selected_solve_job_id:
                self.selected_solve_job_id = None
                removed_selected_solve = True
            if group == "benchmark" and job_id == self.selected_benchmark_job_id:
                self.selected_benchmark_job_id = None
            if group == "benchmark":
                removed_benchmark_labels.add(job.label)
            table = self._job_table_for_group(group)
            if table is not None and table.exists(job_id):
                table.delete(job_id)
            del self.jobs[job_id]
            self._forget_job_feed(job_id)

        if removed_selected:
            self.selected_job_id = None
        if removed_selected_solve:
            self._clear_solve_view()
        if removed_benchmark_labels:
            self.benchmark_rows = [
                row
                for row in self.benchmark_rows
                if row.run_label not in removed_benchmark_labels
            ]
            self._remove_benchmark_filter_labels(removed_benchmark_labels)
            self._fill_benchmark_table()
            self._schedule_benchmark_chart_refresh()
        self._refresh_job_buttons()

    def load_selected_solve_job(self) -> None:
        job = self._selected_solve_job()
        if job is not None and job.problem is not None:
            self._display_solve_job(job)
            self._select_job(job.job_id)

    def _clear_solve_view(self) -> None:
        self.current_problem = None
        self.latest_solve_result = None
        self.current_cnf_dimacs = ""
        self.cnf_text.delete("1.0", tk.END)
        self._write_result("Generate or solve a problem to see results.")
        self._refresh_solve_detail_panel()

    def _poll_run_events(self) -> None:
        processed = 0
        deadline = time.perf_counter() + UI_EVENT_BATCH_SECONDS
        self.batching_run_events = True

        try:
            while processed < UI_EVENT_BATCH_MAX and time.perf_counter() < deadline:
                try:
                    event = self.event_queue.get_nowait()
                except queue.Empty:
                    break

                self._handle_run_event(event)
                processed += 1
        finally:
            self.batching_run_events = False
            self._flush_pending_feed_messages()
            if self.job_buttons_refresh_needed:
                self.job_buttons_refresh_needed = False
                self._refresh_job_buttons()

        self.root.after(UI_EVENT_POLL_MS, self._poll_run_events)

    def _handle_run_event(self, event: RunEvent) -> None:
        job_id = event.payload.get("_job_id")
        job = self.jobs.get(job_id) if job_id else None
        prefix = f"{job.label}: " if job is not None else ""
        feed_job_id = job.job_id if job is not None else None

        if event.type == EVENT_LOG:
            self.append_feed(f"{prefix}{event.message}", feed_job_id)
            return

        if event.type == EVENT_PROGRESS:
            self._apply_progress(event, job)
            return

        if event.type == EVENT_ROW:
            row = event.payload.get("row")
            if row is not None:
                if job is not None:
                    row.run_label = job.label
                    job.rows.append(row)
                self.benchmark_rows.append(row)
                if self._benchmark_row_is_visible(row):
                    self._insert_benchmark_row(row)
                self._request_job_buttons_refresh()
            self._apply_progress(event, job)
            return

        if event.type == EVENT_CNF:
            self._apply_cnf_event(event, job)
            return

        if event.type == EVENT_RESULT:
            result = event.payload.get("result")
            if result is not None:
                if job is not None:
                    job.result = result
                    job.status = result.status
                    job.progress_current = 1
                    job.progress_total = 1
                    self._update_job_row(job)
                    if self.selected_job_id == job.job_id:
                        self._display_solve_job(job)
                else:
                    self.latest_solve_result = result
                    self._write_result(self._format_solve_result(result))
                    self._refresh_solve_detail_panel()
                    self._set_runtime_progress(100)
            return

        if event.type == EVENT_ERROR:
            if job is not None and job.finished:
                return
            self.append_feed(f"{prefix}ERROR: {event.message}", feed_job_id)
            if job is not None:
                self._finish_job(job, "Failed")
            messagebox.showerror("Run failed", event.message)
            return

        if event.type == EVENT_CANCELLED:
            if job is not None and job.finished:
                return
            self.append_feed(f"{prefix}{event.message or 'Run cancelled.'}", feed_job_id)
            if job is not None:
                self._finish_job(job, "Cancelled")
            return

        if event.type == EVENT_DONE:
            if job is not None and job.finished:
                return
            self.append_feed(f"{prefix}{event.message or 'Run finished.'}", feed_job_id)
            if job is not None:
                self._finish_job(job, "Done")

    def _apply_progress(self, event: RunEvent, job: RunJob | None = None) -> None:
        if job is not None:
            job.progress_current = event.current
            job.progress_total = event.total
            if event.message:
                job.status = event.message
            self._update_job_row(job)
            return

        if event.total:
            self._set_runtime_progress((event.current or 0) * 100 / event.total)
        if event.message:
            self.run_status.set(event.message)

    def _finish_job(self, job: RunJob, status: str) -> None:
        if job.finished:
            return

        job.finished = True
        job.status = status
        if job.progress_total and job.progress_current is None:
            job.progress_current = job.progress_total
        self._update_job_row(job)

        if job.pending_chart_refresh:
            job.pending_chart_refresh = False
            if len(self.benchmark_rows) <= BENCHMARK_AUTO_CHART_MAX_ROWS:
                self._schedule_benchmark_chart_refresh()
            else:
                self.append_feed(f"{job.label}: Chart auto-refresh skipped for a large benchmark; use Refresh Chart when you are ready.", job.job_id)

    def _apply_cnf_event(self, event: RunEvent, job: RunJob | None = None) -> None:
        payload = event.payload
        problem_data = payload["problem"]
        problem = ProblemInstance(
            name=problem_data["name"],
            problem_type=problem_data["problem_type"],
            clauses=problem_data["clauses"],
            metadata=problem_data.get("metadata", {}),
        )
        if job is not None:
            job.problem = problem
            job.dimacs = payload["dimacs"]
            job.result = None
            if self.selected_job_id == job.job_id:
                self._display_solve_job(job)
            return

        self.current_problem = problem
        self.latest_solve_result = None
        self._set_cnf_preview(payload["dimacs"])
        self._write_result(f"Generated {self.current_problem.clause_count} clauses for {self.current_problem.name}.")
        self._refresh_solve_detail_panel()

    def _display_solve_job(self, job: RunJob) -> None:
        self.current_problem = job.problem
        self.latest_solve_result = job.result
        self._set_cnf_preview(job.dimacs)

        if job.result is not None:
            self._write_result(self._format_solve_result(job.result))
        elif job.problem is not None:
            self._write_result(f"Generated {job.problem.clause_count} clauses for {job.problem.name}.")
        else:
            self._write_result("Waiting for CNF generation...")

        self._refresh_solve_detail_panel()

    def _set_cnf_preview(self, dimacs: str, *, force: bool = False) -> None:
        self.current_cnf_dimacs = dimacs
        self.cnf_text.delete("1.0", tk.END)
        if not dimacs:
            return
        if force or len(dimacs) <= CNF_AUTO_DISPLAY_MAX_CHARS:
            self.cnf_text.insert("1.0", dimacs)
            return

        size_kb = len(dimacs) / 1024
        self.cnf_text.insert(
            "1.0",
            (
                f"CNF preview skipped ({size_kb:.1f} KB, {len(dimacs):,} characters).\n"
                "Use Refresh CNF Preview when you want to load the full DIMACS text."
            ),
        )

    def refresh_cnf_preview(self) -> None:
        if not self.current_cnf_dimacs:
            self._write_result("Generate, load, or select a CNF before refreshing the preview.")
            return
        self._set_cnf_preview(self.current_cnf_dimacs, force=True)

    def _build_solve_tab(self) -> None:
        self.problem_kind = tk.StringVar(value="Sudoku")
        self.solver_name = tk.StringVar(value="CDCL")
        self.solve_timeout_seconds = tk.StringVar(value="30")
        self.advanced_solver_logs = tk.BooleanVar(value=False)
        self.solver_log_level = tk.StringVar(value="Periodic progress")
        self.cdcl_branching = tk.StringVar(value="VSIDS")
        self.cdcl_initial_phase = tk.StringVar(value="Positive first")
        self.cdcl_restarts = tk.BooleanVar(value=False)
        self.cdcl_restart_interval = tk.StringVar(value="100")
        self.cdcl_learned_clause_limit = tk.StringVar(value="")
        self.cdcl_random_seed = tk.StringVar(value="")
        self.walksat_max_tries = tk.StringVar(value="10")
        self.walksat_max_flips = tk.StringVar(value="10000")
        self.walksat_noise = tk.StringVar(value="0.5")
        self.walksat_selection_mode = tk.StringVar(value="Classic WalkSAT")
        self.walksat_adaptive_noise = tk.BooleanVar(value=False)
        self.walksat_random_seed = tk.StringVar(value="")

        toolbar = self._build_top_toolbar(self.solve_tab)
        toolbar.grid(row=0, column=0, sticky="ew")
        self.generate_button = self._toolbar_button(
            toolbar,
            "+ Generate CNF",
            self.generate_cnf,
            style="Generate.TButton",
        )
        self.solve_button = self._toolbar_button(
            toolbar,
            "> Solve",
            self.solve_current,
            style="Primary.TButton",
        )
        self.solve_toolbar_cancel_button = self._toolbar_button(
            toolbar,
            "x Cancel",
            self.cancel_selected_solve_job,
            style="Danger.TButton",
            state=tk.DISABLED,
        )
        self.save_cnf_button = self._toolbar_button(
            toolbar,
            "Save CNF",
            self.save_cnf_dialog,
            style="Export.TButton",
        )
        self.load_dimacs_button = self._toolbar_button(
            toolbar,
            "Load DIMACS",
            self.load_dimacs_dialog,
            style="Export.TButton",
        )
        self.generate_button.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.solve_button.grid(row=0, column=1, sticky="w", padx=(0, 6))
        self.solve_toolbar_cancel_button.grid(row=0, column=2, sticky="w", padx=(0, 12))
        ttk.Label(toolbar, text="Solver").grid(row=0, column=3, sticky="w")
        self.solve_solver_box = ttk.Combobox(
            toolbar,
            textvariable=self.solver_name,
            values=SOLVE_SOLVERS,
            state="readonly",
            width=12,
        )
        self.solve_solver_box.grid(row=0, column=4, sticky="w", padx=(6, 12))
        ttk.Label(toolbar, text="Timeout").grid(row=0, column=5, sticky="w")
        ttk.Entry(toolbar, textvariable=self.solve_timeout_seconds, width=7).grid(row=0, column=6, sticky="w", padx=(6, 12))
        self.save_cnf_button.grid(row=0, column=7, sticky="w", padx=(0, 6))
        self.load_dimacs_button.grid(row=0, column=8, sticky="w")

        workspace = ttk.PanedWindow(self.solve_tab, orient=tk.HORIZONTAL)
        workspace.grid(row=1, column=0, sticky="nsew")
        self.solve_workspace = workspace

        left_shell = ttk.Frame(workspace)
        center = ttk.Frame(workspace)
        detail_shell = ttk.Frame(workspace)
        left_shell.configure(width=340)
        detail_shell.configure(width=320)
        workspace.add(left_shell, weight=0)
        workspace.add(center, weight=1)
        workspace.add(detail_shell, weight=0)

        left = self._build_scrollable_panel(left_shell)
        self.solve_tab._tab_scroll_canvas = left_shell._tab_scroll_canvas
        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)

        controls = ttk.LabelFrame(left, text="Problem", padding=8)
        controls.pack(fill=tk.X)
        controls.columnconfigure(1, weight=1)

        ttk.Label(controls, text="Type").grid(row=0, column=0, sticky="w")
        problem_box = ttk.Combobox(
            controls,
            textvariable=self.problem_kind,
            values=PROBLEM_KINDS,
            state="readonly",
            width=20,
        )
        problem_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        problem_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_problem_form())

        self.problem_description = tk.StringVar()
        ttk.Label(
            controls,
            textvariable=self.problem_description,
            wraplength=215,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self.problem_form = ttk.LabelFrame(left, text="Input", padding=8)
        self.problem_form.pack(fill=tk.BOTH, expand=True, pady=(10, 0))
        self.problem_form.columnconfigure(0, weight=1)

        solve_jobs_host = ttk.Frame(left)
        solve_jobs_host.pack(fill=tk.X, pady=(10, 0))
        solve_jobs_host.columnconfigure(0, weight=1)
        self._build_solve_jobs_panel(solve_jobs_host, row=0)

        solver_controls = ttk.LabelFrame(left, text="Solver Options", padding=8)
        solver_controls.pack(fill=tk.X, pady=(10, 0))
        solver_controls.columnconfigure(1, weight=1)

        self.solve_solver_guide = self._build_solver_guide(solver_controls, row=0, wraplength=200)

        ttk.Checkbutton(
            solver_controls,
            text="Advanced solver logs",
            variable=self.advanced_solver_logs,
            command=self._refresh_solver_log_controls,
        ).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.solver_log_label = ttk.Label(solver_controls, text="Log detail")
        self.solver_log_label.grid(row=2, column=0, sticky="w", pady=(8, 0))
        self.solver_log_box = ttk.Combobox(
            solver_controls,
            textvariable=self.solver_log_level,
            values=("Periodic progress", "Verbose debug"),
            state=tk.DISABLED,
            width=20,
        )
        self.solver_log_box.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        self.solve_cdcl_options_frame = self._build_cdcl_option_group(
            solver_controls,
            3,
            self.cdcl_branching,
            self.cdcl_initial_phase,
            self.cdcl_restarts,
            self.cdcl_restart_interval,
            self.cdcl_learned_clause_limit,
            self.cdcl_random_seed,
            width=20,
        )
        self.solve_walksat_options_frame = self._build_walksat_option_group(
            solver_controls,
            4,
            self.walksat_max_tries,
            self.walksat_max_flips,
            self.walksat_noise,
            self.walksat_selection_mode,
            self.walksat_adaptive_noise,
            self.walksat_random_seed,
            width=20,
        )

        self.solve_result_pane = ttk.PanedWindow(center, orient=tk.VERTICAL)
        self.solve_result_pane.grid(row=0, column=0, sticky="nsew")
        cnf_frame = ttk.LabelFrame(self.solve_result_pane, text="CNF Preview", padding=6)
        result_frame = ttk.LabelFrame(self.solve_result_pane, text="Result", padding=6)
        self.solve_result_pane.add(cnf_frame, weight=2)
        self.solve_result_pane.add(result_frame, weight=1)
        cnf_frame.rowconfigure(1, weight=1)
        cnf_frame.columnconfigure(0, weight=1)
        result_frame.rowconfigure(0, weight=1)
        result_frame.columnconfigure(0, weight=1)

        cnf_tools = ttk.Frame(cnf_frame)
        cnf_tools.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 6))
        self.refresh_cnf_button = ttk.Button(
            cnf_tools,
            text="Refresh CNF Preview",
            command=self.refresh_cnf_preview,
        )
        self.refresh_cnf_button.pack(side=tk.RIGHT)
        self.cnf_text = tk.Text(cnf_frame, height=22, wrap="none")
        self.cnf_text.grid(row=1, column=0, sticky="nsew")
        yscroll = ttk.Scrollbar(cnf_frame, orient=tk.VERTICAL, command=self.cnf_text.yview)
        yscroll.grid(row=1, column=1, sticky="ns")
        self.cnf_text.configure(yscrollcommand=yscroll.set)

        self.result_text = tk.Text(result_frame, height=13, wrap="word")
        self.result_text.grid(row=0, column=0, sticky="nsew")
        result_scroll = ttk.Scrollbar(result_frame, orient=tk.VERTICAL, command=self.result_text.yview)
        result_scroll.grid(row=0, column=1, sticky="ns")
        self.result_text.configure(yscrollcommand=result_scroll.set)
        self.root.after(80, self._set_initial_solve_result_sash)

        self._build_solve_detail_panel(detail_shell)

        self._refresh_problem_form()
        self._refresh_solver_log_controls()

    def _set_initial_solve_result_sash(self) -> None:
        if not hasattr(self, "solve_result_pane"):
            return
        try:
            height = self.solve_result_pane.winfo_height()
            if height > 60:
                self.solve_result_pane.sashpos(0, max(140, int(height * 0.62)))
        except tk.TclError:
            pass

    def _build_solve_action_buttons(self, parent, row: int) -> None:
        actions = ttk.LabelFrame(parent, text="Actions", padding=6)
        actions.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        self.generate_button = ttk.Button(
            actions,
            text="Generate CNF",
            command=self.generate_cnf,
            style="Generate.TButton",
        )
        self.solve_button = ttk.Button(
            actions,
            text="Solve",
            command=self.solve_current,
            style="Primary.TButton",
        )
        self.save_cnf_button = ttk.Button(
            actions,
            text="Save CNF",
            command=self.save_cnf_dialog,
            style="Export.TButton",
        )
        self.load_dimacs_button = ttk.Button(
            actions,
            text="Load DIMACS",
            command=self.load_dimacs_dialog,
            style="Export.TButton",
        )

        self.generate_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.solve_button.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self.save_cnf_button.grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
        self.load_dimacs_button.grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=(6, 0))

    def _build_solve_jobs_panel(self, parent, row: int) -> None:
        panel = ttk.LabelFrame(parent, text="Solve Jobs", padding=6)
        panel.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        panel.columnconfigure(0, weight=1)

        compact_widths = {"label": 130, "status": 82, "progress": 82}
        self.solve_jobs_table = self._build_job_table(
            panel,
            self._on_solve_job_selected,
            height=3,
            widths=compact_widths,
            selectmode="extended",
        )
        solve_scroll = ttk.Scrollbar(panel, orient=tk.VERTICAL, command=self.solve_jobs_table.yview)
        self.solve_jobs_table.configure(yscrollcommand=solve_scroll.set)
        self.solve_jobs_table.grid(row=0, column=0, columnspan=2, sticky="ew")
        solve_scroll.grid(row=0, column=2, sticky="ns")
        self.solve_jobs_scrollbar = solve_scroll

        self.solve_cancel_button = ttk.Button(
            panel,
            text="Cancel Selected",
            command=self.cancel_selected_solve_job,
            state=tk.DISABLED,
            style="Danger.TButton",
        )
        self.solve_load_button = ttk.Button(
            panel,
            text="Load Selected",
            command=self.load_selected_solve_job,
            state=tk.DISABLED,
            style="Primary.TButton",
        )
        self.solve_clear_finished_button = ttk.Button(
            panel,
            text="Clear Finished",
            command=self.clear_finished_solve_jobs,
            state=tk.DISABLED,
        )
        self.solve_delete_button = ttk.Button(
            panel,
            text="Delete Selected",
            command=self.delete_selected_solve_job,
            state=tk.DISABLED,
            style="Danger.TButton",
        )
        self.solve_cancel_button.grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
        self.solve_load_button.grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=(6, 0))
        self.solve_clear_finished_button.grid(row=2, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
        self.solve_delete_button.grid(row=2, column=1, sticky="ew", padx=(3, 0), pady=(6, 0))

    def _build_job_table(
        self,
        parent,
        select_callback,
        height: int = 4,
        widths: dict[str, int] | None = None,
        selectmode: str = "browse",
    ):
        table = ttk.Treeview(
            parent,
            columns=("label", "status", "progress"),
            show="headings",
            height=height,
            selectmode=selectmode,
        )
        headings = {
            "label": "Job",
            "status": "Status",
            "progress": "Progress",
        }
        widths = widths or {
            "label": 210,
            "status": 120,
            "progress": 96,
        }
        for column in ("label", "status", "progress"):
            table.heading(column, text=headings[column])
            table.column(column, width=widths[column])
        table.tag_configure("muted", foreground="#6b7280")
        table.bind("<<TreeviewSelect>>", select_callback)
        return table

    def _build_solve_detail_panel(self, parent=None) -> None:
        parent = parent or self.solve_tab
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        self.solve_detail_frame = ttk.LabelFrame(parent, text="Problem Info", padding=8)
        self.solve_detail_frame.grid(row=0, column=0, sticky="nsew")
        self.solve_detail_frame.columnconfigure(0, weight=1)
        self.solve_detail_frame.rowconfigure(0, weight=1)

        self.solve_detail_pane = ttk.PanedWindow(self.solve_detail_frame, orient=tk.VERTICAL)
        self.solve_detail_pane.grid(row=0, column=0, sticky="nsew")

        summary_frame = ttk.Frame(self.solve_detail_pane)
        summary_frame.rowconfigure(1, weight=1)
        summary_frame.columnconfigure(0, weight=1)
        ttk.Label(summary_frame, text="Stats and response").grid(row=0, column=0, sticky="w")
        self.solve_detail_text = tk.Text(summary_frame, height=8, width=34, wrap=tk.WORD)
        self.solve_detail_text.grid(row=1, column=0, sticky="nsew")
        detail_scroll = ttk.Scrollbar(summary_frame, orient=tk.VERTICAL, command=self.solve_detail_text.yview)
        detail_scroll.grid(row=1, column=1, sticky="ns")
        self.solve_detail_text.configure(yscrollcommand=detail_scroll.set)
        ttk.Button(summary_frame, text="Copy response", command=self.copy_solve_response).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        self.solve_detail_notebook = ttk.Notebook(self.solve_detail_pane)
        self.solve_detail_pane.add(summary_frame, weight=1)
        self.solve_detail_pane.add(self.solve_detail_notebook, weight=2)

        input_frame = ttk.Frame(self.solve_detail_notebook, padding=6)
        input_frame.rowconfigure(1, weight=1)
        input_frame.columnconfigure(0, weight=1)
        self.solve_detail_notebook.add(input_frame, text="Input")
        self.solve_input_label = tk.StringVar(value="Problem data")
        ttk.Label(input_frame, textvariable=self.solve_input_label).grid(row=0, column=0, sticky="w")
        self.solve_input_text = tk.Text(input_frame, height=14, width=34, wrap=tk.WORD)
        self.solve_input_text.grid(row=1, column=0, sticky="nsew")
        input_scroll = ttk.Scrollbar(input_frame, orient=tk.VERTICAL, command=self.solve_input_text.yview)
        input_scroll.grid(row=1, column=1, sticky="ns")
        self.solve_input_text.configure(yscrollcommand=input_scroll.set)
        ttk.Button(input_frame, text="Copy data", command=self.copy_solve_data).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        visual_frame = ttk.Frame(self.solve_detail_notebook, padding=6)
        visual_frame.rowconfigure(2, weight=1)
        visual_frame.columnconfigure(0, weight=1)
        self.solve_detail_notebook.add(visual_frame, text="Graph")
        self.solve_visual_status = tk.StringVar(value="Generate or solve a graph problem to preview it.")
        ttk.Label(visual_frame, textvariable=self.solve_visual_status, wraplength=300).grid(row=0, column=0, sticky="ew")
        graph_buttons = ttk.Frame(visual_frame)
        graph_buttons.grid(row=1, column=0, sticky="ew", pady=(4, 6))
        graph_buttons.columnconfigure(0, weight=1)
        graph_buttons.columnconfigure(1, weight=1)
        self.refresh_solve_graph_button = ttk.Button(
            graph_buttons,
            text="@ Refresh graph",
            command=lambda: self.render_solve_graph(force=True),
            state=tk.DISABLED,
        )
        self.refresh_solve_graph_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.open_solve_graph_button = ttk.Button(
            graph_buttons,
            text="Open Graph",
            command=self.open_solve_graph_window,
            state=tk.DISABLED,
        )
        self.open_solve_graph_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.solve_visual_frame = ttk.Frame(visual_frame)
        self.solve_visual_frame.grid(row=2, column=0, sticky="nsew")
        self.solve_visual_frame.rowconfigure(0, weight=1)
        self.solve_visual_frame.columnconfigure(0, weight=1)

        self._write_text_widget(self.solve_detail_text, "Generate or solve a problem to see stats and response.")
        self._write_text_widget(self.solve_input_text, "Generate or solve a problem to see problem-specific input data.")

    def _clear_form(self) -> None:
        for child in self.problem_form.winfo_children():
            child.destroy()

    def _build_cdcl_option_controls(
        self,
        parent,
        start_row: int,
        branching_var,
        phase_var,
        restarts_var,
        restart_interval_var,
        learned_limit_var,
        random_seed_var,
        width: int,
    ) -> None:
        ttk.Label(parent, text="CDCL branching").grid(row=start_row, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            parent,
            textvariable=branching_var,
            values=("VSIDS", "Most frequent", "MOMS", "DLIS", "Random"),
            state="readonly",
            width=width,
        ).grid(row=start_row, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        ttk.Label(parent, text="Initial phase").grid(row=start_row + 1, column=0, sticky="w", pady=(8, 0))
        ttk.Combobox(
            parent,
            textvariable=phase_var,
            values=("Positive first", "Negative first", "Polarity based", "Random"),
            state="readonly",
            width=width,
        ).grid(row=start_row + 1, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        ttk.Checkbutton(parent, text="Restarts", variable=restarts_var).grid(row=start_row + 2, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=restart_interval_var, width=width).grid(row=start_row + 2, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        ttk.Label(parent, text="Learned limit").grid(row=start_row + 3, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=learned_limit_var, width=width).grid(row=start_row + 3, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        ttk.Label(parent, text="Random seed").grid(row=start_row + 4, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=random_seed_var, width=width).grid(row=start_row + 4, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

    def _build_cdcl_option_group(
        self,
        parent,
        row: int,
        branching_var,
        phase_var,
        restarts_var,
        restart_interval_var,
        learned_limit_var,
        random_seed_var,
        width: int,
    ):
        frame = ttk.LabelFrame(parent, text="CDCL Options", padding=6)
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        frame.columnconfigure(1, weight=1)
        self._build_cdcl_option_controls(
            frame,
            0,
            branching_var,
            phase_var,
            restarts_var,
            restart_interval_var,
            learned_limit_var,
            random_seed_var,
            width,
        )
        return frame

    def _build_walksat_option_controls(
        self,
        parent,
        start_row: int,
        max_tries_var,
        max_flips_var,
        noise_var,
        selection_mode_var,
        adaptive_noise_var,
        random_seed_var,
        width: int,
        show_strategy: bool = True,
        help_text: str | None = None,
    ) -> None:
        row = start_row
        ttk.Label(parent, text="Max tries").grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=max_tries_var, width=width).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        row += 1
        ttk.Label(parent, text="Max flips").grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=max_flips_var, width=width).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        row += 1
        ttk.Label(parent, text="Noise").grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=noise_var, width=width).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        if show_strategy:
            row += 1
            ttk.Label(parent, text="Strategy").grid(row=row, column=0, sticky="w", pady=(8, 0))
            ttk.Combobox(
                parent,
                textvariable=selection_mode_var,
                values=WALKSAT_STRATEGIES,
                state="readonly",
                width=width,
            ).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        row += 1
        ttk.Checkbutton(parent, text="Adaptive noise", variable=adaptive_noise_var).grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="w",
            pady=(8, 0),
        )

        row += 1
        ttk.Label(parent, text="Random seed").grid(row=row, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(parent, textvariable=random_seed_var, width=width).grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        default_help_text = (
            "Classic mixes random and greedy flips. ProbSAT favors low-break, "
            "high-make flips. Adaptive noise increases randomness after stagnation."
        )
        row += 1
        ttk.Label(parent, text=help_text or default_help_text, wraplength=260, justify="left").grid(
            row=row,
            column=0,
            columnspan=2,
            sticky="ew",
            pady=(8, 0),
        )

    def _build_walksat_option_group(
        self,
        parent,
        row: int,
        max_tries_var,
        max_flips_var,
        noise_var,
        selection_mode_var,
        adaptive_noise_var,
        random_seed_var,
        width: int,
        show_strategy: bool = True,
        help_text: str | None = None,
    ):
        frame = ttk.LabelFrame(parent, text="WalkSAT Options", padding=6)
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        frame.columnconfigure(1, weight=1)
        self._build_walksat_option_controls(
            frame,
            0,
            max_tries_var,
            max_flips_var,
            noise_var,
            selection_mode_var,
            adaptive_noise_var,
            random_seed_var,
            width,
            show_strategy=show_strategy,
            help_text=help_text,
        )
        return frame

    def _build_probsat_option_group(
        self,
        parent,
        row: int,
        max_tries_var,
        max_flips_var,
        noise_var,
        adaptive_noise_var,
        random_seed_var,
        width: int,
    ):
        frame = ttk.LabelFrame(parent, text="ProbSAT Options", padding=6)
        frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        frame.columnconfigure(1, weight=1)
        self._build_walksat_option_controls(
            frame,
            0,
            max_tries_var,
            max_flips_var,
            noise_var,
            None,
            adaptive_noise_var,
            random_seed_var,
            width,
            show_strategy=False,
            help_text="ProbSAT uses the same local-search limits, but always chooses flips with the probabilistic low-break strategy.",
        )
        return frame

    def _build_solver_guide(self, parent, row: int | None = None, wraplength: int = 250):
        frame = ttk.LabelFrame(parent, text="Solver Guide", padding=6)
        frame.columnconfigure(1, weight=1)
        guide_lines = []

        for index, (name, description) in enumerate(SOLVER_GUIDE_ROWS):
            ttk.Label(frame, text=name, width=8).grid(row=index, column=0, sticky="nw", pady=1)
            ttk.Label(frame, text=description, wraplength=wraplength, justify="left").grid(row=index, column=1, sticky="ew", padx=(8, 0), pady=1)
            guide_lines.append(f"{name}: {description}")

        frame.guide_text = "\n".join(guide_lines)
        if row is not None:
            frame.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(4, 0))
        return frame

    def _refresh_solver_log_controls(self) -> None:
        if self.advanced_solver_logs.get():
            self.solver_log_box.configure(state="readonly")
        else:
            self.solver_log_box.configure(state=tk.DISABLED)

    def _refresh_problem_form(self) -> None:
        self._clear_form()
        kind = self.problem_kind.get()
        self.problem_description.set(PROBLEM_DESCRIPTIONS.get(kind, ""))

        if kind == "Sudoku":
            self._build_sudoku_form()
        elif kind in GRAPH_PROBLEM_KINDS:
            self._build_graph_form()
        elif kind == "N-Queens":
            self._build_n_queens_form()
        elif kind == "Random 3-SAT":
            self._build_random_3sat_form()
        else:
            self._build_dimacs_form()

    def _build_sudoku_form(self) -> None:
        self.sudoku_size = tk.IntVar(value=4)
        top = ttk.Frame(self.problem_form)
        top.pack(fill=tk.X)
        ttk.Label(top, text="Size").pack(side=tk.LEFT)
        size_box = ttk.Combobox(top, textvariable=self.sudoku_size, values=SUDOKU_SIZES, state="readonly", width=6)
        size_box.pack(side=tk.LEFT, padx=(8, 0))
        size_box.bind("<<ComboboxSelected>>", lambda _event: self._build_sudoku_grid())
        ttk.Button(top, text="Clear", command=lambda: self._build_sudoku_grid()).pack(side=tk.RIGHT)

        self.sudoku_viewport = ttk.Frame(self.problem_form)
        self.sudoku_viewport.pack(fill=tk.X, anchor="nw")
        self.sudoku_viewport.columnconfigure(0, weight=1)
        self.sudoku_viewport.rowconfigure(0, weight=1)

        self.sudoku_canvas = tk.Canvas(
            self.sudoku_viewport,
            width=300,
            height=300,
            highlightthickness=0,
            borderwidth=0,
        )
        self.sudoku_canvas.grid(row=0, column=0, sticky="nsew")
        sudoku_y_scroll = ttk.Scrollbar(self.sudoku_viewport, orient=tk.VERTICAL, command=self.sudoku_canvas.yview)
        sudoku_y_scroll.grid(row=0, column=1, sticky="ns")
        sudoku_x_scroll = ttk.Scrollbar(self.sudoku_viewport, orient=tk.HORIZONTAL, command=self.sudoku_canvas.xview)
        sudoku_x_scroll.grid(row=1, column=0, sticky="ew")
        self.sudoku_canvas.configure(xscrollcommand=sudoku_x_scroll.set, yscrollcommand=sudoku_y_scroll.set)

        self.sudoku_grid_frame = ttk.Frame(self.sudoku_canvas)
        self.sudoku_canvas_window = self.sudoku_canvas.create_window(
            0,
            0,
            window=self.sudoku_grid_frame,
            anchor="nw",
        )
        self.sudoku_grid_frame.bind("<Configure>", self._update_sudoku_scroll_region)
        self.sudoku_canvas.bind("<MouseWheel>", self._on_sudoku_mousewheel)
        self.sudoku_grid_frame.bind("<MouseWheel>", self._on_sudoku_mousewheel)
        self.sudoku_entries: list[list[ttk.Entry]] = []
        self._build_sudoku_grid()

    def _update_sudoku_scroll_region(self, _event=None) -> None:
        try:
            self.sudoku_canvas.configure(scrollregion=self.sudoku_canvas.bbox("all"))
        except tk.TclError:
            return

    def _on_sudoku_mousewheel(self, event) -> str:
        if event.state & 0x0001:
            self.sudoku_canvas.xview_scroll(int(-1 * (event.delta / 120)), "units")
        else:
            self.sudoku_canvas.yview_scroll(int(-1 * (event.delta / 120)), "units")
        return "break"

    def _build_sudoku_grid(self) -> None:
        for child in self.sudoku_grid_frame.winfo_children():
            child.destroy()

        size = int(self.sudoku_size.get())
        entry_width = 2 if size >= 16 else 3
        canvas_width = 340 if size >= 16 else 300
        canvas_height = 320 if size >= 16 else 300
        self.sudoku_canvas.configure(width=canvas_width, height=canvas_height)
        self.sudoku_entries = []

        for r in range(size):
            row_entries = []
            for c in range(size):
                entry = ttk.Entry(self.sudoku_grid_frame, width=entry_width, justify="center")
                entry.bind("<MouseWheel>", self._on_sudoku_mousewheel)
                entry.grid(row=r, column=c, padx=0, pady=0)
                row_entries.append(entry)
            self.sudoku_entries.append(row_entries)

        self.sudoku_canvas.xview_moveto(0)
        self.sudoku_canvas.yview_moveto(0)
        self._update_sudoku_scroll_region()

    def _build_n_queens_form(self) -> None:
        fields = ttk.Frame(self.problem_form)
        fields.pack(fill=tk.X)
        fields.columnconfigure(1, weight=1)
        self.n_queens_size = tk.StringVar(value="8")

        ttk.Label(fields, text="Board size n").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(fields, textvariable=self.n_queens_size, width=12).grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=2)

    def _build_random_3sat_form(self) -> None:
        fields = ttk.Frame(self.problem_form)
        fields.pack(fill=tk.X)
        fields.columnconfigure(1, weight=1)
        self.random_3sat_variables = tk.StringVar(value="50")
        self.random_3sat_clauses = tk.StringVar(value="210")
        self.random_3sat_seed = tk.StringVar(value="1")
        self.random_3sat_mode = tk.StringVar(value="Planted SAT")
        self.random_3sat_sat_percentage = tk.StringVar(value="50")

        ttk.Label(fields, text="Variables").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(fields, textvariable=self.random_3sat_variables, width=12).grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=2)
        ttk.Label(fields, text="Clauses").grid(row=1, column=0, sticky="w", pady=2)
        ttk.Entry(fields, textvariable=self.random_3sat_clauses, width=12).grid(row=1, column=1, sticky="ew", padx=(8, 0), pady=2)
        ttk.Label(fields, text="Seed").grid(row=2, column=0, sticky="w", pady=2)
        ttk.Entry(fields, textvariable=self.random_3sat_seed, width=12).grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=2)
        ttk.Label(fields, text="Formula mode").grid(row=3, column=0, sticky="w", pady=2)
        mode_combo = ttk.Combobox(
            fields,
            textvariable=self.random_3sat_mode,
            values=RANDOM_3SAT_MODES,
            state="readonly",
            width=12,
        )
        mode_combo.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=2)
        mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_random_3sat_controls())
        ttk.Label(fields, text="SAT target % (blank=random)").grid(row=4, column=0, sticky="w", pady=2)
        self.random_3sat_sat_percentage_entry = ttk.Entry(fields, textvariable=self.random_3sat_sat_percentage, width=12)
        self.random_3sat_sat_percentage_entry.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=2)
        self._refresh_random_3sat_controls()

    def _refresh_random_3sat_controls(self) -> None:
        if not hasattr(self, "random_3sat_sat_percentage_entry"):
            return
        state = tk.NORMAL if self.random_3sat_mode.get() == "Random" else tk.DISABLED
        self.random_3sat_sat_percentage_entry.configure(state=state)

    def _random_3sat_sat_percentage_from_text(self, text: str) -> float | None:
        raw = str(text).strip()
        if not raw:
            return None
        return float(raw)

    def _build_graph_form(self) -> None:
        self.graph_mode = tk.StringVar(value="Manual")
        self.graph_field_entries = {}
        mode_row = ttk.Frame(self.problem_form)
        mode_row.pack(fill=tk.X)
        ttk.Radiobutton(mode_row, text="Manual", variable=self.graph_mode, value="Manual", command=self._refresh_graph_controls).pack(side=tk.LEFT)
        ttk.Radiobutton(mode_row, text="G(n,p)", variable=self.graph_mode, value="Probability", command=self._refresh_graph_controls).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Radiobutton(mode_row, text="G(n,m)", variable=self.graph_mode, value="Exact edges", command=self._refresh_graph_controls).pack(side=tk.LEFT, padx=(12, 0))
        ttk.Radiobutton(mode_row, text="G(n,d)", variable=self.graph_mode, value="Average degree", command=self._refresh_graph_controls).pack(side=tk.LEFT, padx=(12, 0))

        fields = ttk.Frame(self.problem_form)
        fields.pack(fill=tk.X, pady=(10, 0))
        fields.columnconfigure(1, weight=1)
        self.graph_nodes = tk.StringVar(value="10")
        self.graph_colors = tk.StringVar(value="3")
        self.graph_target = tk.StringVar(value="3")
        self.graph_probability = tk.StringVar(value="0.3")
        self.graph_edge_count = tk.StringVar(value="10")
        self.graph_average_degree = tk.StringVar(value="4")
        self.graph_seed = tk.StringVar(value="")

        labels = [("nodes", "Nodes", self.graph_nodes)]
        if self.problem_kind.get() == "Graph Coloring":
            labels.append(("colors", "Colors", self.graph_colors))
        if self.problem_kind.get() in ("Independent Set", "Clique"):
            labels.append(("target", "Target k", self.graph_target))
        labels.extend([
            ("probability", "Probability p", self.graph_probability),
            ("edge_count", "Exact edges m", self.graph_edge_count),
            ("average_degree", "Average degree d", self.graph_average_degree),
            ("seed", "Seed", self.graph_seed),
        ])

        for row, (key, label, variable) in enumerate(labels):
            ttk.Label(fields, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(fields, textvariable=variable, width=12)
            entry.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=2)
            self.graph_field_entries[key] = entry

        self.graph_edge_label = ttk.Label(self.problem_form, text="Manual edges: 1-2, 2-3")
        self.graph_edge_label.pack(anchor="w", pady=(10, 2))
        self.edge_text = tk.Text(self.problem_form, height=7, width=32)
        self.edge_text.pack(fill=tk.BOTH, expand=True)
        self.edge_text.insert("1.0", "1-2, 2-3, 3-4")
        self._refresh_graph_controls()

    def _refresh_graph_controls(self) -> None:
        if not hasattr(self, "graph_field_entries"):
            return

        mode = self.graph_mode.get()
        active_by_key = {
            "nodes": True,
            "colors": True,
            "target": True,
            "probability": mode == "Probability",
            "edge_count": mode == "Exact edges",
            "average_degree": mode == "Average degree",
            "seed": mode != "Manual",
        }

        for key, entry in self.graph_field_entries.items():
            entry.configure(state=tk.NORMAL if active_by_key.get(key, False) else tk.DISABLED)

        manual = mode == "Manual"
        if hasattr(self, "edge_text"):
            self.edge_text.configure(state=tk.NORMAL if manual else tk.DISABLED)

    def _build_dimacs_form(self) -> None:
        self.dimacs_loaded_problem_type = tk.StringVar(value="DIMACS")
        type_row = ttk.Frame(self.problem_form)
        type_row.pack(fill=tk.X, pady=(0, 8))
        ttk.Label(type_row, text="Treat as").pack(side=tk.LEFT)
        ttk.Combobox(
            type_row,
            textvariable=self.dimacs_loaded_problem_type,
            values=("DIMACS", "Sudoku", "Graph Coloring", "N-Queens", "Random 3-SAT", "Hamiltonian Path", "Independent Set", "Clique"),
            state="readonly",
            width=22,
        ).pack(side=tk.LEFT, padx=(8, 0))
        ttk.Label(self.problem_form, text="Paste DIMACS or plain CNF clauses").pack(anchor="w")
        self.dimacs_input = tk.Text(self.problem_form, height=18, width=36)
        self.dimacs_input.pack(fill=tk.BOTH, expand=True, pady=(4, 0))
        self.dimacs_input.insert("1.0", "p cnf 2 2\n1 2 0\n-1 2 0\n")

    def _read_sudoku_grid(self) -> list[list[int]]:
        grid = []

        for row_entries in self.sudoku_entries:
            row = []
            for entry in row_entries:
                raw = entry.get().strip()
                row.append(0 if raw == "" else int(raw))
            grid.append(row)

        return grid

    def build_problem_from_form(self) -> ProblemInstance:
        kind = self.problem_kind.get()

        if kind == "Sudoku":
            return sudoku_problem(self._read_sudoku_grid())

        if kind == "N-Queens":
            return n_queens_problem(int(self.n_queens_size.get()))

        if kind == "Random 3-SAT":
            seed = self.random_3sat_seed.get().strip()
            formula_mode = self.random_3sat_mode.get()
            return random_3sat_problem(
                int(self.random_3sat_variables.get()),
                int(self.random_3sat_clauses.get()),
                seed=int(seed) if seed else None,
                formula_mode=formula_mode,
                sat_percentage=self._random_3sat_sat_percentage_from_text(self.random_3sat_sat_percentage.get()) if formula_mode == "Random" else None,
            )

        if kind == "Graph Coloring":
            nodes = int(self.graph_nodes.get())
            colors = int(self.graph_colors.get())

            if self.graph_mode.get() == "Probability":
                probability = float(self.graph_probability.get())
                seed = self.graph_seed.get().strip()
                return random_graph_coloring_problem(nodes, probability, colors, seed=int(seed) if seed else None)

            if self.graph_mode.get() == "Exact edges":
                edge_count = int(self.graph_edge_count.get())
                seed = self.graph_seed.get().strip()
                return exact_edges_graph_coloring_problem(nodes, edge_count, colors, seed=int(seed) if seed else None)

            if self.graph_mode.get() == "Average degree":
                average_degree = float(self.graph_average_degree.get())
                seed = self.graph_seed.get().strip()
                return average_degree_graph_coloring_problem(nodes, average_degree, colors, seed=int(seed) if seed else None)

            edge_text = self.edge_text.get("1.0", tk.END)
            return manual_graph_coloring_problem(nodes, colors, edge_text)

        if kind == "Hamiltonian Path":
            nodes = int(self.graph_nodes.get())

            if self.graph_mode.get() == "Probability":
                probability = float(self.graph_probability.get())
                seed = self.graph_seed.get().strip()
                return random_hamiltonian_path_problem(nodes, probability, seed=int(seed) if seed else None)

            if self.graph_mode.get() == "Exact edges":
                edge_count = int(self.graph_edge_count.get())
                seed = self.graph_seed.get().strip()
                return exact_edges_hamiltonian_path_problem(nodes, edge_count, seed=int(seed) if seed else None)

            if self.graph_mode.get() == "Average degree":
                average_degree = float(self.graph_average_degree.get())
                seed = self.graph_seed.get().strip()
                return average_degree_hamiltonian_path_problem(nodes, average_degree, seed=int(seed) if seed else None)

            return manual_hamiltonian_path_problem(nodes, self.edge_text.get("1.0", tk.END))

        if kind == "Independent Set":
            nodes = int(self.graph_nodes.get())
            target = int(self.graph_target.get())

            if self.graph_mode.get() == "Probability":
                probability = float(self.graph_probability.get())
                seed = self.graph_seed.get().strip()
                return random_independent_set_problem(nodes, probability, target, seed=int(seed) if seed else None)

            if self.graph_mode.get() == "Exact edges":
                edge_count = int(self.graph_edge_count.get())
                seed = self.graph_seed.get().strip()
                return exact_edges_independent_set_problem(nodes, edge_count, target, seed=int(seed) if seed else None)

            if self.graph_mode.get() == "Average degree":
                average_degree = float(self.graph_average_degree.get())
                seed = self.graph_seed.get().strip()
                return average_degree_independent_set_problem(nodes, average_degree, target, seed=int(seed) if seed else None)

            return manual_independent_set_problem(nodes, target, self.edge_text.get("1.0", tk.END))

        if kind == "Clique":
            nodes = int(self.graph_nodes.get())
            target = int(self.graph_target.get())

            if self.graph_mode.get() == "Probability":
                probability = float(self.graph_probability.get())
                seed = self.graph_seed.get().strip()
                return random_clique_problem(nodes, probability, target, seed=int(seed) if seed else None)

            if self.graph_mode.get() == "Exact edges":
                edge_count = int(self.graph_edge_count.get())
                seed = self.graph_seed.get().strip()
                return exact_edges_clique_problem(nodes, edge_count, target, seed=int(seed) if seed else None)

            if self.graph_mode.get() == "Average degree":
                average_degree = float(self.graph_average_degree.get())
                seed = self.graph_seed.get().strip()
                return average_degree_clique_problem(nodes, average_degree, target, seed=int(seed) if seed else None)

            return manual_clique_problem(nodes, target, self.edge_text.get("1.0", tk.END))

        text = self.dimacs_input.get("1.0", tk.END)
        return dimacs_problem_from_text(text)

    def _problem_snapshot_from_form(self) -> dict:
        kind = self.problem_kind.get()

        if kind == "Sudoku":
            return {"kind": "Sudoku", "grid": self._read_sudoku_grid()}

        if kind == "N-Queens":
            return {"kind": "N-Queens", "size": int(self.n_queens_size.get())}

        if kind == "Random 3-SAT":
            seed = self.random_3sat_seed.get().strip()
            formula_mode = self.random_3sat_mode.get()
            return {
                "kind": "Random 3-SAT",
                "variables": int(self.random_3sat_variables.get()),
                "clauses": int(self.random_3sat_clauses.get()),
                "seed": int(seed) if seed else None,
                "formula_mode": formula_mode,
                "sat_percentage": self._random_3sat_sat_percentage_from_text(self.random_3sat_sat_percentage.get()) if formula_mode == "Random" else None,
            }

        if kind in GRAPH_PROBLEM_KINDS:
            mode = self.graph_mode.get()
            snapshot = {
                "kind": kind,
                "mode": mode,
                "nodes": int(self.graph_nodes.get()),
                "seed": int(self.graph_seed.get()) if self.graph_seed.get().strip() else None,
            }
            if kind == "Graph Coloring":
                snapshot["colors"] = int(self.graph_colors.get())
            if kind in ("Independent Set", "Clique"):
                snapshot["target"] = int(self.graph_target.get())
            if mode == "Probability":
                snapshot["probability"] = float(self.graph_probability.get())
            elif mode == "Exact edges":
                snapshot["edge_count"] = int(self.graph_edge_count.get())
            elif mode == "Average degree":
                snapshot["average_degree"] = float(self.graph_average_degree.get())
            else:
                snapshot["edge_text"] = self.edge_text.get("1.0", tk.END)
            return snapshot

        return {
            "kind": "DIMACS/CNF",
            "text": self.dimacs_input.get("1.0", tk.END),
            "loaded_problem_type": self.dimacs_loaded_problem_type.get(),
        }

    def _solver_logging_options_from_form(self) -> dict:
        return self._logging_options(
            self.advanced_solver_logs.get(),
            self.solver_log_level.get(),
            self.cdcl_branching.get(),
            self.cdcl_initial_phase.get(),
            self.cdcl_restarts.get(),
            self.cdcl_restart_interval.get(),
            self.cdcl_learned_clause_limit.get(),
            self.cdcl_random_seed.get(),
            self.walksat_max_tries.get(),
            self.walksat_max_flips.get(),
            self.walksat_noise.get(),
            self.walksat_selection_mode.get(),
            self.walksat_adaptive_noise.get(),
            self.walksat_random_seed.get(),
        )

    def _benchmark_logging_options_from_form(self) -> dict:
        return self._logging_options(
            self.bench_advanced_solver_logs.get(),
            self.bench_solver_log_level.get(),
            self.bench_cdcl_branching.get(),
            self.bench_cdcl_initial_phase.get(),
            self.bench_cdcl_restarts.get(),
            self.bench_cdcl_restart_interval.get(),
            self.bench_cdcl_learned_clause_limit.get(),
            self.bench_cdcl_random_seed.get(),
            self.bench_walksat_max_tries.get(),
            self.bench_walksat_max_flips.get(),
            self.bench_walksat_noise.get(),
            "Classic WalkSAT",
            self.bench_walksat_adaptive_noise.get(),
            self.bench_walksat_random_seed.get(),
            self.bench_probsat_max_tries.get(),
            self.bench_probsat_max_flips.get(),
            self.bench_probsat_noise.get(),
            self.bench_probsat_adaptive_noise.get(),
            self.bench_probsat_random_seed.get(),
        )

    def _logging_options(
        self,
        enabled: bool,
        level: str,
        branching: str = "VSIDS",
        initial_phase: str = "Positive first",
        restarts_enabled: bool = False,
        restart_interval: str = "100",
        learned_clause_limit: str = "",
        random_seed: str = "",
        walksat_max_tries: str = "10",
        walksat_max_flips: str = "10000",
        walksat_noise: str = "0.5",
        walksat_selection_mode: str = "Classic WalkSAT",
        walksat_adaptive_noise: bool = False,
        walksat_random_seed: str = "",
        probsat_max_tries: str | None = None,
        probsat_max_flips: str | None = None,
        probsat_noise: str | None = None,
        probsat_adaptive_noise: bool | None = None,
        probsat_random_seed: str | None = None,
    ) -> dict:
        if not enabled:
            options = {"mode": "normal"}
        elif level == "Verbose debug":
            options = {"mode": "debug", "progress_interval": 50, "verbose_limit": 200}
        else:
            options = {"mode": "periodic", "progress_interval": 50, "verbose_limit": 200}

        options["branching"] = branching
        options["initial_phase"] = initial_phase
        options["restart_interval"] = self._optional_int_text(restart_interval) if restarts_enabled else None
        options["learned_clause_limit"] = self._optional_int_text(learned_clause_limit)
        options["random_seed"] = self._optional_int_text(random_seed)
        options["cdcl_random_seed"] = options["random_seed"]
        options["walksat_max_tries"] = self._positive_int_text(walksat_max_tries)
        options["walksat_max_flips"] = self._positive_int_text(walksat_max_flips)
        options["walksat_noise"] = self._probability_text(walksat_noise)
        options["walksat_selection_mode"] = self._walksat_selection_mode_key(walksat_selection_mode)
        options["walksat_adaptive_noise"] = bool(walksat_adaptive_noise)
        options["walksat_random_seed"] = self._optional_int_text(walksat_random_seed)
        options["probsat_max_tries"] = self._positive_int_text(probsat_max_tries if probsat_max_tries is not None else walksat_max_tries)
        options["probsat_max_flips"] = self._positive_int_text(probsat_max_flips if probsat_max_flips is not None else walksat_max_flips)
        options["probsat_noise"] = self._probability_text(probsat_noise if probsat_noise is not None else walksat_noise)
        options["probsat_adaptive_noise"] = bool(probsat_adaptive_noise) if probsat_adaptive_noise is not None else bool(walksat_adaptive_noise)
        options["probsat_random_seed"] = self._optional_int_text(probsat_random_seed if probsat_random_seed is not None else walksat_random_seed)
        return options

    def _walksat_selection_mode_key(self, text: str) -> str:
        return "probsat" if str(text).strip().lower() == "probsat" else "walksat"

    def _optional_int_text(self, text: str) -> int | None:
        raw = str(text).strip()
        if not raw:
            return None
        value = int(raw)
        return value if value > 0 else None

    def _positive_int_text(self, text: str) -> int:
        value = int(str(text).strip())
        if value <= 0:
            raise ValueError("WalkSAT numeric limits must be positive")
        return value

    def _probability_text(self, text: str) -> float:
        value = float(str(text).strip())
        if value < 0 or value > 1:
            raise ValueError("WalkSAT noise must be between 0 and 1")
        return value

    def generate_cnf(self) -> None:
        try:
            snapshot = self._problem_snapshot_from_form()
            self._start_process_worker(
                f"Generating CNF for {snapshot['kind']}",
                generate_cnf_process,
                snapshot,
                kind="generate",
            )
        except Exception as exc:
            messagebox.showerror("Cannot generate CNF", str(exc))

    def solve_current(self) -> None:
        try:
            snapshot = self._problem_snapshot_from_form()
            solver_name = self.solver_name.get()
            logging_options = self._solver_logging_options_from_form()
            timeout_seconds = parse_timeout_seconds(self.solve_timeout_seconds.get())
            self._start_process_worker(
                f"Solving {snapshot['kind']} with {solver_name}",
                solve_process,
                snapshot,
                solver_name,
                logging_options,
                timeout_seconds,
                kind="solve",
            )
        except Exception as exc:
            messagebox.showerror("Cannot solve problem", str(exc))

    def _solve_detail_row(self) -> BenchmarkRow | None:
        if self.current_problem is None:
            return None

        result = self.latest_solve_result
        stats = result.stats if result is not None else {}
        metadata = self.current_problem.metadata or {}
        return BenchmarkRow(
            case_name=self.current_problem.name,
            problem_type=self.current_problem.problem_type,
            solver=result.solver if result is not None else self.solver_name.get(),
            status=result.status if result is not None else "CNF generated",
            elapsed=result.elapsed if result is not None else 0.0,
            clauses=self.current_problem.clause_count,
            variables=self.current_problem.variable_count,
            repeat=1,
            detail=self._problem_detail_text(self.current_problem),
            conflicts=stats.get("conflicts", "-"),
            decisions=stats.get("decisions", "-"),
            propagations=stats.get("propagations", "-"),
            learned_clauses=stats.get("learned_clauses", "-"),
            generation_mode=metadata.get("mode", ""),
            edge_count=metadata.get("edges", "-"),
            node_count=metadata.get("nodes", "-"),
            graph_edges=metadata.get("graph_edges", []),
            decoded=result.decoded if result is not None else None,
            seed=metadata.get("seed", "-"),
            solver_options=stats.get("solver_options", ""),
            problem_metadata=dict(metadata),
            problem_clauses=self.current_problem.clauses,
        )

    def _problem_detail_text(self, problem: ProblemInstance) -> str:
        metadata = problem.metadata or {}
        if problem.problem_type == "Sudoku":
            return f"size={metadata.get('size', '?')}, givens={metadata.get('givens', '?')}"
        if problem.problem_type == "N-Queens":
            return f"n={metadata.get('size', '?')}"
        if problem.problem_type == "Random 3-SAT":
            mode = metadata.get("mode", "random")
            if mode == "Random" and metadata.get("sat_percentage") is not None:
                mode = f"{mode} ({metadata.get('sat_percentage'):g}% SAT, selected {metadata.get('selected_mode', '-')})"
            return (
                f"n={metadata.get('variables', '?')}, "
                f"m={metadata.get('clauses_requested', '?')}, "
                f"ratio={metadata.get('ratio', 0):.2f}, "
                f"{mode}"
            )
        if problem.problem_type in ("Independent Set", "Clique"):
            return f"k={metadata.get('target', '?')}, edges={metadata.get('edges', '-')}"
        if problem.problem_type in ("Graph Coloring", "Hamiltonian Path"):
            mode = metadata.get("mode", "")
            edges = metadata.get("edges", "-")
            return f"{mode}, edges={edges}" if mode else f"edges={edges}"
        return ""

    def _refresh_solve_detail_panel(self) -> None:
        if not hasattr(self, "solve_detail_text"):
            return

        row = self._solve_detail_row()
        if row is None:
            self._write_text_widget(self.solve_detail_text, "Generate or solve a problem to see stats and response.")
            self._write_text_widget(self.solve_input_text, "Generate or solve a problem to see problem-specific input data.")
            self._clear_solve_graph_preview("Generate or solve a graph problem to preview it.")
            self.refresh_solve_graph_button.configure(state=tk.DISABLED)
            self.open_solve_graph_button.configure(state=tk.DISABLED)
            return

        self._write_text_widget(self.solve_detail_text, self._format_benchmark_row_details(row))
        self.solve_input_label.set(self._benchmark_problem_data_label(row))
        self._write_text_widget(self.solve_input_text, self._format_benchmark_problem_data(row))

        if not self._is_graph_benchmark_row(row):
            self._clear_solve_graph_preview(f"{row.problem_type} rows show their data in the Input tab.")
            self.refresh_solve_graph_button.configure(state=tk.DISABLED)
            self.open_solve_graph_button.configure(state=tk.DISABLED)
            return

        if not row.graph_edges and row.node_count == "-":
            self._clear_solve_graph_preview("No graph data stored for this problem.")
            self.refresh_solve_graph_button.configure(state=tk.DISABLED)
            self.open_solve_graph_button.configure(state=tk.DISABLED)
            return

        policy = self._graph_preview_policy(row.node_count, len(row.graph_edges))
        if policy == "auto":
            self.refresh_solve_graph_button.configure(state=tk.NORMAL)
            self.open_solve_graph_button.configure(state=tk.NORMAL)
            self.render_solve_graph(force=False)
        elif policy == "manual":
            self.refresh_solve_graph_button.configure(state=tk.NORMAL)
            self.open_solve_graph_button.configure(state=tk.NORMAL)
            self._clear_solve_graph_preview("Graph is moderately large; use Refresh graph when needed.")
        else:
            self.refresh_solve_graph_button.configure(state=tk.DISABLED)
            self.open_solve_graph_button.configure(state=tk.DISABLED)
            self._clear_solve_graph_preview("Graph too large to preview safely.")

    def copy_solve_data(self) -> None:
        row = self._solve_detail_row()
        if row is None:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._format_benchmark_problem_data(row))

    def copy_solve_response(self) -> None:
        row = self._solve_detail_row()
        if row is None or row.decoded is None:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._format_decoded(row.decoded))

    def _format_solve_result(self, result) -> str:
        lines = [
            f"Problem: {self.current_problem.name if self.current_problem else ''}",
            f"Solver: {result.solver}",
            f"Status: {result.status}",
            f"Time: {result.elapsed:.6f}s",
            f"Clauses: {result.clauses}",
            f"Variables: {result.variables}",
        ]

        for key in (
            "decisions",
            "conflicts",
            "propagations",
            "learned_clauses",
            "tries",
            "flips",
            "best_unsatisfied",
            "termination_reason",
            "final_noise",
        ):
            if key in result.stats:
                lines.append(f"{key.replace('_', ' ').title()}: {result.stats[key]}")

        if result.decoded is not None:
            lines.append("")
            lines.append("Decoded solution:")
            lines.append(self._format_decoded(result.decoded))

        return "\n".join(lines)

    def _format_decoded(self, decoded) -> str:
        if isinstance(decoded, list):
            return "\n".join(" ".join(f"{value:2}" for value in row) for row in decoded)

        if isinstance(decoded, dict):
            if "board" in decoded:
                lines = []
                if "positions" in decoded:
                    lines.append(f"Positions: {decoded['positions']}")
                    lines.append("")
                lines.extend(str(row) for row in decoded["board"])
                return "\n".join(lines)
            if "path" in decoded:
                return "Path: " + " -> ".join(str(node) for node in decoded["path"])
            if "selected" in decoded:
                return "Selected nodes: " + ", ".join(str(node) for node in decoded["selected"])
            return "\n".join(f"{key}: {decoded[key]}" for key in sorted(decoded))

        return str(decoded)

    def _write_result(self, text: str) -> None:
        self.result_text.delete("1.0", tk.END)
        self.result_text.insert("1.0", text)

    def save_cnf_dialog(self) -> None:
        if self.current_problem is None:
            messagebox.showinfo("No CNF yet", "Generate CNF first, then save it.")
            return

        default_name = self.current_problem.name.replace(" ", "_").replace("/", "_") + ".cnf"
        path = filedialog.asksaveasfilename(
            initialdir=str(INPUT_GENERATED),
            initialfile=default_name,
            defaultextension=".cnf",
            filetypes=[("DIMACS CNF", "*.cnf"), ("All files", "*.*")],
        )

        if path:
            save_dimacs(path, self.current_problem.clauses, [self.current_problem.name, f"type={self.current_problem.problem_type}"])
            self._write_result(f"Saved CNF to {path}")

    def load_dimacs_dialog(self) -> None:
        path = filedialog.askopenfilename(
            initialdir="input",
            filetypes=[("DIMACS CNF", "*.cnf"), ("All files", "*.*")],
        )

        if not path:
            return

        try:
            clauses = load_dimacs(path)
            original_text = Path(path).read_text(encoding="utf-8")
            inferred_type = self._infer_dimacs_problem_type(original_text)
            chosen_type = self._choose_loaded_dimacs_type(inferred_type)
            if chosen_type is None:
                return

            text = clauses_to_dimacs(clauses, [Path(path).name, f"type={chosen_type}"])
            self.problem_kind.set("DIMACS/CNF")
            self._refresh_problem_form()
            self.dimacs_loaded_problem_type.set(chosen_type)
            self.dimacs_input.delete("1.0", tk.END)
            self.dimacs_input.insert("1.0", text)
            self.current_problem = dimacs_problem_from_text(text, name=Path(path).name, problem_type=chosen_type)
            self.latest_solve_result = None
            self._set_cnf_preview(text)
            self._write_result(f"Loaded {len(clauses)} clauses from {path}\nType: {chosen_type}")
            self._refresh_solve_detail_panel()
        except Exception as exc:
            messagebox.showerror("Cannot load DIMACS", str(exc))

    def _infer_dimacs_problem_type(self, text: str) -> str:
        valid_types = {"DIMACS", "Sudoku", "Graph Coloring", "N-Queens", "Random 3-SAT", "Hamiltonian Path", "Independent Set", "Clique"}
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line.startswith("c"):
                continue
            comment = line[1:].strip()
            if comment.startswith("type="):
                problem_type = comment.split("=", 1)[1].strip()
                if problem_type in valid_types:
                    return problem_type
        return "DIMACS"

    def _choose_loaded_dimacs_type(self, initial_type: str) -> str | None:
        dialog = tk.Toplevel(self.root)
        dialog.title("Choose Problem Type")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.resizable(False, False)

        chosen = tk.StringVar(value=initial_type)
        result = {"value": None}

        ttk.Label(dialog, text="Treat loaded CNF as:").grid(row=0, column=0, columnspan=2, sticky="w", padx=12, pady=(12, 6))
        ttk.Combobox(
            dialog,
            textvariable=chosen,
            values=("DIMACS", "Sudoku", "Graph Coloring", "N-Queens", "Random 3-SAT", "Hamiltonian Path", "Independent Set", "Clique"),
            state="readonly",
            width=28,
        ).grid(row=1, column=0, columnspan=2, sticky="ew", padx=12)
        ttk.Label(
            dialog,
            text="This labels the loaded CNF for solving/details. Decoded answers need original encoder metadata.",
            wraplength=320,
            justify="left",
        ).grid(row=2, column=0, columnspan=2, sticky="ew", padx=12, pady=(8, 12))

        def accept() -> None:
            result["value"] = chosen.get()
            dialog.destroy()

        def cancel() -> None:
            dialog.destroy()

        ttk.Button(dialog, text="Cancel", command=cancel).grid(row=3, column=0, sticky="ew", padx=(12, 4), pady=(0, 12))
        ttk.Button(dialog, text="Load", command=accept).grid(row=3, column=1, sticky="ew", padx=(4, 12), pady=(0, 12))
        dialog.columnconfigure(0, weight=1)
        dialog.columnconfigure(1, weight=1)
        self._center_dialog(dialog)
        dialog.wait_window()
        return result["value"]

    def _center_dialog(self, dialog) -> None:
        dialog.update_idletasks()
        width = dialog.winfo_width()
        height = dialog.winfo_height()

        root_x = self.root.winfo_rootx()
        root_y = self.root.winfo_rooty()
        root_width = self.root.winfo_width()
        root_height = self.root.winfo_height()

        if root_width > 1 and root_height > 1:
            x = root_x + (root_width - width) // 2
            y = root_y + (root_height - height) // 2
        else:
            x = (dialog.winfo_screenwidth() - width) // 2
            y = (dialog.winfo_screenheight() - height) // 2

        dialog.geometry(f"+{max(0, x)}+{max(0, y)}")

    def _build_benchmark_tab(self) -> None:
        self.bench_problem = tk.StringVar(value="Graph Coloring")
        self.bench_nodes = tk.StringVar(value="10,20,30")
        self.bench_generation_mode = tk.StringVar(value="Probability")
        self.bench_probs = tk.StringVar(value="0.1,0.3")
        self.bench_edges = tk.StringVar(value="10,20,40")
        self.bench_average_degrees = tk.StringVar(value="3,4,5,6,7")
        self.bench_colors = tk.StringVar(value="2,3")
        self.bench_targets = tk.StringVar(value="2,3")
        self.bench_n_queens_sizes = tk.StringVar(value="4,8")
        self.bench_3sat_preset = tk.StringVar(value=RANDOM_3SAT_PRESET_CUSTOM)
        self.bench_3sat_preset_summary = tk.StringVar(value="Custom Random 3-SAT sweep.")
        self.bench_3sat_variables = tk.StringVar(value="20,50,100")
        self.bench_3sat_ratios = tk.StringVar(value="3.5,4.2,5.0")
        self.bench_3sat_mode = tk.StringVar(value="Planted SAT")
        self.bench_3sat_sat_percentage = tk.StringVar(value="50")
        self.bench_repeats = tk.StringVar(value="1")
        self.bench_timeout_seconds = tk.StringVar(value="30")
        self.bench_seed = tk.StringVar(value="1")
        self.bench_cdcl = tk.BooleanVar(value=True)
        self.bench_dpll = tk.BooleanVar(value=False)
        self.bench_walksat = tk.BooleanVar(value=False)
        self.bench_probsat = tk.BooleanVar(value=False)
        self.bench_advanced_solver_logs = tk.BooleanVar(value=False)
        self.bench_solver_log_level = tk.StringVar(value="Periodic progress")
        self.bench_cdcl_branching = tk.StringVar(value="VSIDS")
        self.bench_cdcl_initial_phase = tk.StringVar(value="Positive first")
        self.bench_cdcl_restarts = tk.BooleanVar(value=False)
        self.bench_cdcl_restart_interval = tk.StringVar(value="100")
        self.bench_cdcl_learned_clause_limit = tk.StringVar(value="")
        self.bench_cdcl_random_seed = tk.StringVar(value="")
        self.bench_walksat_max_tries = tk.StringVar(value="10")
        self.bench_walksat_max_flips = tk.StringVar(value="10000")
        self.bench_walksat_noise = tk.StringVar(value="0.5")
        self.bench_walksat_selection_mode = tk.StringVar(value="Classic WalkSAT")
        self.bench_walksat_adaptive_noise = tk.BooleanVar(value=False)
        self.bench_walksat_random_seed = tk.StringVar(value="")
        self.bench_probsat_max_tries = tk.StringVar(value="10")
        self.bench_probsat_max_flips = tk.StringVar(value="10000")
        self.bench_probsat_noise = tk.StringVar(value="0.5")
        self.bench_probsat_adaptive_noise = tk.BooleanVar(value=False)
        self.bench_probsat_random_seed = tk.StringVar(value="")
        self.bench_suite_graph_coloring = tk.BooleanVar(value=False)
        self.bench_suite_hamiltonian = tk.BooleanVar(value=False)
        self.bench_suite_independent = tk.BooleanVar(value=True)
        self.bench_suite_clique = tk.BooleanVar(value=True)
        self.bench_sudoku_size_vars = {
            size: tk.BooleanVar(value=size in (4, 9))
            for size in SUDOKU_BENCHMARK_SIZES
        }
        self.chart_metric = tk.StringVar(value="Raw Time")
        self.chart_view = tk.StringVar(value="Raw runs")

        toolbar = self._build_top_toolbar(self.benchmark_tab)
        toolbar.grid(row=0, column=0, sticky="ew")
        self.run_benchmark_button = self._toolbar_button(
            toolbar,
            "> Run Benchmark",
            self.run_benchmark,
            style="Primary.TButton",
        )
        self.benchmark_toolbar_cancel_button = self._toolbar_button(
            toolbar,
            "x Cancel Selected",
            self.cancel_selected_benchmark_job,
            style="Danger.TButton",
            state=tk.DISABLED,
        )
        self.skip_benchmark_button = self._toolbar_button(
            toolbar,
            "Skip Case",
            self.skip_current_benchmark_case,
            style="Warning.TButton",
            state=tk.DISABLED,
        )
        self.export_csv_button = self._toolbar_button(
            toolbar,
            "Export CSV",
            self.export_benchmark_csv,
            style="Export.TButton",
        )
        self.export_3sat_csv_button = self._toolbar_button(
            toolbar,
            "Export 3-SAT CSV",
            self.export_random_3sat_csv,
            style="Export.TButton",
        )
        self.export_chart_button = self._toolbar_button(
            toolbar,
            "Export Chart",
            self.export_benchmark_chart,
            style="Export.TButton",
        )
        self.clear_benchmark_table_button = self._toolbar_button(
            toolbar,
            "Clear Table",
            self.clear_benchmark_table,
            style="Danger.TButton",
            state=tk.DISABLED,
        )
        self.run_benchmark_button.grid(row=0, column=0, sticky="w", padx=(0, 6))
        self.benchmark_toolbar_cancel_button.grid(row=0, column=1, sticky="w", padx=(0, 6))
        self.skip_benchmark_button.grid(row=0, column=2, sticky="w", padx=(0, 12))
        ttk.Label(toolbar, text="Metric").grid(row=0, column=3, sticky="w")
        self.chart_metric_box = ttk.Combobox(
            toolbar,
            textvariable=self.chart_metric,
            values=("Raw Time", "Log Time", "Normalized Time", "Conflicts", "Decisions"),
            state="readonly",
            width=16,
        )
        self.chart_metric_box.grid(row=0, column=4, sticky="w", padx=(6, 12))
        ttk.Label(toolbar, text="View").grid(row=0, column=5, sticky="w")
        self.chart_view_box = ttk.Combobox(
            toolbar,
            textvariable=self.chart_view,
            values=("Raw runs", "Average repeats"),
            state="readonly",
            width=14,
        )
        self.chart_view_box.grid(row=0, column=6, sticky="w", padx=(6, 12))
        self.refresh_chart_button = self._toolbar_button(toolbar, "@ Refresh Chart", self.draw_benchmark_chart)
        self.refresh_chart_button.grid(row=0, column=7, sticky="w", padx=(0, 6))
        self.export_csv_button.grid(row=0, column=8, sticky="w", padx=(0, 6))
        self.export_3sat_csv_button.grid(row=0, column=9, sticky="w", padx=(0, 6))
        self.export_chart_button.grid(row=0, column=10, sticky="w", padx=(0, 6))
        self.clear_benchmark_table_button.grid(row=0, column=11, sticky="w")

        workspace = ttk.PanedWindow(self.benchmark_tab, orient=tk.HORIZONTAL)
        workspace.grid(row=1, column=0, sticky="nsew")
        self.benchmark_workspace = workspace

        left_shell = ttk.Frame(workspace)
        center = ttk.Frame(workspace)
        detail_shell = ttk.Frame(workspace)
        left_shell.configure(width=BENCHMARK_LEFT_PANEL_WIDTH)
        detail_shell.configure(width=BENCHMARK_DETAIL_PANEL_WIDTH)
        self.benchmark_left_shell = left_shell
        self.benchmark_detail_shell = detail_shell
        self.benchmark_sash_initialized = False
        workspace.add(left_shell, weight=0)
        workspace.add(center, weight=1)
        workspace.add(detail_shell, weight=0)
        left = self._build_scrollable_panel(left_shell)
        self.benchmark_tab._tab_scroll_canvas = left_shell._tab_scroll_canvas

        self.benchmark_controls = ttk.LabelFrame(left, text="Benchmark", padding=8)
        self.benchmark_controls.pack(fill=tk.X)
        self.benchmark_controls.columnconfigure(1, weight=1)

        ttk.Label(self.benchmark_controls, text="Problem").grid(row=0, column=0, sticky="w")
        problem_box = ttk.Combobox(
            self.benchmark_controls,
            textvariable=self.bench_problem,
            values=BENCHMARK_PROBLEMS,
            state="readonly",
            width=18,
        )
        problem_box.grid(row=0, column=1, sticky="ew", padx=(8, 0))
        problem_box.bind("<<ComboboxSelected>>", lambda _event: self._refresh_benchmark_form())

        self.benchmark_description = tk.StringVar()
        ttk.Label(
            self.benchmark_controls,
            textvariable=self.benchmark_description,
            wraplength=250,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        self.benchmark_input_frame = ttk.Frame(self.benchmark_controls)
        self.benchmark_input_frame.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(8, 0))

        ttk.Label(self.benchmark_controls, text="Repeats").grid(row=3, column=0, sticky="w", pady=(10, 0))
        ttk.Entry(self.benchmark_controls, textvariable=self.bench_repeats, width=18).grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=(10, 0))

        ttk.Label(self.benchmark_controls, text="Timeout (s)").grid(row=4, column=0, sticky="w", pady=(8, 0))
        ttk.Entry(self.benchmark_controls, textvariable=self.bench_timeout_seconds, width=18).grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))

        self._build_benchmark_jobs_panel(row=5)

        solver_frame = ttk.LabelFrame(self.benchmark_controls, text="Solvers", padding=6)
        solver_frame.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        solver_frame.columnconfigure(0, weight=1)
        solver_frame.columnconfigure(1, weight=1)
        solver_frame.columnconfigure(2, weight=1)
        solver_frame.columnconfigure(3, weight=1)
        ttk.Checkbutton(solver_frame, text="CDCL", variable=self.bench_cdcl).grid(row=0, column=0, sticky="w")
        ttk.Checkbutton(solver_frame, text="DPLL", variable=self.bench_dpll).grid(row=0, column=1, sticky="w")
        ttk.Checkbutton(solver_frame, text="WalkSAT", variable=self.bench_walksat).grid(row=0, column=2, sticky="w")
        ttk.Checkbutton(solver_frame, text="ProbSAT", variable=self.bench_probsat).grid(row=0, column=3, sticky="w")
        self.benchmark_solver_guide = self._build_solver_guide(solver_frame, row=None, wraplength=190)
        self.benchmark_solver_guide.grid(row=1, column=0, columnspan=4, sticky="ew", pady=(6, 0))

        ttk.Checkbutton(
            self.benchmark_controls,
            text="Advanced solver logs",
            variable=self.bench_advanced_solver_logs,
            command=self._refresh_benchmark_log_controls,
        ).grid(row=7, column=0, columnspan=2, sticky="w", pady=(8, 0))
        self.bench_log_label = ttk.Label(self.benchmark_controls, text="Log detail")
        self.bench_log_label.grid(row=8, column=0, sticky="w", pady=(8, 0))
        self.bench_log_box = ttk.Combobox(
            self.benchmark_controls,
            textvariable=self.bench_solver_log_level,
            values=("Periodic progress", "Verbose debug"),
            state=tk.DISABLED,
            width=16,
        )
        self.bench_log_box.grid(row=8, column=1, sticky="ew", padx=(8, 0), pady=(8, 0))
        self.benchmark_cdcl_options_frame = self._build_cdcl_option_group(
            self.benchmark_controls,
            9,
            self.bench_cdcl_branching,
            self.bench_cdcl_initial_phase,
            self.bench_cdcl_restarts,
            self.bench_cdcl_restart_interval,
            self.bench_cdcl_learned_clause_limit,
            self.bench_cdcl_random_seed,
            width=16,
        )
        self.benchmark_walksat_options_frame = self._build_walksat_option_group(
            self.benchmark_controls,
            10,
            self.bench_walksat_max_tries,
            self.bench_walksat_max_flips,
            self.bench_walksat_noise,
            self.bench_walksat_selection_mode,
            self.bench_walksat_adaptive_noise,
            self.bench_walksat_random_seed,
            width=16,
            show_strategy=False,
            help_text="Benchmark WalkSAT uses the classic random/greedy flip strategy. ProbSAT has its own configuration below.",
        )
        self.benchmark_probsat_options_frame = self._build_probsat_option_group(
            self.benchmark_controls,
            11,
            self.bench_probsat_max_tries,
            self.bench_probsat_max_flips,
            self.bench_probsat_noise,
            self.bench_probsat_adaptive_noise,
            self.bench_probsat_random_seed,
            width=16,
        )

        center.rowconfigure(0, weight=1)
        center.columnconfigure(0, weight=1)
        self.benchmark_results_pane = ttk.PanedWindow(center, orient=tk.VERTICAL)
        self.benchmark_results_pane.grid(row=0, column=0, sticky="nsew")

        table_frame = ttk.LabelFrame(self.benchmark_results_pane, text="Runs", padding=6)
        table_frame.rowconfigure(0, weight=1)
        table_frame.columnconfigure(0, weight=1)

        columns = ("run", "case", "type", "detail", "solver", "options", "status", "time", "conflicts", "decisions")
        self.benchmark_table = ttk.Treeview(table_frame, columns=columns, show="headings", height=10)
        headings = {
            "run": "Run",
            "case": "Case",
            "type": "Type",
            "detail": "Detail",
            "solver": "Solver",
            "options": "Options",
            "status": "Status",
            "time": "Time",
            "conflicts": "Conflicts",
            "decisions": "Decisions",
        }
        widths = {
            "run": 55,
            "case": 170,
            "type": 105,
            "detail": 120,
            "solver": 70,
            "options": 120,
            "status": 75,
            "time": 80,
            "conflicts": 75,
            "decisions": 75,
        }
        for column in columns:
            self.benchmark_table.heading(column, text=headings[column])
            self.benchmark_table.column(column, width=widths.get(column, 100))
        self.benchmark_table.grid(row=0, column=0, sticky="nsew")
        self.benchmark_table.bind("<<TreeviewSelect>>", self._on_benchmark_row_selected)
        table_scroll = ttk.Scrollbar(table_frame, orient=tk.VERTICAL, command=self.benchmark_table.yview)
        table_scroll.grid(row=0, column=1, sticky="ns")
        table_xscroll = ttk.Scrollbar(table_frame, orient=tk.HORIZONTAL, command=self.benchmark_table.xview)
        table_xscroll.grid(row=1, column=0, sticky="ew")
        self.benchmark_table.configure(yscrollcommand=table_scroll.set, xscrollcommand=table_xscroll.set)

        self.chart_frame = ttk.LabelFrame(self.benchmark_results_pane, text="Chart", padding=8)
        self.chart_frame.rowconfigure(0, weight=1)
        self.chart_frame.columnconfigure(0, weight=1)
        self.benchmark_results_pane.add(table_frame, weight=3)
        self.benchmark_results_pane.add(self.chart_frame, weight=1)

        self._build_benchmark_detail_panel(detail_shell)

        self._refresh_benchmark_form()
        self._refresh_benchmark_log_controls()

    def _set_initial_benchmark_sash(self) -> None:
        if not hasattr(self, "benchmark_workspace") or self.benchmark_sash_initialized:
            return
        try:
            self.benchmark_workspace.update_idletasks()
            total_width = self.benchmark_workspace.winfo_width()
            if total_width <= 1:
                return
            left_width = min(BENCHMARK_LEFT_PANEL_WIDTH, max(260, total_width - BENCHMARK_DETAIL_PANEL_WIDTH - 260))
            self.benchmark_workspace.sashpos(0, left_width)
            if len(self.benchmark_workspace.panes()) >= 3:
                detail_start = max(left_width + 260, total_width - BENCHMARK_DETAIL_PANEL_WIDTH)
                self.benchmark_workspace.sashpos(1, detail_start)
            self.benchmark_sash_initialized = True
        except tk.TclError:
            pass

    def _build_benchmark_action_buttons(self, row: int) -> None:
        actions = ttk.LabelFrame(self.benchmark_controls, text="Actions", padding=6)
        actions.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        actions.columnconfigure(0, weight=1)
        actions.columnconfigure(1, weight=1)

        self.run_benchmark_button = ttk.Button(
            actions,
            text="Run Benchmark",
            command=self.run_benchmark,
            style="Primary.TButton",
        )
        self.skip_benchmark_button = ttk.Button(
            actions,
            text="Skip Current",
            command=self.skip_current_benchmark_case,
            state=tk.DISABLED,
            style="Warning.TButton",
        )
        self.export_csv_button = ttk.Button(
            actions,
            text="Export CSV",
            command=self.export_benchmark_csv,
            style="Export.TButton",
        )
        self.export_chart_button = ttk.Button(
            actions,
            text="Export Chart",
            command=self.export_benchmark_chart,
            style="Export.TButton",
        )
        self.clear_benchmark_table_button = ttk.Button(
            actions,
            text="Clear Table",
            command=self.clear_benchmark_table,
            state=tk.DISABLED,
            style="Danger.TButton",
        )

        self.run_benchmark_button.grid(row=0, column=0, sticky="ew", padx=(0, 3))
        self.skip_benchmark_button.grid(row=0, column=1, sticky="ew", padx=(3, 0))
        self.export_csv_button.grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
        self.export_chart_button.grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=(6, 0))
        self.clear_benchmark_table_button.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def _build_benchmark_jobs_panel(self, row: int) -> None:
        panel = ttk.LabelFrame(self.benchmark_controls, text="Benchmark Jobs", padding=6)
        panel.grid(row=row, column=0, columnspan=2, sticky="ew", pady=(8, 0))
        panel.columnconfigure(0, weight=1)
        panel.columnconfigure(1, weight=1)

        self.benchmark_jobs_table = self._build_job_table(
            panel,
            self._on_benchmark_job_selected,
            selectmode="extended",
        )
        benchmark_scroll = ttk.Scrollbar(panel, orient=tk.VERTICAL, command=self.benchmark_jobs_table.yview)
        self.benchmark_jobs_table.configure(yscrollcommand=benchmark_scroll.set)
        self.benchmark_jobs_table.grid(row=0, column=0, columnspan=2, sticky="ew")
        benchmark_scroll.grid(row=0, column=2, sticky="ns")
        self.benchmark_jobs_scrollbar = benchmark_scroll

        self.benchmark_cancel_button = ttk.Button(
            panel,
            text="Cancel Selected",
            command=self.cancel_selected_benchmark_job,
            state=tk.DISABLED,
            style="Danger.TButton",
        )
        self.benchmark_skip_job_button = ttk.Button(
            panel,
            text="Skip Selected Case",
            command=self.skip_current_benchmark_case,
            state=tk.DISABLED,
            style="Warning.TButton",
        )
        self.benchmark_show_selected_button = ttk.Button(
            panel,
            text="Show Selected Runs",
            command=self.show_selected_benchmark_run,
            state=tk.DISABLED,
            style="Primary.TButton",
        )
        self.benchmark_show_all_button = ttk.Button(
            panel,
            text="Show All Runs",
            command=self.show_all_benchmark_runs,
            state=tk.DISABLED,
        )
        self.benchmark_clear_finished_jobs_button = ttk.Button(
            panel,
            text="Clear Finished Jobs",
            command=self.clear_finished_benchmark_jobs,
            state=tk.DISABLED,
        )
        self.benchmark_clear_all_results_button = ttk.Button(
            panel,
            text="Hide Results",
            command=self.clear_all_benchmark_results,
            state=tk.DISABLED,
        )
        self.benchmark_delete_job_button = ttk.Button(
            panel,
            text="Delete Selected Jobs",
            command=self.delete_selected_benchmark_job,
            state=tk.DISABLED,
            style="Danger.TButton",
        )

        self.benchmark_cancel_button.grid(row=1, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
        self.benchmark_skip_job_button.grid(row=1, column=1, sticky="ew", padx=(3, 0), pady=(6, 0))
        self.benchmark_show_selected_button.grid(row=2, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
        self.benchmark_show_all_button.grid(row=2, column=1, sticky="ew", padx=(3, 0), pady=(6, 0))
        self.benchmark_clear_finished_jobs_button.grid(row=3, column=0, sticky="ew", padx=(0, 3), pady=(6, 0))
        self.benchmark_clear_all_results_button.grid(row=3, column=1, sticky="ew", padx=(3, 0), pady=(6, 0))
        self.benchmark_delete_job_button.grid(row=4, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        self.benchmark_status = tk.StringVar(value="Showing all benchmark rows.")
        ttk.Label(panel, textvariable=self.benchmark_status, wraplength=230).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))

    def _build_benchmark_detail_panel(self, parent=None) -> None:
        parent = parent or self.benchmark_tab
        parent.rowconfigure(0, weight=1)
        parent.columnconfigure(0, weight=1)
        self.benchmark_detail_frame = ttk.LabelFrame(parent, text="Selected Case", padding=8)
        self.benchmark_detail_frame.grid(row=0, column=0, sticky="nsew")
        self.benchmark_detail_frame.columnconfigure(0, weight=1)
        self.benchmark_detail_frame.rowconfigure(0, weight=1)

        self.benchmark_detail_pane = ttk.PanedWindow(self.benchmark_detail_frame, orient=tk.VERTICAL)
        self.benchmark_detail_pane.grid(row=0, column=0, sticky="nsew")

        summary_frame = ttk.Frame(self.benchmark_detail_pane)
        summary_frame.rowconfigure(1, weight=1)
        summary_frame.columnconfigure(0, weight=1)
        ttk.Label(summary_frame, text="Stats and response").grid(row=0, column=0, sticky="w")
        self.benchmark_detail_text = tk.Text(summary_frame, height=8, width=34, wrap=tk.WORD)
        self.benchmark_detail_text.grid(row=1, column=0, sticky="nsew")
        detail_scroll = ttk.Scrollbar(summary_frame, orient=tk.VERTICAL, command=self.benchmark_detail_text.yview)
        detail_scroll.grid(row=1, column=1, sticky="ns")
        self.benchmark_detail_text.configure(yscrollcommand=detail_scroll.set)
        benchmark_detail_buttons = ttk.Frame(summary_frame)
        benchmark_detail_buttons.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        benchmark_detail_buttons.columnconfigure(0, weight=1)
        benchmark_detail_buttons.columnconfigure(1, weight=1)
        ttk.Button(benchmark_detail_buttons, text="Copy response", command=self.copy_benchmark_response).grid(row=0, column=0, sticky="ew", padx=(0, 4))
        ttk.Button(
            benchmark_detail_buttons,
            text="Save CNF",
            command=self.save_selected_benchmark_cnf,
            style="Export.TButton",
        ).grid(row=0, column=1, sticky="ew", padx=(4, 0))

        self.benchmark_detail_notebook = ttk.Notebook(self.benchmark_detail_pane)
        self.benchmark_detail_pane.add(summary_frame, weight=1)
        self.benchmark_detail_pane.add(self.benchmark_detail_notebook, weight=2)

        edge_frame = ttk.Frame(self.benchmark_detail_notebook, padding=6)
        edge_frame.rowconfigure(1, weight=1)
        edge_frame.columnconfigure(0, weight=1)
        self.benchmark_detail_notebook.add(edge_frame, text="Input")
        self.benchmark_input_label = tk.StringVar(value="Problem data")
        ttk.Label(edge_frame, textvariable=self.benchmark_input_label).grid(row=0, column=0, sticky="w")
        self.benchmark_edge_text = tk.Text(edge_frame, height=14, width=34, wrap=tk.WORD)
        self.benchmark_edge_text.grid(row=1, column=0, sticky="nsew")
        edge_scroll = ttk.Scrollbar(edge_frame, orient=tk.VERTICAL, command=self.benchmark_edge_text.yview)
        edge_scroll.grid(row=1, column=1, sticky="ns")
        self.benchmark_edge_text.configure(yscrollcommand=edge_scroll.set)
        ttk.Button(edge_frame, text="Copy data", command=self.copy_benchmark_edges).grid(row=2, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        preview_frame = ttk.Frame(self.benchmark_detail_notebook, padding=6)
        preview_frame.rowconfigure(2, weight=1)
        preview_frame.columnconfigure(0, weight=1)
        self.benchmark_detail_notebook.add(preview_frame, text="Graph")
        self.graph_preview_status = tk.StringVar(value="Select a graph benchmark row to preview it.")
        ttk.Label(preview_frame, textvariable=self.graph_preview_status, wraplength=300).grid(row=0, column=0, sticky="ew")
        graph_buttons = ttk.Frame(preview_frame)
        graph_buttons.grid(row=1, column=0, sticky="ew", pady=(4, 6))
        graph_buttons.columnconfigure(0, weight=1)
        graph_buttons.columnconfigure(1, weight=1)
        self.render_graph_button = ttk.Button(
            graph_buttons,
            text="@ Refresh graph",
            command=lambda: self.render_selected_benchmark_graph(force=True),
            state=tk.DISABLED,
        )
        self.render_graph_button.grid(row=0, column=0, sticky="ew", padx=(0, 4))
        self.open_benchmark_graph_button = ttk.Button(
            graph_buttons,
            text="Open Graph",
            command=self.open_benchmark_graph_window,
            state=tk.DISABLED,
        )
        self.open_benchmark_graph_button.grid(row=0, column=1, sticky="ew", padx=(4, 0))
        self.graph_preview_frame = ttk.Frame(preview_frame)
        self.graph_preview_frame.grid(row=2, column=0, sticky="nsew")
        self.graph_preview_frame.rowconfigure(0, weight=1)
        self.graph_preview_frame.columnconfigure(0, weight=1)

        self._write_text_widget(self.benchmark_detail_text, "Select a benchmark row to see its stats and response.")
        self._write_text_widget(self.benchmark_edge_text, "Select a benchmark row to see problem-specific input data.")

    def _refresh_benchmark_form(self) -> None:
        for child in self.benchmark_input_frame.winfo_children():
            child.destroy()

        problem = self.bench_problem.get()
        self.benchmark_description.set(PROBLEM_DESCRIPTIONS.get(problem, ""))

        if problem == "Sudoku":
            self.benchmark_controls.configure(text="Sudoku Benchmark")
            self._build_sudoku_benchmark_form()
        elif problem == "N-Queens":
            self.benchmark_controls.configure(text="N-Queens Benchmark")
            self._build_n_queens_benchmark_form()
        elif problem == "Random 3-SAT":
            self.benchmark_controls.configure(text="Random 3-SAT Benchmark")
            self._build_random_3sat_benchmark_form()
        elif problem == "Graph Suite":
            self.benchmark_controls.configure(text="Graph Suite Benchmark")
            self._build_graph_suite_benchmark_form()
        else:
            self.benchmark_controls.configure(text=f"{problem} Benchmark")
            self._build_graph_benchmark_form()

    def _refresh_benchmark_log_controls(self) -> None:
        if self.bench_advanced_solver_logs.get():
            self.bench_log_box.configure(state="readonly")
        else:
            self.bench_log_box.configure(state=tk.DISABLED)

    def _build_graph_benchmark_form(self) -> None:
        self.bench_graph_field_entries = {}
        self.bench_graph_mode_buttons = {}

        ttk.Label(self.benchmark_input_frame, text="Generation").grid(row=0, column=0, sticky="w", pady=2)
        mode_row = ttk.Frame(self.benchmark_input_frame)
        mode_row.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=2)
        for label, value in [
            ("G(n,p)", "Probability"),
            ("G(n,m)", "Exact edges"),
            ("G(n,d)", "Average degree"),
        ]:
            button = ttk.Radiobutton(
                mode_row,
                text=label,
                variable=self.bench_generation_mode,
                value=value,
                command=self._refresh_benchmark_graph_controls,
            )
            button.pack(side=tk.LEFT, padx=(0, 10))
            self.bench_graph_mode_buttons[value] = button

        fields = [
            ("nodes", "Nodes", self.bench_nodes),
        ]
        if self.bench_problem.get() == "Graph Coloring":
            fields.append(("colors", "Colors", self.bench_colors))
        if self.bench_problem.get() in ("Independent Set", "Clique"):
            fields.append(("targets", "Target k values", self.bench_targets))
        fields.extend([
            ("probabilities", "Probabilities", self.bench_probs),
            ("edge_counts", "Edge counts", self.bench_edges),
            ("average_degrees", "Average degrees", self.bench_average_degrees),
            ("seed", "Seed", self.bench_seed),
        ])

        for row, (key, label, variable) in enumerate(fields, start=1):
            ttk.Label(self.benchmark_input_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(self.benchmark_input_frame, textvariable=variable, width=18)
            entry.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=2)
            self.bench_graph_field_entries[key] = entry

        self._refresh_benchmark_graph_controls()

    def _build_graph_suite_benchmark_form(self) -> None:
        self.bench_graph_field_entries = {}
        self.bench_graph_mode_buttons = {}

        ttk.Label(self.benchmark_input_frame, text="Problems").grid(row=0, column=0, sticky="nw", pady=2)
        problem_frame = ttk.Frame(self.benchmark_input_frame)
        problem_frame.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=2)
        suite_options = [
            ("Clique", self.bench_suite_clique),
            ("Independent Set", self.bench_suite_independent),
            ("Graph Coloring", self.bench_suite_graph_coloring),
            ("Hamiltonian Path", self.bench_suite_hamiltonian),
        ]
        for index, (label, variable) in enumerate(suite_options):
            ttk.Checkbutton(
                problem_frame,
                text=label,
                variable=variable,
                command=self._refresh_benchmark_graph_controls,
            ).grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 10), pady=2)

        ttk.Label(self.benchmark_input_frame, text="Generation").grid(row=1, column=0, sticky="w", pady=2)
        mode_row = ttk.Frame(self.benchmark_input_frame)
        mode_row.grid(row=1, column=1, sticky="w", padx=(8, 0), pady=2)
        for label, value in [
            ("G(n,p)", "Probability"),
            ("G(n,m)", "Exact edges"),
            ("G(n,d)", "Average degree"),
        ]:
            button = ttk.Radiobutton(
                mode_row,
                text=label,
                variable=self.bench_generation_mode,
                value=value,
                command=self._refresh_benchmark_graph_controls,
            )
            button.pack(side=tk.LEFT, padx=(0, 10))
            self.bench_graph_mode_buttons[value] = button

        fields = [
            ("nodes", "Nodes", self.bench_nodes),
            ("colors", "Colors", self.bench_colors),
            ("targets", "Target k values", self.bench_targets),
            ("probabilities", "Probabilities", self.bench_probs),
            ("edge_counts", "Edge counts", self.bench_edges),
            ("average_degrees", "Average degrees", self.bench_average_degrees),
            ("seed", "Seed", self.bench_seed),
        ]

        for row, (key, label, variable) in enumerate(fields, start=2):
            ttk.Label(self.benchmark_input_frame, text=label).grid(row=row, column=0, sticky="w", pady=2)
            entry = ttk.Entry(self.benchmark_input_frame, textvariable=variable, width=18)
            entry.grid(row=row, column=1, sticky="ew", padx=(8, 0), pady=2)
            self.bench_graph_field_entries[key] = entry

        self._refresh_benchmark_graph_controls()

    def _refresh_benchmark_graph_controls(self) -> None:
        if not hasattr(self, "bench_graph_field_entries"):
            return

        mode = self.bench_generation_mode.get()
        is_suite = self.bench_problem.get() == "Graph Suite"
        active_by_key = {
            "nodes": True,
            "colors": (not is_suite) or self.bench_suite_graph_coloring.get(),
            "targets": (not is_suite) or self.bench_suite_independent.get() or self.bench_suite_clique.get(),
            "probabilities": mode == "Probability",
            "edge_counts": mode == "Exact edges",
            "average_degrees": mode == "Average degree",
            "seed": True,
        }

        for key, entry in self.bench_graph_field_entries.items():
            entry.configure(state=tk.NORMAL if active_by_key.get(key, False) else tk.DISABLED)

    def _build_n_queens_benchmark_form(self) -> None:
        ttk.Label(self.benchmark_input_frame, text="Sizes").grid(row=0, column=0, sticky="w", pady=2)
        ttk.Entry(self.benchmark_input_frame, textvariable=self.bench_n_queens_sizes, width=18).grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=2)

    def _build_random_3sat_benchmark_form(self) -> None:
        ttk.Label(self.benchmark_input_frame, text="Preset").grid(row=0, column=0, sticky="w", pady=2)
        preset_frame = ttk.Frame(self.benchmark_input_frame)
        preset_frame.grid(row=0, column=1, sticky="ew", padx=(8, 0), pady=2)
        preset_frame.columnconfigure(0, weight=1)
        preset_combo = ttk.Combobox(
            preset_frame,
            textvariable=self.bench_3sat_preset,
            values=random_3sat_preset_names(),
            state="readonly",
            width=18,
        )
        preset_combo.grid(row=0, column=0, sticky="ew")
        preset_combo.bind("<<ComboboxSelected>>", lambda _event: self._apply_random_3sat_preset())
        ttk.Button(
            preset_frame,
            text="Apply",
            command=self._apply_random_3sat_preset,
            width=7,
        ).grid(row=0, column=1, sticky="e", padx=(6, 0))
        ttk.Label(
            self.benchmark_input_frame,
            textvariable=self.bench_3sat_preset_summary,
            wraplength=240,
            justify="left",
        ).grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 6))

        ttk.Label(self.benchmark_input_frame, text="Variables").grid(row=2, column=0, sticky="w", pady=2)
        self.bench_3sat_variables_entry = ttk.Entry(
            self.benchmark_input_frame,
            textvariable=self.bench_3sat_variables,
            width=18,
        )
        self.bench_3sat_variables_entry.grid(row=2, column=1, sticky="ew", padx=(8, 0), pady=2)
        ttk.Label(self.benchmark_input_frame, text="Clause/var ratios").grid(row=3, column=0, sticky="w", pady=2)
        self.bench_3sat_ratios_entry = ttk.Entry(
            self.benchmark_input_frame,
            textvariable=self.bench_3sat_ratios,
            width=18,
        )
        self.bench_3sat_ratios_entry.grid(row=3, column=1, sticky="ew", padx=(8, 0), pady=2)
        ttk.Label(self.benchmark_input_frame, text="Seed").grid(row=4, column=0, sticky="w", pady=2)
        self.bench_3sat_seed_entry = ttk.Entry(
            self.benchmark_input_frame,
            textvariable=self.bench_seed,
            width=18,
        )
        self.bench_3sat_seed_entry.grid(row=4, column=1, sticky="ew", padx=(8, 0), pady=2)
        ttk.Label(self.benchmark_input_frame, text="Formula mode").grid(row=5, column=0, sticky="w", pady=2)
        mode_combo = ttk.Combobox(
            self.benchmark_input_frame,
            textvariable=self.bench_3sat_mode,
            values=RANDOM_3SAT_MODES,
            state="readonly",
            width=18,
        )
        self.bench_3sat_mode_combo = mode_combo
        mode_combo.grid(row=5, column=1, sticky="ew", padx=(8, 0), pady=2)
        mode_combo.bind("<<ComboboxSelected>>", lambda _event: self._refresh_benchmark_random_3sat_controls())
        ttk.Label(self.benchmark_input_frame, text="SAT target % (blank=random)").grid(row=6, column=0, sticky="w", pady=2)
        self.bench_3sat_sat_percentage_entry = ttk.Entry(
            self.benchmark_input_frame,
            textvariable=self.bench_3sat_sat_percentage,
            width=18,
        )
        self.bench_3sat_sat_percentage_entry.grid(row=6, column=1, sticky="ew", padx=(8, 0), pady=2)
        self._refresh_benchmark_random_3sat_controls()

    def _refresh_benchmark_random_3sat_controls(self) -> None:
        if not hasattr(self, "bench_3sat_sat_percentage_entry"):
            return
        preset_active = self.bench_3sat_preset.get() != RANDOM_3SAT_PRESET_CUSTOM
        field_state = tk.DISABLED if preset_active else tk.NORMAL
        readonly_state = tk.DISABLED if preset_active else "readonly"
        for widget_name in (
            "bench_3sat_variables_entry",
            "bench_3sat_ratios_entry",
            "bench_3sat_seed_entry",
        ):
            widget = getattr(self, widget_name, None)
            if widget is not None:
                widget.configure(state=field_state)
        if hasattr(self, "bench_3sat_mode_combo"):
            self.bench_3sat_mode_combo.configure(state=readonly_state)
        sat_state = tk.NORMAL if self.bench_3sat_mode.get() == "Random" and not preset_active else tk.DISABLED
        self.bench_3sat_sat_percentage_entry.configure(state=sat_state)

    def _apply_random_3sat_preset(self) -> None:
        preset = self.bench_3sat_preset.get()
        ui_values = random_3sat_preset_ui_values(preset)
        if ui_values is not None:
            self.bench_3sat_variables.set(ui_values.variables)
            self.bench_3sat_ratios.set(ui_values.ratios)
            self.bench_seed.set(ui_values.seed)
            self.bench_3sat_mode.set(ui_values.formula_mode)
            self.bench_3sat_sat_percentage.set(ui_values.sat_percentage)

        default_solvers = random_3sat_preset_default_solvers(preset)
        if default_solvers:
            self.bench_cdcl.set("CDCL" in default_solvers)
            self.bench_dpll.set("DPLL" in default_solvers)
            self.bench_walksat.set("WalkSAT" in default_solvers)
            self.bench_probsat.set("ProbSAT" in default_solvers)

        self.bench_3sat_preset_summary.set(random_3sat_preset_summary(preset))
        self._refresh_benchmark_random_3sat_controls()

    def _build_sudoku_benchmark_form(self) -> None:
        ttk.Label(self.benchmark_input_frame, text="Sizes").grid(row=0, column=0, sticky="nw", pady=2)
        sizes_frame = ttk.Frame(self.benchmark_input_frame)
        sizes_frame.grid(row=0, column=1, sticky="w", padx=(8, 0), pady=2)

        for index, size in enumerate(SUDOKU_BENCHMARK_SIZES):
            ttk.Checkbutton(
                sizes_frame,
                text=f"{size}x{size}",
                variable=self.bench_sudoku_size_vars[size],
            ).grid(row=index // 2, column=index % 2, sticky="w", padx=(0, 10), pady=2)

    def _selected_sudoku_benchmark_sizes(self) -> list[int]:
        return [
            size
            for size in SUDOKU_BENCHMARK_SIZES
            if self.bench_sudoku_size_vars[size].get()
        ]

    def _selected_graph_suite_problems(self) -> list[str]:
        selected = []
        if self.bench_suite_clique.get():
            selected.append("Clique")
        if self.bench_suite_independent.get():
            selected.append("Independent Set")
        if self.bench_suite_graph_coloring.get():
            selected.append("Graph Coloring")
        if self.bench_suite_hamiltonian.get():
            selected.append("Hamiltonian Path")
        return selected

    def _graph_benchmark_inputs_from_form(self) -> tuple[str, list[float], list[int], list[float], list]:
        if self.bench_generation_mode.get() == "Exact edges":
            edge_counts = parse_int_list(self.bench_edges.get())
            return "exact_edges", [], edge_counts, [], edge_counts
        if self.bench_generation_mode.get() == "Average degree":
            average_degrees = parse_float_list(self.bench_average_degrees.get())
            return "average_degree", [], [], average_degrees, average_degrees
        probabilities = parse_float_list(self.bench_probs.get())
        return "probability", probabilities, [], [], probabilities

    def _graph_suite_problem_value_count(self, suite_problems: list[str], target_sizes: list[int], color_counts: list[int]) -> int:
        total = 0
        if "Clique" in suite_problems:
            total += len(target_sizes)
        if "Independent Set" in suite_problems:
            total += len(target_sizes)
        if "Graph Coloring" in suite_problems:
            total += len(color_counts)
        if "Hamiltonian Path" in suite_problems:
            total += 1
        return total

    def run_benchmark(self) -> None:
        try:
            solvers = []
            if self.bench_cdcl.get():
                solvers.append("CDCL")
            if self.bench_dpll.get():
                solvers.append("DPLL")
            if self.bench_walksat.get():
                solvers.append("WalkSAT")
            if self.bench_probsat.get():
                solvers.append("ProbSAT")
            if not solvers:
                raise ValueError("Select at least one solver")

            repeats = int(self.bench_repeats.get())
            logging_options = self._benchmark_logging_options_from_form()
            timeout_seconds = parse_timeout_seconds(self.bench_timeout_seconds.get())

            if self.bench_problem.get() == "Sudoku":
                sizes = self._selected_sudoku_benchmark_sizes()
                if not sizes:
                    raise ValueError("Select at least one Sudoku size")

                total_runs = len(sizes) * repeats * len(solvers)
                params = {
                    "problem_type": "Sudoku",
                    "sizes": sizes,
                    "solvers": solvers,
                    "repeats": repeats,
                    "logging_options": logging_options,
                    "timeout_seconds": timeout_seconds,
                }
            elif self.bench_problem.get() == "N-Queens":
                sizes = parse_int_list(self.bench_n_queens_sizes.get())
                total_runs = len(sizes) * repeats * len(solvers)
                params = {
                    "problem_type": "N-Queens",
                    "sizes": sizes,
                    "solvers": solvers,
                    "repeats": repeats,
                    "logging_options": logging_options,
                    "timeout_seconds": timeout_seconds,
                }
            elif self.bench_problem.get() == "Random 3-SAT":
                preset_name = self.bench_3sat_preset.get()
                if preset_name != RANDOM_3SAT_PRESET_CUSTOM:
                    total_runs = random_3sat_preset_case_count(preset_name) * len(solvers)
                    params = {
                        "problem_type": "Random 3-SAT",
                        "preset_name": preset_name,
                        "solvers": solvers,
                        "repeats": 1,
                        "logging_options": logging_options,
                        "timeout_seconds": timeout_seconds,
                    }
                else:
                    seed_text = self.bench_seed.get().strip()
                    variable_counts = parse_int_list(self.bench_3sat_variables.get())
                    clause_ratios = parse_float_list(self.bench_3sat_ratios.get())
                    formula_mode = self.bench_3sat_mode.get()
                    total_runs = len(variable_counts) * len(clause_ratios) * repeats * len(solvers)
                    params = {
                        "problem_type": "Random 3-SAT",
                        "preset_name": RANDOM_3SAT_PRESET_CUSTOM,
                        "variable_counts": variable_counts,
                        "clause_ratios": clause_ratios,
                        "solvers": solvers,
                        "repeats": repeats,
                        "seed": int(seed_text) if seed_text else None,
                        "formula_mode": formula_mode,
                        "sat_percentage": self._random_3sat_sat_percentage_from_text(self.bench_3sat_sat_percentage.get()) if formula_mode == "Random" else None,
                        "logging_options": logging_options,
                        "timeout_seconds": timeout_seconds,
                    }
            elif self.bench_problem.get() == "Graph Suite":
                seed_text = self.bench_seed.get().strip()
                node_counts = parse_int_list(self.bench_nodes.get())
                seed = int(seed_text) if seed_text else None
                generation_mode, probabilities, edge_counts, average_degrees, sweep_values = self._graph_benchmark_inputs_from_form()
                suite_problems = self._selected_graph_suite_problems()
                if not suite_problems:
                    raise ValueError("Select at least one Graph Suite problem")
                color_counts = parse_int_list(self.bench_colors.get()) if self.bench_suite_graph_coloring.get() else []
                needs_targets = self.bench_suite_independent.get() or self.bench_suite_clique.get()
                target_sizes = parse_int_list(self.bench_targets.get()) if needs_targets else []
                if needs_targets and not target_sizes:
                    raise ValueError("Graph Suite target problems need at least one target k value")
                if self.bench_suite_graph_coloring.get() and not color_counts:
                    raise ValueError("Graph Suite graph coloring needs at least one color count")
                suite_count = self._graph_suite_problem_value_count(suite_problems, target_sizes, color_counts)
                if suite_count <= 0:
                    raise ValueError("Graph Suite needs target k values, color counts, or Hamiltonian Path selected")
                total_runs = len(node_counts) * len(sweep_values) * suite_count * repeats * len(solvers)
                params = {
                    "problem_type": "Graph Suite",
                    "node_counts": node_counts,
                    "probabilities": probabilities,
                    "edge_counts": edge_counts,
                    "average_degrees": average_degrees,
                    "suite_problems": suite_problems,
                    "color_counts": color_counts,
                    "target_sizes": target_sizes,
                    "solvers": solvers,
                    "repeats": repeats,
                    "seed": seed,
                    "generation_mode": generation_mode,
                    "logging_options": logging_options,
                    "timeout_seconds": timeout_seconds,
                }
            else:
                seed_text = self.bench_seed.get().strip()
                node_counts = parse_int_list(self.bench_nodes.get())
                seed = int(seed_text) if seed_text else None
                generation_mode, probabilities, edge_counts, average_degrees, sweep_values = self._graph_benchmark_inputs_from_form()
                if self.bench_problem.get() == "Graph Coloring":
                    color_counts = parse_int_list(self.bench_colors.get())
                    target_sizes = []
                    specific_count = len(color_counts)
                elif self.bench_problem.get() in ("Independent Set", "Clique"):
                    color_counts = []
                    target_sizes = parse_int_list(self.bench_targets.get())
                    specific_count = len(target_sizes)
                else:
                    color_counts = []
                    target_sizes = []
                    specific_count = 1
                total_runs = len(node_counts) * len(sweep_values) * specific_count * repeats * len(solvers)
                params = {
                    "problem_type": self.bench_problem.get(),
                    "node_counts": node_counts,
                    "probabilities": probabilities,
                    "edge_counts": edge_counts,
                    "average_degrees": average_degrees,
                    "color_counts": color_counts,
                    "target_sizes": target_sizes,
                    "solvers": solvers,
                    "repeats": repeats,
                    "seed": seed,
                    "generation_mode": generation_mode,
                    "logging_options": logging_options,
                    "timeout_seconds": timeout_seconds,
                }

            skip_event = mp.Event()
            job = self._start_process_worker(
                f"Benchmarking {total_runs} solver runs",
                benchmark_process,
                params,
                extra_events=(skip_event,),
                benchmark_skip_event=skip_event,
                kind="benchmark",
            )
            job.pending_chart_refresh = True
        except Exception as exc:
            messagebox.showerror("Benchmark failed", str(exc))

    def _visible_benchmark_rows(self) -> list[BenchmarkRow]:
        labels = self._benchmark_filter_labels()
        if labels is None:
            return list(self.benchmark_rows)
        return [
            row
            for row in self.benchmark_rows
            if row.run_label in labels
        ]

    def _benchmark_filter_labels(self) -> set[str] | None:
        label_filter = self.benchmark_filter_run_label
        if label_filter is None:
            return None
        if isinstance(label_filter, str):
            return {label_filter}
        return set(label_filter)

    def _benchmark_filter_label_text(self) -> str:
        label_filter = self.benchmark_filter_run_label
        if label_filter is None:
            return "all benchmark rows"
        if label_filter == ():
            return "no selected runs"
        if isinstance(label_filter, str):
            return label_filter
        return ", ".join(label_filter)

    def _benchmark_row_is_visible(self, row: BenchmarkRow) -> bool:
        labels = self._benchmark_filter_labels()
        return labels is None or row.run_label in labels

    def _remove_benchmark_filter_labels(self, removed_labels: set[str]) -> None:
        labels = self._benchmark_filter_labels()
        if labels is None:
            return
        remaining = tuple(label for label in self._benchmark_filter_label_order() if label not in removed_labels)
        if not remaining:
            self.benchmark_filter_run_label = None
        elif len(remaining) == 1:
            self.benchmark_filter_run_label = remaining[0]
        else:
            self.benchmark_filter_run_label = remaining

    def _benchmark_filter_label_order(self) -> tuple[str, ...]:
        label_filter = self.benchmark_filter_run_label
        if label_filter is None:
            return ()
        if isinstance(label_filter, str):
            return (label_filter,)
        return label_filter

    def _set_benchmark_status(self, message: str) -> None:
        if hasattr(self, "benchmark_status"):
            self.benchmark_status.set(message)

    def _clear_benchmark_chart(self, message: str | None = None) -> None:
        if self.benchmark_canvas is not None:
            self.benchmark_canvas.get_tk_widget().destroy()
            self.benchmark_canvas = None
            self.benchmark_figure = None
        if self.benchmark_chart_message is not None:
            self.benchmark_chart_message.destroy()
            self.benchmark_chart_message = None
        if message:
            self.benchmark_chart_message = ttk.Label(
                self.chart_frame,
                text=message,
                justify="center",
                wraplength=460,
            )
            self.benchmark_chart_message.grid(row=0, column=0, sticky="nsew")

    def _schedule_benchmark_chart_refresh(self, *, allow_large_auto: bool = False) -> bool:
        if self.pending_benchmark_chart_after_id is not None:
            try:
                self.root.after_cancel(self.pending_benchmark_chart_after_id)
            except tk.TclError:
                pass
            self.pending_benchmark_chart_after_id = None
        visible_count = len(self._visible_benchmark_rows())
        if not allow_large_auto and visible_count > BENCHMARK_AUTO_CHART_MAX_ROWS:
            self._clear_benchmark_chart(
                f"Chart skipped for {visible_count} rows. Use Refresh Chart when you want to render it."
            )
            self._set_benchmark_status(
                f"Showing {self._benchmark_filter_label_text()} ({visible_count} rows); chart refresh skipped."
            )
            return False
        self._set_benchmark_status("Drawing chart...")
        self.pending_benchmark_chart_after_id = self.root.after(50, self._run_deferred_benchmark_chart_refresh)
        return True

    def _run_deferred_benchmark_chart_refresh(self) -> None:
        self.pending_benchmark_chart_after_id = None
        self.draw_benchmark_chart()
        visible_count = len(self._visible_benchmark_rows())
        if self.benchmark_filter_run_label is None:
            self._set_benchmark_status(f"Showing all benchmark rows ({visible_count}).")
        else:
            self._set_benchmark_status(f"Showing {self._benchmark_filter_label_text()} ({visible_count} rows).")

    def show_selected_benchmark_run(self) -> None:
        jobs = self._selected_benchmark_jobs()
        if not jobs:
            return
        labels = tuple(job.label for job in jobs)
        self.benchmark_filter_run_label = labels[0] if len(labels) == 1 else labels
        self._set_benchmark_status(f"Showing {self._benchmark_filter_label_text()}...")
        self._fill_benchmark_table()
        self._schedule_benchmark_chart_refresh()
        self._refresh_job_buttons()

    def show_all_benchmark_runs(self) -> None:
        self._set_benchmark_status("Showing all runs...")
        self.benchmark_filter_run_label = None
        self._fill_benchmark_table()
        self._schedule_benchmark_chart_refresh()
        self._refresh_job_buttons()

    def clear_selected_benchmark_run_results(self) -> None:
        jobs = self._selected_benchmark_jobs()
        if not jobs:
            return
        run_labels = {job.label for job in jobs}
        self.benchmark_rows = [
            row
            for row in self.benchmark_rows
            if row.run_label not in run_labels
        ]
        for job in jobs:
            job.rows = []
        self._remove_benchmark_filter_labels(run_labels)
        self._set_benchmark_status(f"Cleared {', '.join(job.label for job in jobs)} results.")
        self._fill_benchmark_table()
        self._schedule_benchmark_chart_refresh()
        self._refresh_job_buttons()

    def clear_all_benchmark_results(self) -> None:
        table = getattr(self, "benchmark_jobs_table", None)
        if table is not None:
            table.selection_remove(table.selection())
        if self.selected_job_id == self.selected_benchmark_job_id:
            self.selected_job_id = None
        self.selected_benchmark_job_id = None
        self.benchmark_rows = []
        for job in self.jobs.values():
            if job.kind == "benchmark":
                job.rows = []
        self.benchmark_filter_run_label = None
        self._set_benchmark_status("Cleared all benchmark results.")
        self._fill_benchmark_table()
        self._schedule_benchmark_chart_refresh()
        self._refresh_job_buttons()

    def clear_benchmark_table(self) -> None:
        self.benchmark_rows = []
        for job in self.jobs.values():
            if job.kind == "benchmark":
                job.rows = []
        self.benchmark_filter_run_label = None
        self._set_benchmark_status("Benchmark table cleared.")
        self._fill_benchmark_table()
        self.draw_benchmark_chart()
        self._refresh_job_buttons()

    def _fill_benchmark_table(self) -> None:
        self._set_benchmark_status("Refreshing table...")
        self.benchmark_row_by_item = {}
        for item in self.benchmark_table.get_children():
            self.benchmark_table.delete(item)

        for row in self._visible_benchmark_rows():
            self._insert_benchmark_row(row)
        visible_count = len(self._visible_benchmark_rows())
        if self.benchmark_filter_run_label is None:
            self._set_benchmark_status(f"Showing all benchmark rows ({visible_count}).")
        else:
            self._set_benchmark_status(f"Showing {self._benchmark_filter_label_text()} ({visible_count} rows).")
        self.selected_benchmark_row = None
        if hasattr(self, "benchmark_detail_text"):
            self._write_text_widget(self.benchmark_detail_text, "Select a benchmark row to see its stats and response.")
            self._write_text_widget(self.benchmark_edge_text, "Select a benchmark row to see problem-specific input data.")
            self._clear_benchmark_graph_preview("Select a graph benchmark row to preview it.")
            self.render_graph_button.configure(state=tk.DISABLED)
            self.open_benchmark_graph_button.configure(state=tk.DISABLED)

    def _insert_benchmark_row(self, row: BenchmarkRow) -> None:
        item = self.benchmark_table.insert(
            "",
            tk.END,
            values=(
                row.run_label,
                row.case_name,
                row.problem_type,
                row.detail,
                row.solver,
                row.solver_options,
                row.status,
                f"{row.elapsed:.6f}s",
                row.conflicts,
                row.decisions,
            ),
        )
        self.benchmark_row_by_item[item] = row

    def _on_benchmark_row_selected(self, _event=None) -> None:
        selected = self.benchmark_table.selection()
        if not selected:
            return

        row = self.benchmark_row_by_item.get(selected[0])
        if row is None:
            return

        self.selected_benchmark_row = row
        self._show_benchmark_row_details(row)

    def _show_benchmark_row_details(self, row: BenchmarkRow) -> None:
        self._write_text_widget(self.benchmark_detail_text, self._format_benchmark_row_details(row))
        self.benchmark_input_label.set(self._benchmark_problem_data_label(row))
        self._write_text_widget(self.benchmark_edge_text, self._format_benchmark_problem_data(row))

        if not self._is_graph_benchmark_row(row):
            self._clear_benchmark_graph_preview(f"{row.problem_type} rows show their data in the Input tab.")
            self.render_graph_button.configure(state=tk.DISABLED)
            self.open_benchmark_graph_button.configure(state=tk.DISABLED)
            return

        if not row.graph_edges and row.node_count == "-":
            self._clear_benchmark_graph_preview("No graph data stored for this benchmark row.")
            self.render_graph_button.configure(state=tk.DISABLED)
            self.open_benchmark_graph_button.configure(state=tk.DISABLED)
            return

        policy = self._graph_preview_policy(row.node_count, len(row.graph_edges))
        if policy == "auto":
            self.render_graph_button.configure(state=tk.NORMAL)
            self.open_benchmark_graph_button.configure(state=tk.NORMAL)
            self.render_selected_benchmark_graph(force=False)
        elif policy == "manual":
            self.render_graph_button.configure(state=tk.NORMAL)
            self.open_benchmark_graph_button.configure(state=tk.NORMAL)
            self._clear_benchmark_graph_preview("Graph is moderately large; use Refresh graph when needed.")
        else:
            self.render_graph_button.configure(state=tk.DISABLED)
            self.open_benchmark_graph_button.configure(state=tk.DISABLED)
            self._clear_benchmark_graph_preview("Graph too large to preview safely.")

    def _format_benchmark_row_details(self, row: BenchmarkRow) -> str:
        lines = [
            f"Case: {row.case_name}",
            f"Repeat: {row.repeat}",
            f"Solver: {row.solver}",
            f"Status: {row.status}",
            f"Time: {row.elapsed:.6f}s",
            f"Clauses: {row.clauses}",
            f"Variables: {row.variables}",
            f"Conflicts: {row.conflicts}",
            f"Decisions: {row.decisions}",
            f"Propagations: {row.propagations}",
            f"Learned clauses: {row.learned_clauses}",
        ]
        if row.run_label:
            lines.insert(0, f"Run: {row.run_label}")
        if row.solver_options:
            lines.append(f"Solver options: {row.solver_options}")

        lines.extend(self._benchmark_problem_summary_lines(row))

        if row.detail:
            lines.append(f"Detail: {row.detail}")
        if row.decoded is not None:
            lines.extend(["", "Decoded response:", self._format_decoded(row.decoded)])

        return "\n".join(lines)

    def _benchmark_problem_summary_lines(self, row: BenchmarkRow) -> list[str]:
        metadata = row.problem_metadata or {}
        if row.problem_type == "Sudoku":
            size = metadata.get("size", "?")
            return [
                f"Size: {size}x{size}",
                f"Box size: {metadata.get('box_size', '-')}",
                f"Givens: {metadata.get('givens', '-')}",
                f"Empty cells: {metadata.get('empty_cells', '-')}",
                f"Generation: {row.generation_mode or metadata.get('mode', '-')}",
            ]

        if row.problem_type == "N-Queens":
            return [
                f"Board: {metadata.get('size', '?')}x{metadata.get('size', '?')}",
                f"Queens: {metadata.get('queens', metadata.get('size', '-'))}",
                f"Board cells: {metadata.get('board_cells', '-')}",
            ]

        if row.problem_type == "Random 3-SAT":
            generation = row.generation_mode or metadata.get("mode", "-")
            if metadata.get("mode") == "Random" and metadata.get("sat_percentage") is not None:
                generation = (
                    f"{generation} ({metadata.get('sat_percentage'):g}% SAT, "
                    f"{metadata.get('unsat_percentage', 0):g}% UNSAT)"
                )
            return [
                f"Variables: {metadata.get('variables', row.variables)}",
                f"Clauses: {metadata.get('clauses_requested', row.clauses)}",
                f"Clause width: {metadata.get('width', 3)}",
                f"Ratio: {metadata.get('ratio', 0):.2f}",
                f"Generation: {generation}",
                f"Selected: {metadata.get('selected_mode', '-')}",
                f"Seed: {row.seed}",
            ]

        if self._is_graph_benchmark_row(row):
            nodes = self._safe_int(row.node_count)
            edges = len(row.graph_edges) if row.graph_edges else self._safe_int(row.edge_count)
            density = "-"
            if nodes and nodes > 1 and edges is not None:
                density = f"{(2 * edges / (nodes * (nodes - 1))):.4f}"
            lines = [
                f"Nodes: {row.node_count}",
                f"Edges: {edges if edges is not None else row.edge_count}",
                f"Density: {density}",
                f"Generation: {row.generation_mode or '-'}",
                f"Seed: {row.seed}",
            ]
            if metadata.get("suite"):
                lines.insert(0, f"Shared graph: {metadata.get('shared_graph_id', '-')}")
                lines.insert(1, f"Graph case: {metadata.get('suite_graph_label', '-')}")
            return lines

        return []

    def _benchmark_problem_data_label(self, row: BenchmarkRow) -> str:
        if row.problem_type == "Sudoku":
            return "Sudoku puzzle"
        if row.problem_type == "N-Queens":
            return "N-Queens board"
        if row.problem_type == "Random 3-SAT":
            return "3-SAT formula"
        if self._is_graph_benchmark_row(row):
            return "Graph edges"
        return "Problem data"

    def _format_benchmark_problem_data(self, row: BenchmarkRow) -> str:
        if row.problem_type == "Sudoku":
            return self._format_sudoku_benchmark_data(row)
        if row.problem_type == "N-Queens":
            return self._format_n_queens_benchmark_data(row)
        if row.problem_type == "Random 3-SAT":
            return self._format_random_3sat_data(row)
        if self._is_graph_benchmark_row(row):
            return self._format_benchmark_edges(row.graph_edges, row.node_count)
        return "No extra problem data stored for this row."

    def _format_sudoku_benchmark_data(self, row: BenchmarkRow) -> str:
        metadata = row.problem_metadata or {}
        lines = []
        grid = metadata.get("grid")
        if grid:
            lines.append("Initial puzzle:")
            lines.append(self._format_grid_with_dots(grid))
        else:
            lines.append("No initial Sudoku grid stored for this row.")

        if isinstance(row.decoded, list):
            lines.extend(["", "Solved grid:", self._format_decoded(row.decoded)])
        return "\n".join(lines)

    def _format_n_queens_benchmark_data(self, row: BenchmarkRow) -> str:
        metadata = row.problem_metadata or {}
        lines = [
            f"Board size: {metadata.get('size', '?')}x{metadata.get('size', '?')}",
            f"Queens to place: {metadata.get('queens', metadata.get('size', '-'))}",
        ]
        if isinstance(row.decoded, dict):
            lines.extend(["", self._format_decoded(row.decoded)])
        else:
            lines.append("")
            lines.append("No board response stored for this row.")
        return "\n".join(lines)

    def _format_random_3sat_data(self, row: BenchmarkRow) -> str:
        metadata = row.problem_metadata or {}
        sat_percentage = metadata.get("sat_percentage")
        sat_chance = "-" if sat_percentage is None else f"{sat_percentage:g}%"
        lines = [
            f"Variables: {metadata.get('variables', row.variables)}",
            f"Clauses: {metadata.get('clauses_requested', row.clauses)}",
            f"Ratio: {metadata.get('ratio', 0):.2f}",
            f"Mode: {metadata.get('mode', '-')}",
            f"SAT target: {sat_chance}",
            f"Selected: {metadata.get('selected_mode', '-')}",
            f"Seed: {row.seed}",
        ]
        if not row.problem_clauses:
            storage = metadata.get("cnf_storage")
            if storage:
                lines.extend(["", f"CNF clauses not stored for this benchmark row ({storage})."])
            return "\n".join(lines)

        lines.extend(["", "First clauses:"])
        shown = row.problem_clauses[:20]
        lines.extend(" ".join(str(lit) for lit in clause) for clause in shown)
        if len(row.problem_clauses) > len(shown):
            lines.append(f"... {len(row.problem_clauses) - len(shown)} more clauses")
        return "\n".join(lines)

    def _format_grid_with_dots(self, grid: list[list[int]]) -> str:
        return "\n".join(" ".join("." if value == 0 else str(value) for value in row) for row in grid)

    def _is_graph_benchmark_row(self, row: BenchmarkRow) -> bool:
        return row.problem_type in GRAPH_PROBLEM_KINDS

    def _format_benchmark_edges(self, edges: list[tuple[int, int]], node_count=None) -> str:
        if not edges:
            if self._safe_int(node_count) is not None:
                return "0 edges"
            return "No graph edges stored for this row."

        sorted_edges = sorted((int(u), int(v)) for u, v in edges)
        header = f"{len(sorted_edges)} edges"
        edge_text = ", ".join(f"{u}-{v}" for u, v in sorted_edges)
        return f"{header}\n\n{edge_text}"

    def _safe_int(self, value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _write_text_widget(self, widget, text: str) -> None:
        widget.configure(state=tk.NORMAL)
        widget.delete("1.0", tk.END)
        widget.insert("1.0", text)
        widget.configure(state=tk.DISABLED)

    def _graph_preview_policy(self, node_count, edge_count: int) -> str:
        nodes = self._safe_int(node_count)
        if nodes is None:
            return "skip"
        if nodes <= 80 and edge_count <= 250:
            return "auto"
        if nodes <= 200 and edge_count <= 800:
            return "manual"
        return "skip"

    def copy_benchmark_edges(self) -> None:
        if self.selected_benchmark_row is None:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._format_benchmark_problem_data(self.selected_benchmark_row))

    def copy_benchmark_response(self) -> None:
        if self.selected_benchmark_row is None or self.selected_benchmark_row.decoded is None:
            return
        self.root.clipboard_clear()
        self.root.clipboard_append(self._format_decoded(self.selected_benchmark_row.decoded))

    def _benchmark_row_dimacs(self, row: BenchmarkRow) -> str:
        if not row.problem_clauses:
            raise ValueError("This benchmark row does not have CNF clauses stored.")

        comments = [
            row.case_name,
            f"type={row.problem_type}",
            f"solver={row.solver}",
            f"status={row.status}",
            f"repeat={row.repeat}",
            f"variables={row.variables}",
        ]
        if row.solver_options:
            comments.append(f"solver_options={row.solver_options}")
        if row.detail:
            comments.append(row.detail)
        return clauses_to_dimacs(row.problem_clauses, comments)

    def save_selected_benchmark_cnf(self) -> None:
        row = self.selected_benchmark_row
        if row is None:
            messagebox.showinfo("No benchmark row", "Select a benchmark row first.")
            return
        if not row.problem_clauses:
            messagebox.showinfo("No CNF stored", "This benchmark row does not have CNF clauses stored.")
            return

        safe_name = row.case_name.replace(" ", "_").replace("/", "_")
        default_name = f"{safe_name}_r{row.repeat}_{row.solver}.cnf"
        path = filedialog.asksaveasfilename(
            initialdir=str(INPUT_GENERATED),
            initialfile=default_name,
            defaultextension=".cnf",
            filetypes=[("DIMACS CNF", "*.cnf"), ("All files", "*.*")],
        )

        if not path:
            return

        try:
            Path(path).parent.mkdir(parents=True, exist_ok=True)
            Path(path).write_text(self._benchmark_row_dimacs(row), encoding="utf-8")
            messagebox.showinfo("Saved", f"Saved benchmark CNF to {path}")
        except Exception as exc:
            messagebox.showerror("Cannot save CNF", str(exc))

    def _clear_benchmark_graph_preview(self, message: str) -> None:
        if self.benchmark_detail_canvas is not None:
            self.benchmark_detail_canvas.get_tk_widget().destroy()
            self.benchmark_detail_canvas = None
        for child in self.graph_preview_frame.winfo_children():
            child.destroy()
        self.graph_preview_status.set(message)

    def _clear_solve_graph_preview(self, message: str) -> None:
        if self.solve_detail_canvas is not None:
            self.solve_detail_canvas.get_tk_widget().destroy()
            self.solve_detail_canvas = None
        for child in self.solve_visual_frame.winfo_children():
            child.destroy()
        self.solve_visual_status.set(message)

    def _build_graph_figure(self, row: BenchmarkRow, figsize=(4.4, 2.6), show_labels: bool = True, node_size_override=None):
        nodes = self._safe_int(row.node_count)
        if nodes is None or nodes <= 0:
            raise ValueError("No graph node data is available.")

        figure = Figure(figsize=figsize, dpi=100)
        axis = figure.add_subplot(111)
        positions = self._circular_graph_positions(nodes)
        edges = sorted((int(u), int(v)) for u, v in row.graph_edges)

        for u, v in edges:
            if u in positions and v in positions:
                axis.plot(
                    [positions[u][0], positions[v][0]],
                    [positions[u][1], positions[v][1]],
                    color="#c9c9c9",
                    linewidth=0.7,
                    zorder=1,
                )

        path_edges = self._benchmark_path_edges(row)
        for u, v in path_edges:
            if u in positions and v in positions:
                axis.plot(
                    [positions[u][0], positions[v][0]],
                    [positions[u][1], positions[v][1]],
                    color="#222222",
                    linewidth=2.0,
                    zorder=2,
                )

        node_colors = [self._benchmark_node_color(row, node) for node in range(1, nodes + 1)]
        node_size = node_size_override if node_size_override is not None else (52 if nodes <= 80 else 20)
        axis.scatter(
            [positions[node][0] for node in range(1, nodes + 1)],
            [positions[node][1] for node in range(1, nodes + 1)],
            c=node_colors,
            s=node_size,
            edgecolors="#333333",
            linewidths=0.4,
            zorder=3,
        )

        if show_labels and nodes <= 80:
            labels = self._benchmark_node_labels(row, nodes)
            for node in range(1, nodes + 1):
                axis.text(
                    positions[node][0],
                    positions[node][1],
                    labels.get(node, str(node)),
                    ha="center",
                    va="center",
                    fontsize=6,
                    zorder=4,
                )

        axis.set_aspect("equal")
        axis.axis("off")
        figure.tight_layout()
        return figure, nodes, len(edges)

    def render_selected_benchmark_graph(self, force: bool = False) -> None:
        row = self.selected_benchmark_row
        if row is None:
            return

        if Figure is None or FigureCanvasTkAgg is None:
            self._clear_benchmark_graph_preview("Matplotlib Tk support is not available.")
            return

        nodes = self._safe_int(row.node_count)
        if nodes is None or nodes <= 0:
            self._clear_benchmark_graph_preview("No graph node data stored for this benchmark row.")
            return

        policy = self._graph_preview_policy(nodes, len(row.graph_edges))
        if policy == "skip" and not force:
            self._clear_benchmark_graph_preview("Graph too large to preview safely.")
            return

        self._clear_benchmark_graph_preview(f"Rendering {nodes} nodes and {len(row.graph_edges)} edges.")
        figure, nodes, edge_count = self._build_graph_figure(row, figsize=(3.6, 2.3))

        self.benchmark_detail_canvas = FigureCanvasTkAgg(figure, master=self.graph_preview_frame)
        self.benchmark_detail_canvas.draw()
        self.benchmark_detail_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.graph_preview_status.set(f"Preview: {nodes} nodes, {edge_count} edges.")

    def render_solve_graph(self, force: bool = False) -> None:
        row = self._solve_detail_row()
        if row is None:
            return

        if Figure is None or FigureCanvasTkAgg is None:
            self._clear_solve_graph_preview("Matplotlib Tk support is not available.")
            return

        nodes = self._safe_int(row.node_count)
        if nodes is None or nodes <= 0:
            self._clear_solve_graph_preview("No graph node data stored for this problem.")
            return

        policy = self._graph_preview_policy(nodes, len(row.graph_edges))
        if policy == "skip" and not force:
            self._clear_solve_graph_preview("Graph too large to preview safely.")
            return

        self._clear_solve_graph_preview(f"Rendering {nodes} nodes and {len(row.graph_edges)} edges.")
        figure, nodes, edge_count = self._build_graph_figure(row, figsize=(4.4, 2.6))

        self.solve_detail_canvas = FigureCanvasTkAgg(figure, master=self.solve_visual_frame)
        self.solve_detail_canvas.draw()
        self.solve_detail_canvas.get_tk_widget().grid(row=0, column=0, sticky="nsew")
        self.solve_visual_status.set(f"Preview: {nodes} nodes, {edge_count} edges.")

    def open_solve_graph_window(self) -> None:
        row = self._solve_detail_row()
        if row is None:
            messagebox.showinfo("No graph", "Generate or solve a graph problem first.")
            return
        self._open_graph_popout(row, "Solve Graph")

    def open_benchmark_graph_window(self) -> None:
        row = self.selected_benchmark_row
        if row is None:
            messagebox.showinfo("No graph", "Select a graph benchmark row first.")
            return
        self._open_graph_popout(row, "Benchmark Graph")

    def _open_graph_popout(self, row: BenchmarkRow, title: str) -> None:
        if not self._is_graph_benchmark_row(row):
            messagebox.showinfo("No graph", f"{row.problem_type} rows do not have a graph preview.")
            return
        if Figure is None or FigureCanvasTkAgg is None:
            messagebox.showwarning("Graph unavailable", "Matplotlib Tk support is not available.")
            return
        if self._safe_int(row.node_count) is None:
            messagebox.showinfo("No graph", "No graph data is stored for this row.")
            return

        window = tk.Toplevel(self.root)
        window.title(title)
        window.geometry("820x620")
        window.rowconfigure(1, weight=1)
        window.columnconfigure(0, weight=1)

        toolbar = self._build_top_toolbar(window)
        toolbar.grid(row=0, column=0, sticky="ew", padx=8, pady=(8, 0))
        canvas_frame = ttk.Frame(window, padding=8)
        canvas_frame.grid(row=1, column=0, sticky="nsew")
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)
        status = tk.StringVar(value="")
        ttk.Label(window, textvariable=status).grid(row=2, column=0, sticky="ew", padx=8, pady=(0, 8))
        show_labels = tk.BooleanVar(value=True)
        node_size_var = tk.StringVar(value="")

        state = {"canvas": None, "figure": None}

        def draw() -> None:
            if state["canvas"] is not None:
                state["canvas"].get_tk_widget().destroy()
            node_size = None
            raw_size = node_size_var.get().strip()
            if raw_size:
                try:
                    node_size = max(1, int(raw_size))
                except ValueError:
                    status.set("Node size must be a positive integer.")
                    return
            figure, nodes, edge_count = self._build_graph_figure(
                row,
                figsize=(7.2, 5.0),
                show_labels=show_labels.get(),
                node_size_override=node_size,
            )
            state["figure"] = figure
            state["canvas"] = FigureCanvasTkAgg(figure, master=canvas_frame)
            state["canvas"].draw()
            state["canvas"].get_tk_widget().grid(row=0, column=0, sticky="nsew")
            status.set(f"{row.case_name}: {nodes} nodes, {edge_count} edges")

        ttk.Button(toolbar, text="@ Refresh", command=draw).grid(row=0, column=0, sticky="w", padx=(0, 6))
        ttk.Checkbutton(toolbar, text="Labels", variable=show_labels, command=draw).grid(row=0, column=1, sticky="w", padx=(0, 6))
        ttk.Label(toolbar, text="Node size").grid(row=0, column=2, sticky="w")
        ttk.Entry(toolbar, textvariable=node_size_var, width=6).grid(row=0, column=3, sticky="w", padx=(4, 8))
        ttk.Button(
            toolbar,
            text="Export PNG",
            command=lambda: self._export_graph_png(state["figure"], row),
            style="Export.TButton",
        ).grid(row=0, column=4, sticky="w", padx=(0, 6))
        ttk.Button(
            toolbar,
            text="Copy Graph Data",
            command=lambda: self._copy_graph_data(row),
        ).grid(row=0, column=5, sticky="w", padx=(0, 6))
        ttk.Button(
            toolbar,
            text="Export Graph Data",
            command=lambda: self._export_graph_data(row),
            style="Export.TButton",
        ).grid(row=0, column=6, sticky="w")
        draw()

    def _format_graph_export_data(self, row: BenchmarkRow) -> str:
        lines = [
            row.case_name,
            f"type={row.problem_type}",
            f"solver={row.solver}",
            f"status={row.status}",
            f"nodes={row.node_count}",
            f"edges={len(row.graph_edges)}",
        ]
        if row.decoded is not None:
            lines.extend(["", "Decoded:", self._format_decoded(row.decoded)])
        lines.extend(["", "Edges:", self._format_benchmark_edges(row.graph_edges, row.node_count)])
        return "\n".join(lines)

    def _copy_graph_data(self, row: BenchmarkRow) -> None:
        self.root.clipboard_clear()
        self.root.clipboard_append(self._format_graph_export_data(row))

    def _export_graph_data(self, row: BenchmarkRow) -> None:
        safe_name = row.case_name.replace(" ", "_").replace("/", "_")
        path = filedialog.asksaveasfilename(
            initialdir=str(BENCHMARK_OUTPUT),
            initialfile=f"{safe_name}_graph.txt",
            defaultextension=".txt",
            filetypes=[("Text", "*.txt"), ("All files", "*.*")],
        )
        if path:
            Path(path).write_text(self._format_graph_export_data(row), encoding="utf-8")
            messagebox.showinfo("Exported", f"Saved graph data to {path}")

    def _export_graph_png(self, figure, row: BenchmarkRow) -> None:
        if figure is None:
            return
        safe_name = row.case_name.replace(" ", "_").replace("/", "_")
        path = filedialog.asksaveasfilename(
            initialdir=str(BENCHMARK_OUTPUT),
            initialfile=f"{safe_name}_graph.png",
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("All files", "*.*")],
        )
        if path:
            figure.savefig(path)
            messagebox.showinfo("Exported", f"Saved graph image to {path}")

    def _circular_graph_positions(self, node_count: int) -> dict[int, tuple[float, float]]:
        positions = {}
        for index, node in enumerate(range(1, node_count + 1)):
            angle = 2 * math.pi * index / node_count
            positions[node] = (math.cos(angle), math.sin(angle))
        return positions

    def _benchmark_node_color(self, row: BenchmarkRow, node: int) -> str:
        palette = ["#4c78a8", "#f58518", "#54a24b", "#e45756", "#b279a2", "#72b7b2", "#ff9da6", "#9d755d"]
        if row.problem_type == "Graph Coloring" and isinstance(row.decoded, dict):
            color = row.decoded.get(node)
            if color is not None:
                return palette[(int(color) - 1) % len(palette)]
        if row.problem_type in ("Independent Set", "Clique") and isinstance(row.decoded, dict):
            selected = set(row.decoded.get("selected", []))
            return "#59a14f" if node in selected else "#d8d8d8"
        if row.problem_type == "Hamiltonian Path" and isinstance(row.decoded, dict):
            path = row.decoded.get("path", [])
            return "#edc948" if node in path else "#d8d8d8"
        return "#4c78a8"

    def _benchmark_path_edges(self, row: BenchmarkRow) -> set[tuple[int, int]]:
        if row.problem_type != "Hamiltonian Path" or not isinstance(row.decoded, dict):
            return set()
        path = row.decoded.get("path", [])
        edges = set()
        for left, right in zip(path, path[1:]):
            u, v = sorted((int(left), int(right)))
            edges.add((u, v))
        return edges

    def _benchmark_node_labels(self, row: BenchmarkRow, node_count: int) -> dict[int, str]:
        if row.problem_type == "Hamiltonian Path" and isinstance(row.decoded, dict):
            path = row.decoded.get("path", [])
            return {int(node): str(index) for index, node in enumerate(path, start=1)}
        return {node: str(node) for node in range(1, node_count + 1)}

    def draw_benchmark_chart(self) -> None:
        rows = self._visible_benchmark_rows()
        if not rows:
            self._clear_benchmark_chart()
            return

        if Figure is None or FigureCanvasTkAgg is None:
            messagebox.showwarning("Charts unavailable", "Matplotlib Tk support is not available.")
            return

        self._clear_benchmark_chart()

        figure = Figure(figsize=(7.5, 3.6), dpi=100)
        axis = figure.add_subplot(111)
        metric = self.chart_metric.get()

        ylabel = self._benchmark_metric_ylabel(metric)
        if metric == "Log Time":
            axis.set_yscale("log")

        if self.chart_view.get() == "Average repeats":
            groups = self._aggregate_benchmark_rows(rows)
            self._draw_aggregate_bars(axis, groups, metric)
            labels = [group["label"] for group in groups]
            x = list(range(len(groups)))
            statuses = []
            for group in groups:
                for status in group["status_counts"]:
                    if status not in statuses:
                        statuses.append(status)
        else:
            x = list(range(len(rows)))
            labels = [self._benchmark_chart_label(row) for row in rows]
            y = [self._benchmark_metric_value(row, metric) for row in rows]
            if metric == "Log Time":
                y = [max(value, 1e-9) for value in y]
            colors = [self._benchmark_bar_color(row.status) for row in rows]
            axis.bar(x, y, color=colors)
            statuses = [row.status for row in rows]

        axis.set_title(self._benchmark_chart_title(metric, rows))
        axis.set_ylabel(ylabel)
        axis.set_xticks(x)
        axis.set_xticklabels(labels, rotation=45, ha="right", fontsize=8)
        self._draw_benchmark_status_legend(axis, statuses)
        figure.tight_layout()

        self.benchmark_figure = figure
        self.benchmark_canvas = FigureCanvasTkAgg(figure, master=self.chart_frame)
        self.benchmark_canvas.draw()
        chart_widget = self.benchmark_canvas.get_tk_widget()
        chart_widget.configure(width=520, height=220)
        chart_widget.grid(row=0, column=0, sticky="nsew")

    def _benchmark_bar_color(self, status: str) -> str:
        return {
            "SAT": "#4c78a8",
            "UNSAT": "#e45756",
            "TIMEOUT": "#f58518",
            "SKIPPED": "#bab0ab",
            "CANCELLED": "#9d9d9d",
            "UNKNOWN": "#b279a2",
        }.get(status, "#72b7b2")

    def _benchmark_chart_label(self, row: BenchmarkRow) -> str:
        case_name = row.case_name
        problem_prefix = f"{row.problem_type} "
        if case_name.startswith(problem_prefix):
            case_name = case_name[len(problem_prefix):]
        prefix = f"{row.run_label}\n" if row.run_label else ""
        return f"{prefix}{case_name}\n{row.solver}"

    def _benchmark_group_key(self, row: BenchmarkRow) -> tuple:
        return (
            row.run_label,
            row.problem_type,
            row.case_name,
            row.solver,
        )

    def _aggregate_benchmark_rows(self, rows: list[BenchmarkRow]) -> list[dict]:
        groups_by_key = {}
        groups = []
        for row in rows:
            key = self._benchmark_group_key(row)
            if key not in groups_by_key:
                group = {
                    "key": key,
                    "case_name": row.case_name,
                    "problem_type": row.problem_type,
                    "detail": row.detail,
                    "solver": row.solver,
                    "clauses": row.clauses,
                    "variables": row.variables,
                    "generation_mode": row.generation_mode,
                    "edge_count": row.edge_count,
                    "label": self._benchmark_chart_label(row),
                    "rows": [],
                    "finished_rows": [],
                    "status_counts": {},
                }
                groups_by_key[key] = group
                groups.append(group)

            group = groups_by_key[key]
            group["rows"].append(row)
            if row.status in ("SAT", "UNSAT"):
                group["finished_rows"].append(row)
            group["status_counts"][row.status] = group["status_counts"].get(row.status, 0) + 1

        return groups

    def _benchmark_metric_value(self, row: BenchmarkRow, metric: str) -> float:
        if metric in ("Raw Time", "Log Time"):
            return row.elapsed
        if metric == "Normalized Time":
            return row.elapsed / max(row.variables, 1)
        if metric == "Conflicts":
            return 0 if row.conflicts == "-" else float(row.conflicts)
        return 0 if row.decisions == "-" else float(row.decisions)

    def _benchmark_group_metric_value(self, group: dict, metric: str) -> float:
        rows = group["finished_rows"]
        if not rows:
            return 0.0
        return sum(self._benchmark_metric_value(row, metric) for row in rows) / len(rows)

    def _benchmark_metric_ylabel(self, metric: str) -> str:
        if metric == "Raw Time":
            return "Seconds"
        if metric == "Log Time":
            return "Seconds (log)"
        if metric == "Normalized Time":
            return "Seconds / variable"
        if metric == "Conflicts":
            return "Conflicts"
        return "Decisions"

    def _benchmark_status_order(self, statuses) -> list[str]:
        preferred = ["SAT", "UNSAT", "TIMEOUT", "SKIPPED", "CANCELLED", "UNKNOWN"]
        seen = set()
        ordered = []
        for status in preferred:
            if status in statuses and status not in seen:
                ordered.append(status)
                seen.add(status)
        for status in statuses:
            if status not in seen:
                ordered.append(status)
                seen.add(status)
        return ordered

    def _benchmark_status_count_label(self, status_counts: dict[str, int]) -> str:
        short_names = {
            "SAT": "S",
            "UNSAT": "U",
            "TIMEOUT": "T",
            "SKIPPED": "K",
        }
        parts = []
        for status in self._benchmark_status_order(status_counts):
            label = short_names.get(status, status)
            parts.append(f"{label}:{status_counts[status]}")
        return " ".join(parts)

    def _draw_aggregate_bars(self, axis, groups: list[dict], metric: str) -> None:
        placeholder_height = 1e-9 if metric == "Log Time" else 1e-6
        for index, group in enumerate(groups):
            average_value = self._benchmark_group_metric_value(group, metric)
            display_height = average_value if average_value > 0 else placeholder_height
            total_count = len(group["rows"])
            bottom = 0.0
            for status in self._benchmark_status_order(group["status_counts"]):
                count = group["status_counts"][status]
                height = display_height * count / total_count if total_count else 0
                axis.bar(index, height, bottom=bottom, color=self._benchmark_bar_color(status))
                bottom += height

            axis.text(
                index,
                display_height,
                self._benchmark_status_count_label(group["status_counts"]),
                ha="center",
                va="bottom",
                fontsize=7,
                rotation=90,
            )
        axis.margins(y=0.25)

    def _benchmark_chart_title(self, metric: str, rows: list[BenchmarkRow] | None = None) -> str:
        rows = self.benchmark_rows if rows is None else rows
        problem_types = []
        for row in rows:
            if row.problem_type not in problem_types:
                problem_types.append(row.problem_type)

        suffix = " (Average repeats)" if hasattr(self, "chart_view") and self.chart_view.get() == "Average repeats" else ""
        if self.benchmark_filter_run_label is not None:
            suffix = f"{suffix} - {self._benchmark_filter_label_text()}"
        if len(problem_types) == 1:
            return f"{problem_types[0]} - {metric}{suffix}"
        if problem_types:
            return f"Mixed Problems - {metric}{suffix}"
        return f"{metric}{suffix}"

    def _draw_benchmark_status_legend(self, axis, statuses=None) -> None:
        try:
            from matplotlib.patches import Patch
        except Exception:
            return

        if statuses is None:
            statuses = [row.status for row in self.benchmark_rows]
        statuses = self._benchmark_status_order(statuses)

        handles = [
            Patch(color=self._benchmark_bar_color(status), label=status)
            for status in statuses
        ]
        if handles:
            axis.legend(handles=handles, loc="best", fontsize=8)

    def export_benchmark_csv(self) -> None:
        rows = self._visible_benchmark_rows()
        if not rows:
            messagebox.showinfo("No benchmark data", "There are no visible benchmark rows to export.")
            return

        default_name = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = filedialog.asksaveasfilename(
            initialdir=str(BENCHMARK_OUTPUT),
            initialfile=default_name,
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )

        if path:
            write_benchmark_csv(path, rows)
            messagebox.showinfo("Exported", f"Saved benchmark CSV to {path}")

    def export_random_3sat_csv(self) -> None:
        rows = [
            row
            for row in self._visible_benchmark_rows()
            if row.problem_type == "Random 3-SAT"
        ]
        if not rows:
            messagebox.showinfo("No Random 3-SAT data", "There are no visible Random 3-SAT rows to export.")
            return

        default_name = f"random_3sat_benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        path = filedialog.asksaveasfilename(
            initialdir=str(BENCHMARK_OUTPUT),
            initialfile=default_name,
            defaultextension=".csv",
            filetypes=[("CSV", "*.csv"), ("All files", "*.*")],
        )

        if path:
            write_random_3sat_benchmark_csv(path, rows)
            messagebox.showinfo("Exported", f"Saved Random 3-SAT benchmark CSV to {path}")

    def export_benchmark_chart(self) -> None:
        if self.benchmark_figure is None:
            self.draw_benchmark_chart()

        if self.benchmark_figure is None:
            return

        default_name = f"benchmark_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        path = filedialog.asksaveasfilename(
            initialdir=str(BENCHMARK_OUTPUT),
            initialfile=default_name,
            defaultextension=".png",
            filetypes=[("PNG", "*.png"), ("All files", "*.*")],
        )

        if path:
            self.benchmark_figure.savefig(path)
            messagebox.showinfo("Exported", f"Saved chart to {path}")


def main() -> None:
    root = tk.Tk()
    SATApp(root)
    root.mainloop()


if __name__ == "__main__":
    main()
