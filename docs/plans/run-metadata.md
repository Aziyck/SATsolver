# Plan: record where and how every run happened

- **Status:** proposed, not started
- **Written:** 2026-10-19 (as Part 1 of the PyPy plan); its own plan since
  2026-11-13
- **Related:** [PyPy solver runner](pypy-solver-runner.md) (shows the
  interpreter through this metadata), [memory measurement](memory-measurement.md),
  [Benchmarking](../guide/benchmarking.md)
- Item format, difficulty and closing rule: [README.md](README.md)

## Goal

Every solve job and every benchmark records the machine and the software it
ran on, shows it in the UI and carries it into the CSV, so a result table can
say exactly what produced it and two benchmarks from different machines are
never compared by accident.

## Non-goals

- Memory use of a run: see the memory plan.
- A new runtime dependency (`psutil` would make this easier, but the project
  avoids dependencies).

## What to record

Collected once per job, inside the process that runs the solver (so it shows
PyPy when PyPy is used):

| Field | Example | How (standard library only) |
|---|---|---|
| `python_implementation` | `CPython` / `PyPy` | `platform.python_implementation()` |
| `python_version` | `3.11.15` | `platform.python_version()` |
| `os` | `Linux 6.8 (x86_64)` | `platform.system()`, `platform.release()`, `platform.machine()` |
| `cpu_model` | `AMD Ryzen 7 5800U` | Linux: `model name` in `/proc/cpuinfo`; macOS: `sysctl -n machdep.cpu.brand_string`; Windows: registry `HKLM\HARDWARE\DESCRIPTION\System\CentralProcessor\0\ProcessorNameString` (`winreg`); fall back to `platform.processor()` |
| `cpu_logical_cores` | `16` | `os.cpu_count()` |
| `cpu_physical_cores` | `8` or `null` | Linux: distinct `(physical id, core id)` pairs in `/proc/cpuinfo`; elsewhere `null` unless cheap |
| `ram_total_gb` | `15.5` | POSIX: `os.sysconf("SC_PAGE_SIZE") * os.sysconf("SC_PHYS_PAGES")`; Windows: `ctypes` `GlobalMemoryStatusEx` |
| `wizsat_version` | `2.0.0` | today `VERSION` in `sat_web/api.py`; move it into `sat_core` so the job process can read it |
| `git_commit` | `9e11958` or `null` | `git rev-parse --short HEAD` in the repo root, if git is there |
| `git_dirty` | `true` / `false` / `null` | `git status --porcelain` is not empty |
| `workers` | `1` | benchmark request (parallel cases) |
| `started_at` | ISO time with zone | already stored on the job |

- **Hostname:** not recorded by default (CSV files get shared). Opt-in with a
  setting such as `WIZSAT_RECORD_HOSTNAME=1`.
- Every lookup is wrapped so a failure gives `null`, never an error.
- Cache the result per process: CPU model and RAM do not change during a job.

## Tasks

- [ ] **META-1. `run_environment()` returns the facts above**
  - **Difficulty:** medium (three operating systems)
  - **How:** a new module `sat_core/environment.py` with
    `run_environment() -> dict`: standard library only, no `sat_web` import,
    cached per process. Move `VERSION` from `sat_web/api.py` into `sat_core`
    and import it back.
  - **Done when:** tests show it returns every key of the table with
    JSON-serialisable values on the CI platforms (Ubuntu, Windows), and
    returns `None` values instead of raising when `/proc/cpuinfo` and git are
    patched away.

- [ ] **META-2. Jobs store and return their environment**
  - **Difficulty:** hard (database migration, job events)
  - **Blocked by:** META-1
  - **How:** `run_job` in `sat_core/jobs.py` sends the environment once at the
    start (a new `EVENT_ENVIRONMENT` in `sat_core/runtime.py`).
    `sat_web/store.py` gets a JSON column `environment` on `jobs`; the table
    is created with `CREATE TABLE IF NOT EXISTS`, so add `ALTER TABLE jobs ADD
    COLUMN environment TEXT` when the column is missing. `JobManager` keeps it
    on `Job` and returns it from `detail()` only (not in the summary list).
  - **Done when:** an API test sees `environment.python_implementation` on a
    finished job's detail; a second test opens a database file created
    without the column and the server starts, lists the old jobs and gives
    them `environment: null`.

- [ ] **META-3. The UI shows the machine**
  - **Difficulty:** easy
  - **Blocked by:** META-2
  - **How:** `environment` on `JobDetail` in `frontend/src/api/types.ts`
    (nullable). A "Machine" block in the solve job's Settings tab and in the
    benchmark Setup tab (`components/SolverSettingsTable.tsx`,
    `components/BenchmarkSetup.tsx`).
  - **Done when:** a component test shows the block with the interpreter, CPU,
    cores, RAM and commit for a job that has them, and "not recorded" for a
    job without `environment`.

- [ ] **META-4. The CSV carries the machine**
  - **Difficulty:** medium (changes a file format people keep)
  - **Blocked by:** META-2
  - **How:** `rows_to_csv` in `sat_core/benchmark.py` adds a few columns per
    row: `python`, `cpu`, `cores`, `ram_gb`, `os`, `wizsat_commit`. Per-row
    columns (not header comments) keep the file a valid CSV and keep the
    information when benchmarks from different machines are exported together
    with `/api/export.csv?jobs=...`.
  - **Done when:** a test exports a benchmark and finds the new columns filled
    on every row; exporting a benchmark stored before this change gives empty
    cells in those columns, not an error.

- [ ] **META-5. Docs say what is recorded**
  - **Difficulty:** easy
  - **Blocked by:** META-3, META-4
  - **How:** `docs/guide/benchmarking.md` (CSV columns, "what to report"),
    `docs/guide/api.md` (job detail), `docs/guide/user-guide.md` (the Machine
    block).
  - **Done when:** each of those documents describes the new fields, and the
    plan's status line says done.
