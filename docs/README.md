# Documentation

| Folder | For | Start with |
|---|---|---|
| [guide/](guide/) | people using or extending the app | [user guide](guide/user-guide.md) |
| [algorithms/](algorithms/) | how the solvers and encodings work (also shown on the Learn page) | [encodings](algorithms/encodings.md) |
| [report/](report/) | thesis and report material, in English (for people; agents edit it only when asked) | [report index](report/README.md) |
| [visualisations/](visualisations/) | standalone interactive DPLL, CDCL and WalkSAT pages | open `index.html` in any subfolder |
| [images/](images/) | screenshots for the README | [what to add](images/README.md) |
| [plans/](plans/) | features to build, and the order of all open work | [the work queue](plans/README.md) |
| [reviews/](reviews/) | dated code review findings still to fix | [2026-10-16 audit](reviews/2026-10-16-audit.md) |
| [adr/](adr/) | architecture decision records: one short note per decision | [what an ADR is](adr/README.md) |

The words the project uses are defined in [`GLOSSARY.md`](../GLOSSARY.md).

Guides:

- [User guide](guide/user-guide.md): every page of the app.
- [Benchmarking](guide/benchmarking.md): sweeps, limit rules, presets, parallel runs, CSV.
- [Solver performance](guide/performance.md): measurements, what was slow, how to profile.
- [Architecture](guide/architecture.md): how the pieces fit together.
- [HTTP API](guide/api.md): endpoints and live events.
- [Adding a problem or solver](guide/adding-a-problem.md): extension walkthrough.

Algorithms:

- [DPLL](algorithms/dpll.md), [CDCL](algorithms/cdcl.md),
  [WalkSAT and ProbSAT](algorithms/walksat.md)
- [Encodings](algorithms/encodings.md): each problem as CNF.
