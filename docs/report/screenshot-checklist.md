# Screenshot checklist

> English, updated version of `legacy/docs_ro/screenshot_checklist.md`, for
> the web interface. The names in square brackets can be used directly as
> placeholders in the report.

## General interface

- [ ] [Figure 1: The main page of the application (problem gallery on the Solve page)]
- [ ] [Figure 2: The Solve page with a problem selected: input, solver and preview]
- [ ] [Figure 3: The Benchmarks page with the presets]
- [ ] [Figure 4: The Jobs page and the Jobs drawer with a running job]

## Generating and solving CNF

- [ ] [Figure 5: A Sudoku puzzle in the editor, with the CNF size estimate]
- [ ] [Figure 6: The CNF tab of a result, showing the generated DIMACS]
- [ ] [Figure 7: Choosing the CDCL solver and its options]
- [ ] [Figure 8: A SAT result: the solved board, the Verified badge and the statistics]
- [ ] [Figure 9: Downloading a CNF file (Encode only, then Download)]
- [ ] [Figure 10: Opening a DIMACS file on the DIMACS / CNF page]

## Graph problems

- [ ] [Figure 11: Typing the edges of a graph, and editing them in the preview]
- [ ] [Figure 12: Generating a random G(n,p) graph]
- [ ] [Figure 13: A colored graph after solving graph coloring]
- [ ] [Figure 14: A Hamiltonian path highlighted on the graph]
- [ ] [Figure 15: A clique highlighted on the graph]

## Solver options

- [ ] [Figure 16: CDCL options: branching, phase and restarts]
- [ ] [Figure 17: WalkSAT / ProbSAT options: tries, flips, noise]
- [ ] [Figure 18: Time limit and seed]

## Benchmarks

- [ ] [Figure 19: The benchmark builder: parameter grid, solvers and limit rules]
- [ ] [Figure 20: The live plan panel (cases, runs, largest formula)]
- [ ] [Figure 21: A benchmark running, with results streaming in]
- [ ] [Figure 22: Median time chart of a Random 3-SAT preset]
- [ ] [Figure 23: The SAT/UNSAT share chart (phase transition)]
- [ ] [Figure 24: Small multiples: one chart per value of a second parameter]
- [ ] [Figure 25: The run table with filters]
- [ ] [Figure 26: The details of one run (parameters, statistics, Open in Solve)]
- [ ] [Figure 27: Comparing two benchmarks]
- [ ] [Figure 28: The exported CSV opened in a spreadsheet]

## Educational visualisations

Files:

- `docs/visualisations/dpll/index.html`
- `docs/visualisations/cdcl/index.html`
- `docs/visualisations/walksat/index.html`

They are also reachable from the **Learn** page and online at
`https://aziyck.github.io/SATsolver/docs/visualisations/<name>/`.

- [ ] [Figure 29: The DPLL visualiser]
- [ ] [Figure 30: The CDCL visualiser and a learned clause]
- [ ] [Figure 31: The WalkSAT visualiser choosing an unsatisfied clause]

## Consistency tips

1. Use the same theme (light or dark) and the same window size for every
   screenshot; 1440 x 900 works well.
2. Close the Jobs drawer and notifications before capturing.
3. For benchmarks use real data, but keep sizes small when the point is only
   to show the interface.
4. For graphs use a fixed seed so the picture can be reproduced.
5. Each chart has a download button that saves a clean PNG of the chart
   alone.
6. In the report, explain every screenshot in 2 to 4 sentences.
