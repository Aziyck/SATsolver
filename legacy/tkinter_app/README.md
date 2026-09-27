# Legacy Tkinter App (archived)

This folder is a frozen, self-contained snapshot of the original WizSAT
desktop app (Tkinter + Matplotlib) as it was before the move to the web UI.
It is kept for reference only. New work goes into the web app at the
repository root (see the main `README.md`).

The snapshot has its own copies of `sat_core/`, `problems/`, `solvers/` and
`utils/`, so it keeps running even as the product code changes. Nothing in
the product code imports from here.

Differences from the last pre-web commit (`008d3d9`): the Random 3-SAT preset
values were aligned with the decisions taken during the web migration
(Preset B: seeds 1..10 = 100 cases, DPLL capped at n=150 and skipped from
n=200; Preset C: seeds 1..30 = 270 cases; DPLL fallback cap 10 s), which also
makes the archived test suite pass again.

## Run it

Requirements: Python 3.10+ with Tkinter, plus Matplotlib for charts.

```powershell
cd legacy/tkinter_app
python -m pip install matplotlib
python app.py
```

On Linux, Tkinter usually comes from the system package manager
(for example `sudo apt install python3-tk`).

## Run its tests

```powershell
cd legacy/tkinter_app
python -m unittest discover -s tests
```

On a headless Linux machine run the UI tests under a virtual display:
`xvfb-run -a python -m unittest discover -s tests`.

`APP_GUIDE.md` is the original user guide for this desktop UI.
