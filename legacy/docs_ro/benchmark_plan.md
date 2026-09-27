# Plan de benchmark pentru aplicația SAT Solver

Acest document propune o metodologie de evaluare experimentală pentru aplicația SAT Solver. Valorile numerice trebuie completate numai după rulări reale ale aplicației. Tabelele folosesc `TODO` pentru câmpurile care trebuie măsurate.

## Obiective

1. Compararea solverelor complete `DPLL` și `CDCL`.
2. Compararea solverului `WalkSAT` cu strategia `Classic WalkSAT` și strategia `ProbSAT`.
3. Observarea diferenței dintre instanțe satisfiabile și nesatisfiabile.
4. Evaluarea impactului parametrilor: dimensiune, densitate graf, număr de clauze, seed, timeout și opțiuni solver.
5. Obținerea unor tabele și grafice care pot fi incluse în raport.

## Configurație generală

| Parametru | Valoare recomandată | Observații |
|---|---|---|
| Repetări | TODO | minim 3 pentru instanțe rapide |
| Timeout per solver | TODO | același pentru toate solverele |
| Seed | TODO | necesar pentru reproductibilitate |
| Solvere complete | CDCL, DPLL | pot demonstra SAT și UNSAT |
| Solvere incomplete | WalkSAT, ProbSAT | pot întoarce UNKNOWN |
| Export | CSV din aplicație | implementat prin `sat_core/benchmark.py` |

## Seturi de probleme

### Sudoku

Implementare: `problems/sudoku.py`, `utils/sudoku_general.py`, `sat_core/benchmark.py`.

| Dimensiune | Solvere | Repetări | Timeout | Observații |
|---:|---|---:|---:|---|
| 4x4 | CDCL, DPLL | TODO | TODO | instanță mică, verificare rapidă |
| 9x9 | CDCL, DPLL | TODO | TODO | instanță reprezentativă |
| 16x16 | CDCL | TODO | TODO | opțional, poate dura mai mult |
| 25x25 | CDCL | TODO | TODO | opțional, cost ridicat |

WalkSAT și ProbSAT pot fi rulate pe Sudoku pentru comparație, dar interpretarea trebuie făcută atent deoarece aceste metode nu pot demonstra UNSAT.

### N-Queens

Implementare: `problems/n_queens.py`.

| n | Solvere | Repetări | Timeout | Observații |
|---:|---|---:|---:|---|
| TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | creștere graduală a dimensiunii |
| TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | comparație între complet și local search |

### Random 3-SAT

Implementare: `problems/random_3sat.py`.

Moduri recomandate:

- `Planted SAT`, pentru instanțe satisfiabile;
- `Forced UNSAT`, pentru demonstrații UNSAT cu CDCL/DPLL;
- `Random`, pentru formule necontrolate sau mix SAT/UNSAT.

| Variabile | Raport clauze/variabile | Mod | Solvere | Repetări | Seed | Timeout |
|---:|---:|---|---|---:|---:|---:|
| TODO | TODO | Planted SAT | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |
| TODO | TODO | Forced UNSAT | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |
| TODO | TODO | Random | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |

Observație: pentru WalkSAT și ProbSAT, `UNKNOWN` nu este dovadă de nesatisfiabilitate.

### Graph Coloring

Implementare: `problems/graph_coloring.py`, `utils/graph_utils.py`.

| Noduri | Mod graf | Valoare mod | Culori | Solvere | Repetări | Timeout |
|---:|---|---:|---:|---|---:|---:|
| TODO | G(n,p) | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO |
| TODO | G(n,m) | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO |
| TODO | G(n,d) | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO |

### Hamiltonian Path

Implementare: `problems/hamiltonian_path.py`.

| Noduri | Mod graf | Valoare mod | Solvere | Repetări | Timeout |
|---:|---|---:|---|---:|---:|
| TODO | G(n,p) | TODO | CDCL, DPLL | TODO | TODO |
| TODO | G(n,m) | TODO | CDCL, DPLL | TODO | TODO |

WalkSAT și ProbSAT pot fi incluse ca metode incomplete, dar rezultatele `UNKNOWN` trebuie raportate separat.

### Clique și Independent Set

Implementare: `problems/clique.py`, `problems/independent_set.py`.

| Problemă | Noduri | Mod graf | Target k | Solvere | Repetări | Timeout |
|---|---:|---|---:|---|---:|---:|
| Clique | TODO | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO |
| Independent Set | TODO | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO |

### Graph Suite

Implementare: `sat_core/benchmark.py`.

`Graph Suite` este util deoarece rulează mai multe probleme pe același graf generat. Astfel, comparația între Graph Coloring, Hamiltonian Path, Clique și Independent Set devine mai corectă.

| Noduri | Mod graf | Probleme selectate | Solvere | Repetări | Seed | Timeout |
|---:|---|---|---|---:|---:|---:|
| TODO | TODO | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |

## Reguli de comparație corectă

1. Se folosește același timeout pentru toate solverele din aceeași serie.
2. Se păstrează același seed pentru instanțele generate aleator.
3. Pentru CDCL, se notează branching, faza inițială, restarturile și limita de clauze învățate.
4. Pentru WalkSAT/ProbSAT, se notează max tries, max flips, noise, adaptive noise și seed.
5. Se separă rezultatele `UNSAT` de `UNKNOWN`.
6. Nu se compară direct un `UNKNOWN` WalkSAT cu un `UNSAT` CDCL ca și cum ar avea aceeași semnificație.
7. Se exportă CSV-ul imediat după rulare și se păstrează configurația exactă.

## Tabel final recomandat

| Familie | Instanță | Solver | Opțiuni | Status | Timp mediu | Conflicte | Decizii | Propagări | Observații |
|---|---|---|---|---|---:|---:|---:|---:|---|
| TODO | TODO | CDCL | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | DPLL | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | WalkSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | ProbSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
