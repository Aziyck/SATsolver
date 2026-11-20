# Glossary

The words this project uses, each with one meaning. Use them the same way in
code, docs, plans and commit messages. Longer explanations live in the linked
documents; this file only pins the meaning.

## SAT basics

| Term | Meaning |
|---|---|
| variable | A yes/no unknown, written as a positive integer. |
| literal | A variable or its negation: `5` means "x5 is true", `-5` means "x5 is false". |
| clause | A list of literals; it is satisfied when at least one of them is true. |
| CNF | A formula as a list of clauses that must all be satisfied. The only input the solvers take. |
| unit clause | A clause with one literal, which therefore must be true. |
| empty clause | A clause with no literals. It can never be satisfied, so the formula is UNSAT. |
| tautology | A clause containing a literal and its negation. Always true; the solvers drop it. |
| assignment | A value for some (partial) or all (complete) variables. |
| model | A complete assignment that satisfies every clause. Proof that the formula is SAT. |
| DIMACS | The standard text format for CNF (`p cnf <vars> <clauses>`, clauses ending in `0`). See `sat_core/dimacs.py`. |
| encoding | Turning a problem (a Sudoku, a graph question) into CNF. See [encodings](docs/algorithms/encodings.md). |
| decoding | Turning a model back into the problem's answer (a grid, a coloring). |
| readable variable numbers | The encoders' numbering where the digits spell the meaning (`10203` = row 1, column 2, value 3). Sparse on purpose. |

## Answers

| Term | Meaning |
|---|---|
| SAT | A model was found. |
| UNSAT | A complete solver proved that no model exists. |
| UNKNOWN | An incomplete solver gave up. Says nothing about satisfiability; never treat it as UNSAT. |
| TIMEOUT | The time limit ended the run. |
| CANCELLED | The user stopped the job. |
| SKIPPED | A limit rule or the user skipped this run. |
| ERROR | The solver or the encoder failed; the message is in `error`. |
| status | One of the seven values above, for one run. (A job has its own states: queued, running, cancelling, done, failed, cancelled, interrupted.) |
| verified | The model satisfies every clause and the decoded answer passes the problem's own check. |
| expected status | The answer known by construction (planted SAT, forced UNSAT). A different solver answer is flagged. |
| complete solver | Can prove both SAT and UNSAT: DPLL, CDCL. |
| incomplete solver | Can only find models: WalkSAT, ProbSAT. Its failure is UNKNOWN. |

## The app

| Term | Meaning |
|---|---|
| problem | A registered `ProblemSpec`: its parameters, encoder, decoder and check (Sudoku, N-Queens, ...). |
| parameter field | One `ParamField` of a problem or solver: the single description used for validation, forms, sweeps and CSV. |
| instance | One concrete CNF built from a problem and its parameters (`ProblemInstance`). |
| solver | A registered `SolverSpec`: `cdcl`, `dpll`, `walksat`, `probsat`. |
| solver options | The values of a solver's parameter fields for one run. |
| registry | The table, keyed by name, of everything of one kind the app knows: problems (`problems/base.py`, filled by `@register_problem`) and solvers (`sat_core/solver_registry.py`). Code looks a thing up by its key instead of branching on names. Filled when the module is imported. |
| job | One unit of work the server runs in its own process: a solve, an encode (kind `generate`) or a benchmark. Shown as J1, J2, ... |
| happening | One of the nine things that can change a job's status (`slot_free`, `stop`, `process_exited`, ...), the arrows of the status diagram in [architecture](docs/guide/architecture.md#statuses). Not a `RunEvent`: the job's `done`, `error` and `cancelled` events are three of the happenings, the others come from the manager, the user or the process. See `sat_web/lifecycle.py`. |
| job id | The number in J12. Not reused while any job exists. |
| daemon | Python's meaning, not the Unix one. A daemon process is killed when its parent exits and may not start child processes; a daemon thread does not keep its process alive. Job processes are not daemons. See [how it works](docs/guide/how-it-works.md#daemons-and-the-watchdog). |
| process | A running program with its own memory and its own Python interpreter. The browser, the server and each job are separate processes; two processes share nothing unless something is built for it (a queue, a flag). A process can be stopped from outside. See [how it works](docs/guide/how-it-works.md#jobs). |
| thread | One line of work inside a process. The threads of a process share its memory, so they can read and change the same objects, which is why the server needs a lock. Python runs one thread's Python code at a time (the GIL), so threads help with waiting, not with computing in parallel. |
| event loop | The one server thread that runs many small waiting tasks by switching between them whenever one is waiting: every open WebSocket, the regular publishing of job summaries, and the HTTP handlers of the job endpoints, which hand slow work to a pool of worker threads. Started by Uvicorn. |
| reader thread | The server thread, one per running job, that takes that job's events off its event queue and applies them to the job (`JobManager._reader`). See [how it works](docs/guide/how-it-works.md#what-the-big-picture-hides). |
| run token | The object a job and its solvers ask whether to stop (`RunToken`, `sat_core/runtime.py`). It reads the cancel flag, the skip flag and the run's deadline at once. See [how it works](docs/guide/how-it-works.md#stop-skip-and-timeouts). |
| seed | The number that makes a random instance or a random solver choice reproducible. |
| planted SAT | A random formula built around a hidden model, so it is satisfiable by construction. |
| forced UNSAT | A random formula with a small contradictory core added, so it is unsatisfiable by construction. |
| preview | The picture and size estimate shown while the form is edited, before any job. |
| estimate | The CNF size computed from the parameters without building the formula. Used for the size guard. |

## Benchmarks

| Term | Meaning |
|---|---|
| benchmark | A job that runs several solvers on many instances and records one row per run. |
| segment | One parameter grid of a benchmark request. A benchmark is the union of its segments. |
| sweep | A list or range for one field (`"50, 100"`, `"1..10"`), expanded into one value per case. |
| case | One instance of the benchmark: a problem, concrete parameter values and a repeat number. Encoded once. |
| repeat | Running a case again with a derived seed. Repeat 1 uses the case's own seed. |
| solver entry | One line of the benchmark's solver list: a solver, its options and a label. The same solver may appear twice. |
| run | One solver entry on one case. Every solver entry of a case gets the same CNF. |
| row | The stored result of one run. Row index = case index x number of solver entries + position of the entry. |
| limit rule | "For this solver, from this many variables on: cap the time, or skip." Skip wins over cap; the smallest cap applies. |
| `size_variables` | The size a limit rule compares against: n for Random 3-SAT, the header count for DIMACS, else the number of distinct variables. |
| preset | A ready-made benchmark request. |
| workers | How many cases a benchmark solves at the same time (default 1). Changes the measured times and the order in which rows arrive, never which rows exist, their indices or their answers. |
| graph suite | Several graph problems in one benchmark, run on the same graphs. |

## Search solvers (DPLL, CDCL)

Details: [DPLL](docs/algorithms/dpll.md), [CDCL](docs/algorithms/cdcl.md).

| Term | Meaning |
|---|---|
| decision | A guess: the solver picks an unassigned variable and a value. |
| propagation | An assignment forced by a clause that has one unassigned literal left and no true one (unit propagation). |
| conflict | A clause whose literals are all false under the current assignment. |
| trail | The list of assigned literals in the order they were assigned. |
| decision level | How many decisions are open when a literal is assigned. Level 0 holds facts that need no guess. |
| backtracking | DPLL's reaction to a conflict: undo the latest decision and try its other value. |
| backjump | CDCL's reaction: undo several levels at once, back to where the learned clause forces a literal. |
| reason | The clause that forced a propagated literal. Decisions have none. |
| implication graph | Literals linked to the reasons that forced them. Conflict analysis walks it backwards. |
| learned clause | A clause CDCL derives from a conflict. It follows from the formula and blocks the same mistake. |
| first UIP | The point where conflict analysis stops: the learned clause has exactly one literal from the current level. |
| asserting literal | That one literal. After the backjump the learned clause forces it. |
| watched literals | Two literals per clause that propagation tracks; a clause is visited only when one of them becomes false. |
| branching heuristic | How the decision variable is chosen: VSIDS, most frequent, MOMS, DLIS, random. |
| VSIDS / activity | A score per variable, raised when it takes part in a conflict; the highest unassigned score is decided next. |
| phase | The value tried first for a decision variable. Phase saving reuses the value it had last. |
| restart | Dropping every decision while keeping learned clauses, scores and saved phases. |
| Luby sequence | The restart schedule 1, 1, 2, 1, 1, 2, 4, ... multiplied by the restart interval. |
| LBD | Literal block distance: the number of different decision levels in a learned clause when it was learned. Lower is better. |
| glue clause | A learned clause with LBD of at most 2. Never deleted by the automatic clean-up. |
| clean-up (reduction) | Deleting the weaker half of the learned clauses to keep propagation fast. |
| locked clause | A learned clause that is currently the reason of an assignment. It cannot be deleted. |

## Local search (WalkSAT, ProbSAT)

Details: [WalkSAT and ProbSAT](docs/algorithms/walksat.md).

| Term | Meaning |
|---|---|
| flip | Changing the value of one variable in the complete assignment. |
| try | One run from a fresh random assignment, at most "max flips" flips long. |
| budget | Max tries x max flips. Using it up gives UNKNOWN. |
| break | For a variable: how many satisfied clauses its flip would make false. |
| make | For a variable: how many false clauses its flip would satisfy. |
| critical variable | The one variable that keeps a clause true. Its flip breaks that clause. |
| free move | Flipping a variable with break 0. WalkSAT always takes one when it exists. |
| noise | WalkSAT's probability of flipping a random variable of the clause when there is no free move. |
| adaptive noise | Raising the noise when the search stagnates and lowering it after progress. |
| cb | The constant in ProbSAT's weight function; a higher value avoids breaks more strongly. |

## Workflow

Details: [docs/plans/README.md](docs/plans/README.md).

| Term | Meaning |
|---|---|
| review | A dated list of findings about the existing code (`docs/reviews/`). |
| plan | The design and task list of a feature that is not built yet (`docs/plans/`). |
| item | One finding or task with an ID (A3, OPT-1): the unit of work, about one commit. |
| done when | The observable behaviour that proves an item is finished. The agent turns it into a test first. |
| difficulty | easy, medium or hard: how much can go wrong, which decides the model and the review an item gets. |
| blocked | An item that must wait until the items it names are closed. |
| needs decision | An open choice only the user can make. Work on the item stops there. |
| escalate | Mark an item that a session could not finish, with what was tried, for a stronger model. |
| ADR | Architecture decision record: a short, numbered, never-edited note of one decision and its reasons (`docs/adr/`). |
