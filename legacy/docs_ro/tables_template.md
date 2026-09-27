# Șabloane de tabele pentru raport

Aceste tabele sunt pregătite pentru completare manuală după rularea aplicației. Valorile `TODO` nu reprezintă rezultate.

## Tabel 1. Structura aplicației

| Modul | Rol | Observații |
|---|---|---|
| `app.py` | interfață Tkinter, formulare, joburi, afișare rezultate, export | TODO |
| `problems/` | encodere pentru probleme în SAT | TODO |
| `sat_core/` | modele, solver runner, benchmark, runtime, worker processes, DIMACS | TODO |
| `solvers/` | DPLL, CDCL, WalkSAT | TODO |
| `utils/` | funcții auxiliare pentru variabile, grafuri și Sudoku | TODO |
| `docs/visualisations/` | vizualizări educaționale HTML | TODO |

## Tabel 2. Probleme codificate în SAT

| Problemă | Fișier principal | Variabilă SAT | Tipuri de clauze | Decoder |
|---|---|---|---|---|
| Sudoku | `problems/sudoku.py` | `sudoku_var(r,c,v)` | celulă, linie, coloană, bloc, valori inițiale | `decode_sudoku` |
| N-Queens | `problems/n_queens.py` | `n_queens_var(row,col,size)` | linii, coloane, diagonale | `decode_n_queens` |
| Graph Coloring | `problems/graph_coloring.py` | `color_var(node,color,colors)` | culoare per nod, unicitate, muchii | `decode_coloring` |
| Hamiltonian Path | `problems/hamiltonian_path.py` | `hamiltonian_var(position,node,node_count)` | poziții, unicitate, adiacență | `decode_hamiltonian_path` |
| Clique | `problems/clique.py` | `clique_var(slot,node,node_count)` | sloturi, unicitate, conexiuni | `decode_clique` |
| Independent Set | `problems/independent_set.py` | `independent_var(slot,node,node_count)` | sloturi, unicitate, interdicții pe muchii | `decode_independent_set` |
| Random 3-SAT | `problems/random_3sat.py` | variabile directe 1..n | clauze de 3 literali | `_decode_assignment` |

## Tabel 3. Solvere și proprietăți

| Solver | Fișier | Completitudine | Statusuri relevante | Opțiuni principale |
|---|---|---|---|---|
| DPLL | `solvers/dpll.py` | complet | SAT, UNSAT, TIMEOUT, CANCELLED | small-clause implicit, logging |
| CDCL | `solvers/cdcl.py` | complet | SAT, UNSAT, TIMEOUT, CANCELLED | branching, phase, restarts, learned limit, seed |
| WalkSAT | `solvers/walksat.py` | incomplet | SAT, UNKNOWN, TIMEOUT, CANCELLED | tries, flips, noise, adaptive noise, seed |
| ProbSAT | `solvers/walksat.py` | incomplet | SAT, UNKNOWN, TIMEOUT, CANCELLED | `selection_mode="probsat"`, noise, seed |

## Tabel 4. Configurație experimentală

| Experiment | Familie probleme | Parametri | Solvere | Repetări | Timeout | Seed |
|---|---|---|---|---:|---:|---:|
| E1 | Sudoku | TODO | TODO | TODO | TODO | TODO |
| E2 | N-Queens | TODO | TODO | TODO | TODO | TODO |
| E3 | Random 3-SAT | TODO | TODO | TODO | TODO | TODO |
| E4 | Graph Coloring | TODO | TODO | TODO | TODO | TODO |
| E5 | Graph Suite | TODO | TODO | TODO | TODO | TODO |

## Tabel 5. Rezultate experimentale brute

| Experiment | Instanță | Solver | Status | Timp (s) | Conflicte | Decizii | Propagări | Learned clauses | Observații |
|---|---|---|---|---:|---:|---:|---:|---:|---|
| TODO | TODO | CDCL | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | DPLL | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | WalkSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | TODO | ProbSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

## Tabel 6. Rezultate agregate

| Familie | Solver | Rulări | SAT | UNSAT | UNKNOWN | TIMEOUT | Timp mediu (s) | Timp minim (s) | Timp maxim (s) |
|---|---|---:|---:|---:|---:|---:|---:|---:|---:|
| TODO | CDCL | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | DPLL | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | WalkSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | ProbSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

## Tabel 7. Interpretare comparativă

| Observație | Dovezi din benchmark | Interpretare |
|---|---|---|
| CDCL este mai rapid decât DPLL pe instanțe cu multe conflicte | TODO | clauzele învățate reduc repetarea conflictelor |
| WalkSAT găsește rapid unele instanțe SAT | TODO | local search poate fi eficient fără dovadă completă |
| ProbSAT diferă de Classic WalkSAT pe formule random | TODO | alegerea probabilistică schimbă traseul de căutare |
| UNKNOWN nu este echivalent cu UNSAT | TODO | WalkSAT/ProbSAT nu construiesc dovadă de nesatisfiabilitate |

## Tabel 8. Limitări și îmbunătățiri

| Limitare | Impact | Direcție de dezvoltare |
|---|---|---|
| Benchmark fără măsurare memorie | analiza performanței este parțială | adăugarea unor măsurători de memorie |
| WalkSAT și ProbSAT sunt incomplete | pot întoarce UNKNOWN | raportare separată față de UNSAT |
| DPLL are opțiuni limitate în UI | comparație mai simplă, dar mai puțin flexibilă | expunerea unor heuristici suplimentare |
| Benchmark-urile random depind de seed | rezultate greu de reprodus fără configurare | folosirea seed-urilor fixe |
