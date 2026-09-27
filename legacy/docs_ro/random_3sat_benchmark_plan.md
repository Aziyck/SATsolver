# Plan de benchmark pentru Random 3-SAT

Acest document descrie metodologia recomandata pentru evaluarea solverelor pe instante Random 3-SAT in aplicatia SAT Solver. Scopul nu este obtinerea unui singur timp absolut, ci compararea comportamentului solverelor pe familii de formule generate controlat, folosind aceleasi instante pentru fiecare solver.

## Obiective

Benchmark-ul urmareste trei intrebari practice:

- cum se modifica timpul de rulare cand numarul de variabile creste;
- cum influenteaza raportul clauze/variabile dificultatea formulelor;
- cum se comporta solverele complete, CDCL si DPLL, fata de metodele de cautare locala, WalkSAT si ProbSAT.

Rezultatele trebuie exportate numai dupa rularea efectiva a experimentelor. Tabelele din raport vor contine valori masurate, nu rezultate estimate.

## Preset A: Planted SAT

Presetul Planted SAT genereaza instante satisfiabile prin constructie. Setarile propuse sunt:

| Parametru | Valori |
| --- | --- |
| n | raport clauze/variabile | seed-uri | solvere |
| --- | --- | --- | --- |
| 50 | 2.5, 3.5, 4.25, 5.5 | 1..20 | CDCL, DPLL, WalkSAT, ProbSAT |
| 100 | 2.5, 3.5, 4.25, 5.5 | 1..20 | CDCL, DPLL, WalkSAT, ProbSAT |
| 150 | 2.5, 3.5, 4.25, 5.5 | 1..20 | CDCL, DPLL, WalkSAT, ProbSAT |
| 200 | 2.5, 3.5, 4.25, 5.5 | 1..20 | CDCL, WalkSAT, ProbSAT; DPLL este marcat SKIPPED |
| 300 | 3.5, 4.25, 5.5 | 1..10 | CDCL, WalkSAT, ProbSAT; DPLL este marcat SKIPPED |

Acest preset este potrivit pentru compararea tuturor solverelor, deoarece fiecare instanta are cel putin o atribuire satisfiabila. WalkSAT si ProbSAT pot confirma SAT prin gasirea unei atribuiri, chiar daca nu pot demonstra UNSAT.

## Preset B: Forced UNSAT

Presetul Forced UNSAT este folosit ca test de control pentru solverele complete.

| Parametru | Valori |
| --- | --- |
| n | raport clauze/variabile | seed-uri | solvere |
| --- | --- | --- | --- |
| 50 | 3.5, 4.25, 5.5 | 1..10 | CDCL, DPLL |
| 100 | 3.5, 4.25, 5.5 | 1..10 | CDCL, DPLL |
| 150 | 4.25, 5.5 | 1..10 | CDCL, DPLL cu timeout preset |
| 200 | 4.25, 5.5 | 1..10 | CDCL; DPLL este marcat SKIPPED |

WalkSAT si ProbSAT nu sunt incluse implicit aici deoarece sunt algoritmi incompleti: daca nu gasesc o solutie, rezultatul corect este `UNKNOWN`, nu `UNSAT`. Prin urmare, instantele Forced UNSAT sunt utile mai ales pentru verificarea capacitatii CDCL si DPLL de a produce o concluzie negativa.

## Preset C: Mixed SAT/UNSAT

Presetul Mixed SAT/UNSAT foloseste raportul 4.25 si variaza proportia de instante satisfiabile.

| Parametru | Valori |
| --- | --- |
| variabile | 100, 150, 200 |
| raport clauze/variabile | 4.25 |
| fractii SAT | 0.3, 0.5, 0.7 |
| seed-uri | 1..30 |
| solvere | CDCL, DPLL, WalkSAT, ProbSAT |

Acest preset este potrivit pentru discutia practica despre regiunea dificila a 3-SAT. Rezultatele WalkSAT si ProbSAT trebuie interpretate separat: `SAT` inseamna ca s-a gasit o atribuire, iar `UNKNOWN` inseamna doar ca solverul nu a gasit una in limitele impuse.

## Alegerea rapoartelor

Raportul clauze/variabile controleaza densitatea formulei. Pentru Random 3-SAT, valori mici precum 2.5 produc de obicei formule mai relaxate, unde exista mai multe atribuiri satisfiabile. Valori mai mari, precum 5.5, produc formule mai constranse si tind sa fie mai des nesatisfiabile.

Raportul 4.25 este important deoarece este aproape de regiunea de tranzitie SAT/UNSAT cunoscuta pentru Random 3-SAT. In aceasta zona, probabilitatea ca formula sa fie satisfiabila scade rapid, iar instantele sunt frecvent mai dificile pentru solverele complete. Din acest motiv, raportul 4.25 apare atat in presetul Planted SAT, cat si in Forced UNSAT si Mixed SAT/UNSAT.

## Reguli de comparatie

Pentru o comparatie corecta, fiecare combinatie de parametri trebuie generata o singura data pentru un seed dat, apoi aceeasi formula CNF trebuie rulata cu toate solverele selectate. Aplicatia salveaza in randurile de benchmark metadatele instantei si clauzele generate, astfel incat exportul sa reflecte formula efectiv masurata.

Timeout-ul trebuie mentinut constant in cadrul unui experiment, cu exceptiile configurate explicit pentru DPLL in preseturi. In presetul Planted SAT, DPLL este omis pentru `n >= 200`. In presetul Forced UNSAT, DPLL este rulat cu timeout preset pentru `n = 150` si este omis pentru `n = 200`. Randurile omise sunt exportate cu statusul `SKIPPED`.

## De ce WalkSAT si ProbSAT se evalueaza mai ales pe instante SAT

WalkSAT si ProbSAT sunt metode de cautare locala. Ele cauta o atribuire care satisface toate clauzele, dar nu construiesc o demonstratie de nesatisfiabilitate. Din acest motiv:

- pe instante SAT, pot fi comparate dupa timp, numar de flips, numar de incercari si calitatea solutiei gasite;
- pe instante UNSAT, un rezultat `UNKNOWN` nu este o eroare, ci o limita a metodei;
- pentru corectitudinea UNSAT trebuie folosite solvere complete, precum CDCL si DPLL.

## Metrici recomandate

Exportul dedicat Random 3-SAT foloseste coloanele:

```text
problem_mode, n_vars, ratio, n_clauses, sat_fraction, seed, solver, status,
elapsed, decisions, conflicts, propagations, learned_clauses, flips, tries,
best_unsatisfied, timeout
```

In raport se recomanda urmatoarele analize:

- timp mediu si median pe fiecare combinatie `n_vars`, `ratio`, `solver`;
- rata de `SAT`, `UNSAT`, `UNKNOWN` si `TIMEOUT`;
- numar de decizii, conflicte, propagari si clauze invatate pentru CDCL/DPLL;
- numar de flips, tries si `best_unsatisfied` pentru WalkSAT/ProbSAT;
- comparatie separata pentru raportul 4.25;
- discutie separata pentru instantele UNSAT, unde WalkSAT/ProbSAT nu pot oferi dovada de nesatisfiabilitate.

## Interpretarea valorii UNKNOWN

`UNKNOWN` trebuie interpretat in functie de solver:

- pentru WalkSAT si ProbSAT, inseamna ca nu s-a gasit o atribuire satisfiabila in limitele de tries/flips/timeout;
- pentru un solver complet, `UNKNOWN` poate indica o oprire inainte de concluzie, de exemplu timeout sau anulare controlata.

In tabelele finale, `UNKNOWN` nu trebuie amestecat cu `UNSAT`.

## Tabele pentru raport

Rezultatele finale se vor completa dupa rulare:

| Preset | Solver | n_vars | ratio | Seed-uri | Status dominant | Timp mediu | Observatii |
| --- | --- | --- | --- | --- | --- | --- | --- |
| TODO | TODO | TODO | TODO | TODO | TODO | TODO | TODO |

| Solver | Instante rulate | SAT | UNSAT | UNKNOWN | TIMEOUT | Timp mediu | Timp median |
| --- | --- | --- | --- | --- | --- | --- | --- |
| CDCL | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| DPLL | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| WalkSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
| ProbSAT | TODO | TODO | TODO | TODO | TODO | TODO | TODO |
