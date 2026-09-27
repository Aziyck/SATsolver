# Analiza algoritmică a aplicației SAT Solver

## Introducere

Acest document analizează partea algoritmică a aplicației din proiectul `SATsolver`, pe baza codului activ al produsului, nu pe baza unor presupuneri teoretice externe. Au fost urmărite în special modulele din `app.py`, `sat_core/`, `solvers/`, `problems/` și `utils/`.

Aplicația este o interfață desktop Tkinter pentru:

1. generarea de instanțe SAT sau de probleme reduse la SAT;
2. rezolvarea lor cu mai mulți solvers;
3. decodarea soluțiilor în forma problemei originale;
4. benchmark comparativ între algoritmi și instanțe.

Din punct de vedere teoretic, proiectul este relevant pentru tema `P vs NP` deoarece:

1. SAT este problema centrală asupra căreia operează aplicația;
2. mai multe probleme clasice sunt transformate în formule CNF;
3. aplicația separă clar ideea de `căutare` de ideea de `verificare`;
4. sunt implementate atât algoritmi exacți, cât și metode euristice sau incomplete.

---

## 1. Rezumatul aplicației

### 1.1 Ce face aplicația

Aplicația primește instanțe din mai multe familii de probleme:

1. Sudoku;
2. Graph Coloring;
3. N-Queens;
4. Random 3-SAT;
5. Hamiltonian Path;
6. Independent Set;
7. Clique;
8. DIMACS/CNF introdus direct.

Fiecare dintre aceste probleme este convertită într-o formulă booleană în formă normală conjunctivă, apoi formula este dată către unul dintre solverele SAT implementate:

1. `CDCL`;
2. `DPLL`;
3. `WalkSAT`.

În final, o atribuire satisfăcătoare este:

1. păstrată ca mapare `variabilă -> valoare booleană`;
2. decodificată în soluția problemei originale;
3. afișată în interfață și în benchmark-uri.

### 1.2 Fluxul principal

Fluxul real al aplicației este:

```text
UI Tkinter
-> snapshot parametri problemă
-> problems/* construiesc ProblemInstance
-> formula CNF (list[list[int]])
-> sat_core/solver_runner.py
-> solvers/{cdcl,dpll,walksat}.py
-> SolveResult
-> decoder specific problemei
-> afișare/benchmark/export
```

### 1.3 Unde este implementată logica principală

| Zonă | Rol |
|---|---|
| `app.py` | interfață, selectare solver, parametri, export, benchmark |
| `problems/` | reduceri ale problemelor la SAT |
| `solvers/` | algoritmi SAT și euristici |
| `sat_core/solver_runner.py` | orchestratrea solverelor și normalizarea opțiunilor |
| `sat_core/benchmark.py` | generare de instanțe experimentale și evaluare comparativă |
| `utils/` | codificări de variabile, grafuri, Sudoku, funcții auxiliare |

---

## 2. Algoritmi principali identificați

## 2.1 DPLL

- Unde apare în cod:
  - `solvers/dpll.py`, funcția `dpll`
  - `sat_core/solver_runner.py`, funcția `solve_clauses` apelează DPLL prin interfața comună de solver
- Rol în aplicație:
  - solver SAT exact, folosit ca bază clasică și termen de comparație.
- Explicație teoretică:
  - DPLL este un algoritm complet de satisfiabilitate pentru formule CNF. El combină:
    1. propagare unitară;
    2. alegerea unei variabile de decizie;
    3. ramificare pe `True/False`;
    4. backtracking la conflict.
  - Dacă există model, îl găsește; dacă nu există, poate demonstra `UNSAT`.
- Explicație practică:
  - În `solvers/dpll.py:83-281`, solverul:
    1. propagă clauzele unitare;
    2. alege o variabilă;
    3. încearcă întâi o ramură, apoi cealaltă;
    4. simplifică formula prin eliminarea clauzelor satisfăcute și a literalilor falși;
    5. revine recursiv când apare conflict.
- Complexitate:
  - în cel mai rău caz, exponențială, aproximativ `O(2^n)`;
  - propagarea unitară introduce cost suplimentar dependent de numărul de clauze și de lungimea lor.
- Intrări și ieșiri:
  - intrare: listă de clauze CNF `list[list[int]]`;
  - ieșire: dicționar `dict[int, bool]` dacă formula este satisfiabilă, altfel `None`.
- Exemplu simplu:
  - Formula `(x1) ∧ (¬x1 ∨ x2)`.
  - Propagarea unitară forțează `x1 = True`.
  - A doua clauză devine `(x2)`, deci `x2 = True`.
  - Nu mai rămân clauze nesatisfăcute, deci formula este `SAT`.
- Tip:
  - algoritm exact.

### Observații tehnice importante

1. Propagarea unitară este implementată direct în `solvers/dpll.py`, pentru ca solverul activ să fie autonom.
2. DPLL folosește implicit o alegere de variabilă orientată spre clauze mici, fără un modul separat de euristici expus în UI.
3. Solverul colectează și statistici: decizii, propagări, conflicte, timp (`solvers/dpll.py`).

---

## 2.2 Unit Propagation

- Unde apare în cod:
  - `solvers/dpll.py`, funcția internă `_unit_propagate`
  - folosită direct în solverul DPLL activ
- Rol în aplicație:
  - reduce formula și deduce forțări logice înainte de ramificare.
- Explicație teoretică:
  - dacă o clauză are un singur literal neeliminat, acel literal trebuie să fie adevărat pentru ca formula să poată rămâne satisfiabilă.
- Explicație practică:
  - codul caută clauze de lungime `1`, atribuie literalul corespunzător și:
    1. elimină clauzele satisfăcute;
    2. scoate negația literalului din celelalte clauze;
    3. detectează conflictul dacă apare clauza vidă.
- Complexitate:
  - implementarea este iterativă și rescanează formula; în practică poate ajunge aproximativ la `O(k * m * l)` pentru `k` propagări, `m` clauze, `l` lungime medie.
- Intrări și ieșiri:
  - intrare: CNF și atribuire parțială;
  - ieșire: formula simplificată și atribuirea extinsă sau `None` la conflict.
- Exemplu simplu:
  - `(x1) ∧ (¬x1 ∨ x3) ∧ (¬x3 ∨ x4)`.
  - `x1=True`, apoi `x3=True`, apoi `x4=True`.
- Tip:
  - optimizare logică și regulă exactă de inferență.

---

## 2.3 CDCL

- Unde apare în cod:
  - `solvers/cdcl.py`, funcția `cdcl`
  - orchestrat prin `sat_core/solver_runner.py:63-82`
- Rol în aplicație:
  - solverul SAT principal și cel mai avansat din proiect.
- Explicație teoretică:
  - CDCL extinde DPLL prin:
    1. propagare eficientă;
    2. analiză de conflict;
    3. învățare de clauze;
    4. backjumping necronologic;
    5. activitate pentru variabile;
    6. eventual restarts.
  - Este paradigma dominantă în solverele SAT moderne complete.
- Explicație practică:
  - Implementarea din `solvers/cdcl.py:106-749` are toate blocurile esențiale:
    1. normalizarea formulei;
    2. stocarea asignărilor pe niveluri de decizie;
    3. watched literals pentru propagare;
    4. First-UIP conflict analysis;
    5. clauze învățate cu scor LBD;
    6. ștergere controlată a clauzelor învățate;
    7. euristici multiple de branch;
    8. phase selection;
    9. restart opțional.
- Complexitate:
  - teoretic tot exponențială în cel mai rău caz;
  - practic mult mai eficient decât DPLL brut datorită învățării și propagării eficiente.
- Intrări și ieșiri:
  - intrare: formulă CNF și opțiuni de solver;
  - ieșire: model boolean, `None` pentru `UNSAT`, sau `UNKNOWN` dacă este impus `max_conflicts`.
- Exemplu simplu:
  - Dacă o secvență de decizii produce conflict, solverul nu doar revine la ultima decizie, ci deduce o clauză nouă care blochează tiparul de conflict și sare la nivelul relevant.
- Tip:
  - algoritm exact.

### Componente interne ale CDCL

#### a) Normalizarea formulei

- Unde apare:
  - `solvers/cdcl.py:20-56`
- Rol:
  - elimină duplicatele, ignoră tautologiile, detectează clauza vidă.
- Tip:
  - preprocesare și verificare logică.

#### b) Watched Literals

- Unde apare:
  - `watch_clause`, `attach_clause`, `propagate` în `solvers/cdcl.py:316-435`
- Explicație teoretică:
  - fiecare clauză urmărește doi literali; la schimbarea unei valori, nu mai este nevoie să fie rescannată întreaga formulă.
- Explicație practică:
  - `watches` este un dicționar de la literal la lista clauzelor care îl urmăresc.
- Complexitate:
  - reduce foarte mult costul propagării în practică; nu schimbă însă limita de complexitate în cel mai rău caz.
- Tip:
  - optimizare structurală.

#### c) Conflict Analysis First-UIP

- Unde apare:
  - `analyse_conflict` în `solvers/cdcl.py:452-519`
- Explicație teoretică:
  - conflictul este analizat în graful de implicație până se obține primul punct unic de implicație.
- Explicație practică:
  - solverul rezolvă succesiv clauza de conflict cu motivele propagărilor, până rămâne un singur literal de nivel curent.
- Tip:
  - algoritm exact intern al CDCL.

#### d) Clause Learning

- Unde apare:
  - `add_clause`, `analyse_conflict`, secvența de la `solvers/cdcl.py:689-713`
- Rol:
  - previne repetarea aceleiași cauze de conflict.
- Tip:
  - optimizare exactă.

#### e) Non-chronological Backtracking

- Unde apare:
  - `backtrack` în `solvers/cdcl.py:521-541`
- Explicație teoretică:
  - solverul nu revine neapărat la ultima decizie, ci la nivelul de backjump dedus din clauza învățată.
- Tip:
  - optimizare exactă.

#### f) Restarts

- Unde apare:
  - `solvers/cdcl.py:715-723`
- Explicație teoretică:
  - solverul revine periodic la nivelul `0`, păstrând clauzele învățate.
- Explicație practică:
  - este opțional și controlat din UI prin `restart_interval`.
- Tip:
  - strategie euristică de optimizare.

#### g) LBD pentru clauze învățate

- Unde apare:
  - `clause_lbd` în `solvers/cdcl.py:71-73`
  - utilizare la `solvers/cdcl.py:697-701`
- Explicație teoretică:
  - LBD măsoară numărul de niveluri de decizie distincte atinse de o clauză.
  - clauzele cu LBD mic tind să fie mai valoroase.
- Tip:
  - euristică de calitate a clauzelor.

#### h) Ștergerea clauzelor învățate

- Unde apare:
  - `learned_clause_delete_key`, `learned_clauses_to_delete`, `prune_learned_clauses`
  - `solvers/cdcl.py:76-103` și `551-578`
- Explicație teoretică:
  - baza de clauze învățate trebuie limitată pentru a evita degradarea performanței.
- Explicație practică:
  - sunt protejate clauzele binare, cele cu LBD mic și clauzele „locked”.
- Tip:
  - optimizare euristică de memorie și performanță.

---

## 2.4 WalkSAT

- Unde apare în cod:
  - `solvers/walksat.py`, funcția `walksat`
- Rol în aplicație:
  - solver incomplet, folosit experimental și comparativ.
- Explicație teoretică:
  - WalkSAT este algoritm de căutare locală pentru SAT.
  - pornește de la o atribuire aleatoare și modifică variabile din clauze nesatisfăcute, fie aleator, fie „greedy”.
  - dacă nu găsește soluție în bugetul de pași, nu poate concluziona `UNSAT`.
- Explicație practică:
  - în `solvers/walksat.py:132-280`, solverul:
    1. normalizează formula;
    2. alege o atribuire inițială random;
    3. selectează o clauză nesatisfăcută;
    4. cu probabilitatea `noise` alege o variabilă aleator din acea clauză;
    5. altfel alege variabila cu impactul estimat cel mai bun;
    6. face flip și repetă.
- Complexitate:
  - nu are garanție completă; complexitatea este controlată de `max_tries * max_flips`.
- Intrări și ieșiri:
  - intrare: CNF și parametri `max_tries`, `max_flips`, `noise`;
  - ieșire: model dacă găsește unul, altfel `None` cu status `UNKNOWN`.
- Exemplu simplu:
  - Dacă o clauză `(x1 ∨ ¬x2 ∨ x3)` este nesatisfăcută, algoritmul alege una dintre variabile și îi inversează valoarea pentru a reduce numărul clauzelor nesatisfăcute.
- Tip:
  - euristică incompletă de căutare locală.

### Structura auxiliară a WalkSAT

- `solvers/walksat.py:41-130`, clasa `_UnsatisfiedTracker`
- Rol:
  - urmărește incremental clauzele nesatisfăcute și efectul unui flip.
- Semnificație:
  - este o optimizare importantă; evită recalcularea completă a tuturor clauzelor după fiecare flip.

---

## 2.5 Reducerea Sudoku la SAT

- Unde apare în cod:
  - `problems/sudoku.py:47-64`
  - `utils/sudoku_general.py:38-107`
- Rol în aplicație:
  - transformă un puzzle Sudoku într-o formulă CNF echisatisfiabilă.
- Explicație teoretică:
  - se introduce o variabilă booleană `X(r,c,v)` cu sensul „în celula `(r,c)` apare valoarea `v`”.
  - apoi se exprimă prin clauze:
    1. fiecare celulă are cel puțin o valoare;
    2. fiecare celulă are cel mult o valoare;
    3. fiecare valoare apare cel mult o dată pe rând;
    4. fiecare valoare apare cel mult o dată pe coloană;
    5. fiecare valoare apare cel mult o dată pe subbloc;
    6. indiciile inițiale sunt clauze unitare.
- Explicație practică:
  - `generate_sudoku_clauses` construiește exact aceste familii de constrângeri.
- Complexitate:
  - numărul de variabile este `n^3`;
  - numărul de clauze este polinomial în `n`, dar mare; pentru implementarea dată predomină termenii de ordin `O(n^4)` și `O(n^5)` în construcția restricțiilor mutual exclusive.
- Intrări și ieșiri:
  - intrare: grilă `n x n` cu `0` pentru necunoscute;
  - ieșire: `ProblemInstance` ce conține clauzele CNF și decodorul.
- Exemplu simplu:
  - dacă în celula `(1,1)` se află deja `3`, se adaugă clauza unitară `[X(1,1,3)]`.
- Tip:
  - reducere exactă la SAT.

---

## 2.6 Reducerea Graph Coloring la SAT

- Unde apare în cod:
  - `problems/graph_coloring.py:63-77`
  - `utils/graph_utils.py`, `generate_coloring_clauses`
- Rol în aplicație:
  - decide dacă un graf este `k-colorabil`.
- Explicație teoretică:
  - variabila `X(v,c)` înseamnă „nodul `v` primește culoarea `c`”.
  - constrângerile sunt:
    1. fiecare nod are cel puțin o culoare;
    2. fiecare nod are cel mult o culoare;
    3. două noduri adiacente nu au aceeași culoare.
- Explicație practică:
  - `generate_coloring_clauses` implementează exact aceste trei familii de clauze.
- Complexitate:
  - variabile: `O(|V| * k)`;
  - clauze: `O(|V| * k^2 + |E| * k)`.
- Intrări și ieșiri:
  - intrare: graf neorientat și număr de culori `k`;
  - ieșire: CNF și decodare în mapare `nod -> culoare`.
- Exemplu simplu:
  - pentru muchia `(1,2)` și culoarea `red`, se adaugă `¬X(1,red) ∨ ¬X(2,red)`.
- Tip:
  - reducere exactă la SAT.

---

## 2.7 Reducerea N-Queens la SAT

- Unde apare în cod:
  - `problems/n_queens.py:28-59`
- Rol în aplicație:
  - găsește amplasarea a `n` regine fără atac reciproc.
- Explicație teoretică:
  - variabila `X(r,c)` înseamnă „există regină pe poziția `(r,c)`”.
  - constrângerile impun:
    1. exact o regină pe fiecare rând;
    2. cel mult o regină pe fiecare coloană;
    3. cel mult o regină pe fiecare diagonală.
- Explicație practică:
  - codul adaugă clauze de tip „at least one” pe rând și clauze binare de excludere pentru coloane și diagonale.
- Complexitate:
  - variabile: `n^2`;
  - clauze: aproximativ `O(n^3)` pentru această construcție.
- Intrări și ieșiri:
  - intrare: dimensiunea tablei;
  - ieșire: CNF și reprezentare a tablei soluție.
- Exemplu simplu:
  - pe o tablă `4x4`, clauza `[X(1,1), X(1,2), X(1,3), X(1,4)]` impune o regină pe rândul 1.
- Tip:
  - reducere exactă la SAT.

---

## 2.8 Reducerea Hamiltonian Path la SAT

- Unde apare în cod:
  - `problems/hamiltonian_path.py:31-73`
- Rol în aplicație:
  - decide dacă graful are un drum care trece exact o dată prin fiecare nod.
- Explicație teoretică:
  - variabila `X(p,v)` înseamnă „nodul `v` apare pe poziția `p` în drum”.
  - constrângerile impun:
    1. fiecare poziție are exact un nod;
    2. fiecare nod apare exact o dată;
    3. două poziții consecutive nu pot conține noduri neadiacente.
- Explicație practică:
  - ultima categorie de clauze se construiește pentru toate perechile de noduri fără muchie.
- Complexitate:
  - variabile: `n^2`;
  - clauze: aproximativ `O(n^3 + n^2 + n * non_edges)`, adică în cel mai rău caz `O(n^4)`.
- Intrări și ieșiri:
  - intrare: graf neorientat;
  - ieșire: CNF și un drum decodificat ca listă de noduri.
- Exemplu simplu:
  - dacă `2` și `4` nu sunt adiacente, atunci `¬X(3,2) ∨ ¬X(4,4)` interzice apariția lor consecutivă.
- Tip:
  - reducere exactă la SAT.

---

## 2.9 Reducerea Independent Set la SAT

- Unde apare în cod:
  - `problems/independent_set.py:29-73`
- Rol în aplicație:
  - decide existența unei mulțimi independente de mărime `k`.
- Explicație teoretică:
  - variabila `X(s,v)` înseamnă „nodul `v` ocupă slotul `s` din selecție”.
  - constrângerile impun:
    1. fiecare slot selectează un nod;
    2. același slot nu poate selecta două noduri;
    3. același nod nu poate ocupa două sloturi;
    4. două noduri adiacente nu pot fi alese simultan.
- Explicație practică:
  - este o codificare cu sloturi, convenabilă pentru a impune cardinalitatea exactă `k`.
- Complexitate:
  - variabile: `k * n`;
  - clauze: aproximativ `O(k*n^2 + k^2*n + k^2*|E|)`.
- Intrări și ieșiri:
  - intrare: graf și ținta `k`;
  - ieșire: CNF și lista nodurilor selectate.
- Exemplu simplu:
  - pentru muchia `(u,v)`, clauza `¬X(s1,u) ∨ ¬X(s2,v)` interzice selectarea simultană în orice două sloturi.
- Tip:
  - reducere exactă la SAT.

---

## 2.10 Reducerea Clique la SAT

- Unde apare în cod:
  - `problems/clique.py:29-76`
- Rol în aplicație:
  - decide existența unei clique de mărime `k`.
- Explicație teoretică:
  - variabila `X(s,v)` înseamnă „nodul `v` este pus în slotul `s` al cliquei”.
  - constrângerile sunt similare cu Independent Set, dar condiția structurală este inversă:
    - dacă două noduri nu sunt adiacente, ele nu pot fi alese simultan.
- Explicație practică:
  - codul construiește explicit complementul relației de adiacență prin `adjacency`.
- Complexitate:
  - variabile: `k * n`;
  - clauze: aproximativ `O(k*n^2 + k^2*n + k^2*|non_edges|)`.
- Intrări și ieșiri:
  - intrare: graf și `k`;
  - ieșire: CNF și lista nodurilor selectate.
- Exemplu simplu:
  - dacă `u` și `v` nu au muchie, se adaugă `¬X(s1,u) ∨ ¬X(s2,v)`.
- Tip:
  - reducere exactă la SAT.

---

## 2.11 Generarea Random 3-SAT

- Unde apare în cod:
  - `problems/random_3sat.py:45-123`
- Rol în aplicație:
  - produce instanțe experimentale SAT/UNSAT pentru comparații.
- Explicație teoretică:
  - o formulă 3-SAT are clauze de exact 3 literali.
  - aplicația suportă:
    1. `Planted SAT`;
    2. `Forced UNSAT`;
    3. `Random`, cu eventuală alegere probabilistică între cele două.
- Explicație practică:
  - `Planted SAT`:
    - se generează mai întâi o atribuire ascunsă;
    - se acceptă doar clauzele satisfăcute de acea atribuire.
  - `Forced UNSAT`:
    - se selectează 3 variabile;
    - se adaugă toate cele 8 combinații posibile de semne;
    - rezultatul este imposibil de satisfăcut simultan.
- Complexitate:
  - generarea este aproximativ liniară în numărul de clauze cerut, cu buclă de respingere pentru modul planted.
- Intrări și ieșiri:
  - intrare: număr de variabile, număr de clauze, seed, mod;
  - ieșire: `ProblemInstance` cu formulă 3-CNF.
- Exemplu simplu:
  - pentru variabilele `a,b,c`, setul tuturor celor 8 clauze pe combinații de semn forțează `UNSAT`.
- Tip:
  - generator de instanțe și mecanism experimental, nu solver.

---

## 3. Algoritmi auxiliari

## 3.1 Generarea de grafuri aleatoare `G(n,p)`

- Unde apare:
  - `utils/graph_utils.py`, `generate_random_graph`
- Rol:
  - generează grafuri prin model Erdős-Rényi.
- Explicație:
  - pentru fiecare pereche de noduri, muchia este introdusă independent cu probabilitatea `p`.
- Complexitate:
  - `O(n^2)`.
- Tip:
  - algoritm auxiliar de generare.

## 3.2 Generarea de grafuri cu număr exact de muchii `G(n,m)`

- Unde apare:
  - `utils/graph_utils.py`, `generate_random_graph_exact_edges`
- Rol:
  - produce instanțe controlate după numărul exact de muchii.
- Explicație:
  - se generează lista tuturor muchiilor posibile și se selectează aleator `m`.
- Complexitate:
  - generarea muchiilor posibile este `O(n^2)`.
- Tip:
  - algoritm auxiliar de generare.

## 3.3 Conversia grad mediu -> număr de muchii

- Unde apare:
  - `problems/graph_coloring.py:105-113`
  - reutilizat de problemele pe grafuri
- Rol:
  - transformă parametrul teoretic `d` în `m = round(n*d/2)`.
- Explicație:
  - într-un graf neorientat, suma gradelor este `2m`.
- Tip:
  - formulă de reducere parametrică.

## 3.4 Conversia și parsarea DIMACS

- Unde apare:
  - `sat_core/dimacs.py`
  - `problems/dimacs_problem.py`
- Rol:
  - import/export de formule CNF în format standard.
- Explicație:
  - transformă reprezentarea internă `list[list[int]]` în format textual DIMACS și invers.
- Tip:
  - infrastructură standard, nu algoritm de căutare.

## 3.5 Backtracking nativ pentru Sudoku

- Unde apare:
  - `utils/sudoku_general.py:110-163`, `solve_sudoku`
- Rol:
  - solver Sudoku direct, independent de SAT.
- Explicație:
  - caută o celulă liberă, încearcă valori valide și revine la conflict.
- Complexitate:
  - exponențială.
- Tip:
  - algoritm exact auxiliar.

---

## 4. Euristici și strategii folosite

## 4.1 Euristici de alegere a variabilei în DPLL

### Small-clause preference

- Unde apare:
  - `solvers/dpll.py`, funcția internă `_choose_variable_small_clause`
  - utilizată implicit de DPLL
- Explicație:
  - sortează clauzele după lungime și alege o variabilă dintr-o clauză mică.
- Semnificație teoretică:
  - clauzele mici sunt mai restrictive; ramificarea în jurul lor tinde să detecteze mai repede conflictele.
- Tip:
  - euristică.

## 4.2 VSIDS-like activity

- Unde apare:
  - `solvers/cdcl.py:243`, `437-450`, `594-603`
- Explicație:
  - variabilele implicate în conflicte primesc scor de activitate mai mare și sunt alese prioritar ulterior.
- Semnificație:
  - concentrează căutarea în zonele „fierbinți” ale formulei.
- Tip:
  - euristică majoră de branch în CDCL.

## 4.3 MOMS

- Unde apare:
  - `solvers/cdcl.py:614-630`
- Explicație:
  - Maximum Occurrences in clauses of Minimum Size.
  - alege variabila care apare frecvent în cele mai scurte clauze încă nerezolvate.
- Tip:
  - euristică.

## 4.4 DLIS

- Unde apare:
  - `solvers/cdcl.py:632-643`
- Explicație:
  - Dynamic Largest Individual Sum.
  - alege literalul care satisface cât mai multe clauze nerezolvate.
- Tip:
  - euristică.

## 4.5 Random branching

- Unde apare:
  - `solvers/cdcl.py:645-657`
- Rol:
  - alternativă experimentală de comparație.
- Tip:
  - euristică stocastică.

## 4.6 Phase selection

- Unde apare:
  - `solvers/cdcl.py:269-280`, `660-667`
- Variante:
  - `Positive first`;
  - `Negative first`;
  - `Polarity based`;
  - `Random`;
  - `saved phase`.
- Observație teoretică:
  - alegerea semnului literalului poate schimba drastic performanța, deși nu schimbă corectitudinea.
- Tip:
  - euristică.

## 4.7 Saved phase

- Unde apare:
  - `solvers/cdcl.py:242`, `308`, `665-666`
- Explicație:
  - solverul reîncearcă ultima polaritate folosită cu succes pentru o variabilă.
- Tip:
  - euristică de continuitate a căutării.

## 4.8 Noise în WalkSAT

- Unde apare:
  - `solvers/walksat.py:168-170`, `263-273`
- Explicație:
  - cu probabilitatea `noise`, flip-ul se face aleator; altfel, greedy.
- Semnificație:
  - echilibru între explorare și exploatare.
- Tip:
  - euristică stocastică.

## 4.9 Greedy flip score în WalkSAT

- Unde apare:
  - `solvers/walksat.py:88-107`, `266-272`
- Explicație:
  - estimează câte clauze ar rămâne nesatisfăcute după flip.
- Tip:
  - euristică locală de optimizare.

## 4.10 Planted assignment pentru generare SAT

- Unde apare:
  - `problems/random_3sat.py:77-91`
- Explicație:
  - formulele generate sunt forțate să fie satisfăcute de o atribuire ascunsă.
- Tip:
  - metodă constructivă de generare.

## 4.11 Forced UNSAT core

- Unde apare:
  - `problems/random_3sat.py:31-42`, `83-85`
- Explicație:
  - toate cele 8 combinații de semn pe aceleași 3 variabile fac formula nesatisfiabilă.
- Tip:
  - construcție logică exactă pentru generare.

---

## 5. Structuri de date importante

| Structură | Unde apare | Rol teoretic și practic |
|---|---|---|
| `list[list[int]]` pentru CNF | peste tot în `problems/`, `solvers/`, `sat_core/` | reprezentarea standard a formulei SAT |
| `dict[int, bool]` | DPLL, WalkSAT, rezultate | atribuire booleană pentru variabile |
| `Clause` | `solvers/cdcl.py:9-17` | clauză îmbogățită cu metadate pentru CDCL |
| `watches: dict[literal, list[Clause]]` | `solvers/cdcl.py:246-247` | suport pentru watched literals |
| `trail` și `trail_lim` | `solvers/cdcl.py:250-255` | stiva cronologică a asignărilor și delimitarea nivelurilor |
| `levels` | `solvers/cdcl.py:240` | nivelul de decizie al fiecărei variabile |
| `reasons` | `solvers/cdcl.py:241` | clauza care a forțat o propagare |
| `activity` | `solvers/cdcl.py:243` | scor VSIDS-like |
| `_UnsatisfiedTracker` | `solvers/walksat.py:41-130` | actualizare incrementală a clauzelor nesatisfăcute |
| `Graph = dict[int, list[int]]` | `problems/*`, `utils/graph_utils.py` | listă de adiacență pentru grafuri |
| `ProblemInstance` | `sat_core/models.py:10-37` | ambalaj unificat: CNF, metadata, decoder |
| `SolveResult` | `sat_core/models.py:40-49` | rezultat standardizat al solverului |
| `BenchmarkRow` | `sat_core/models.py:52-96` | unitate de măsurare experimentală |

---

## 6. Reguli logice și condiții de verificare

Acestea nu sunt întotdeauna „algoritmi” în sens strict, dar sunt foarte utile în partea teoretică.

## 6.1 Verificări de validitate a inputului

- Sudoku:
  - `problems/sudoku.py:9-24`
  - verifică dimensiune pătrată perfectă, valori în interval, grilă pătratică.
- Grafuri:
  - `problems/graph_coloring.py:18-35`
  - interzice self-loops, noduri în afara intervalului și normalizează lista muchiilor.
- Random 3-SAT:
  - `problems/random_3sat.py:53-67`
  - asigură condiții minime pentru modurile SAT/UNSAT.

## 6.2 Reguli CNF structurale

- Tautology elimination:
  - `solvers/cdcl.py:20-56`
  - `solvers/walksat.py:9-38`
- Duplicate literal elimination:
  - `solvers/cdcl.py:59-68`
- Empty clause detection:
  - criteriu direct pentru `UNSAT`.

## 6.3 Modele standard de constrângeri

### a) At least one

- folosit în Sudoku, Graph Coloring, N-Queens, Hamiltonian Path, Independent Set, Clique.

### b) At most one

- implementat aproape mereu prin clauze binare pe toate perechile.

### c) Exactly one

- obținut prin combinația `at least one` + `at most one`.

Acesta este unul dintre cele mai importante concepte explicabile în raport, pentru că apare repetat și unifică toate reducerile la SAT.

<!-- ## 6.4 Clamp la graf complet

- `utils/graph_utils.py`
- dacă se cer prea multe muchii, aplicația nu produce eroare, ci limitează la numărul maxim posibil.
- Tip:
  - regulă practică de robustețe. -->

## 6.4 Cooperative cancellation / timeout / skip

- `sat_core/runtime.py`
- nu ține direct de teoria SAT, dar este o strategie importantă de control al execuției în aplicație.

---

## 7. Legătura cu partea teoretică a lucrării

## 7.1 Legătura cu P vs NP

Aplicația ilustrează foarte bine diferența dintre:

1. `căutarea` unei soluții;
2. `verificarea` unei soluții.

În SAT:

1. dacă ni se dă o atribuire, verificarea satisfacției unei formule este polinomială;
2. găsirea atribuirii este, în general, problema dificilă.

Acesta este exact tipul de diferență conceptuală care stă în centrul discuției `P vs NP`.

## 7.2 Legătura cu SAT și 3-SAT

Aplicația are:

1. solveri SAT generali;
2. generator explicit pentru 3-SAT;
3. import direct DIMACS;
4. reduceri de la alte probleme la SAT.

Asta face posibilă explicarea ideii că SAT este problemă `NP-completă`, iar 3-SAT este o restricție celebră tot `NP-completă`.

## 7.3 Legătura cu reducibilitatea polinomială

Modulele din `problems/` sunt exemple concrete de reducere polinomială:

1. `Graph Coloring -> SAT`;
2. `Hamiltonian Path -> SAT`;
3. `Independent Set -> SAT`;
4. `Clique -> SAT`;
5. `Sudoku -> SAT`;
6. `N-Queens -> SAT`.

În raport poți sublinia că aplicația nu doar „rezolvă SAT”, ci și demonstrează practic ideea de transformare a unor probleme combinatoriale în SAT.

## 7.4 Legătura cu căutarea combinatorială

Proiectul conține mai multe paradigme:

1. backtracking clasic;
2. branch-and-search prin DPLL;
3. conflict-driven learning prin CDCL;
4. local search prin WalkSAT.

Această diversitate este foarte valoroasă pentru partea teoretică, fiindcă poți compara:

1. algoritmi exacți versus incompleți;
2. metode sistematice versus stocastice;
3. deducție logică versus explorare euristică.

---

## 8. Ce poți scrie în raport

## 8.1 Formulare recomandată pentru partea teoretică

Poți structura capitolul teoretic astfel:

### 1. SAT și rolul său în complexitate

Explică:

1. ce este o formulă CNF;
2. ce este satisfiabilitatea;
3. de ce verificarea este ușoară dacă soluția este dată;
4. de ce căutarea este dificilă în general.

### 2. Reduceri la SAT

Prezintă separat:

1. Sudoku;
2. Graph Coloring;
3. Hamiltonian Path;
4. Independent Set;
5. Clique;
6. N-Queens.

Accentul ar trebui pus pe variabilele booleene introduse și pe tiparele de clauze.

### 3. Algoritmi de rezolvare

Compară:

1. DPLL;
2. CDCL;
3. WalkSAT.

Poți evidenția:

1. caracterul complet sau incomplet;
2. folosirea propagării;
3. rolul euristicilor;
4. impactul în practică.

### 4. Euristici

Explică:

1. alegerea variabilei;
2. alegerea polarității;
3. restarts;
4. clause learning;
5. VSIDS, MOMS, DLIS;
6. random noise în WalkSAT.

### 5. Evaluare experimentală

Leagă benchmark-ul din aplicație de:

1. densitatea grafurilor;
2. mărimea formulelor;
3. raportul clauze/variabile pentru 3-SAT;
4. influența euristicilor asupra performanței.

## 8.2 Idei de formulări academice gata de adaptat

> Aplicația folosește SAT ca limbaj universal de modelare pentru probleme combinatoriale. Fiecare instanță este transformată într-o formulă CNF, iar satisfiabilitatea formulei este echivalentă cu existența unei soluții pentru problema inițială.

> Solverul DPLL reprezintă varianta clasică de căutare sistematică prin ramificare și revenire, în timp ce solverul CDCL extinde acest model prin învățare din conflicte, backjumping necronologic și euristici moderne de selecție.

> WalkSAT ilustrează o paradigmă diferită, bazată pe căutare locală și pe mutări stocastice, fiind eficient în unele cazuri satisfiabile, dar fără garanția demonstrării nesatisfiabilității.

> Reducerile implementate pentru Graph Coloring, Hamiltonian Path, Independent Set și Clique evidențiază în practică ideea de reducere polinomială, esențială în teoria NP-completitudinii.

---

## 9. Sugestii de îmbunătățire a aplicației

Aceste sugestii nu descriu comportament existent, ci extensii posibile.

1. Adăugarea unei secțiuni explicite de verificare formală a soluției decodate pentru fiecare problemă, nu doar a formulei SAT.
2. Introducerea unei reduceri explicite `3-SAT -> Clique` sau `3-SAT -> Independent Set` pentru a lega și mai clar teoria NP-completitudinii de cod.
3. Implementarea unor preprocesări suplimentare:
   - pure literal elimination;
   - subsumption;
   - clause strengthening.
4. Adăugarea unei secțiuni vizuale despre graful de implicație din CDCL și clauzele învățate.
5. Măsurarea memoriei, nu doar a timpului, în benchmark.
6. Adăugarea unor experimente pe pragul de fază pentru Random 3-SAT în jurul raportului clauze/variabile cunoscut din literatură.

---

## 10. Concluzie

Aplicația este mai mult decât o interfață pentru SAT. Ea reprezintă o mică platformă educațională și experimentală pentru:

1. modelarea problemelor combinatoriale;
2. reducerea acestora la SAT;
3. compararea mai multor paradigme algoritmice;
4. observarea practică a diferenței dintre rezolvare exactă și euristică.

Din analiza codului rezultă că nucleul teoretic al proiectului este format din:

1. reduceri exacte la SAT;
2. algoritmi exacți `DPLL` și `CDCL`;
3. algoritm euristic incomplet `WalkSAT`;
4. euristici moderne pentru branching, phase selection, learning și restart;
5. structuri de date specializate pentru propagare și analiză de conflict.

Pentru o lucrare despre `P vs NP`, acest proiect este foarte potrivit, deoarece conectează direct:

1. teoria SAT și NP-completitudinea;
2. transformarea problemelor clasice în CNF;
3. diferența dintre verificare și căutare;
4. impactul real al euristicilor asupra unor probleme teoretic dificile.

---

## Anexă: hartă rapidă a algoritmilor

| Categorie | Elemente identificate |
|---|---|
| Algoritmi principali | DPLL, CDCL, WalkSAT |
| Algoritmi auxiliari | unit propagation, generare grafuri `G(n,p)` și `G(n,m)`, backtracking Sudoku, backtracking colorare |
| Reduceri la SAT | Sudoku, Graph Coloring, N-Queens, Hamiltonian Path, Independent Set, Clique |
| Euristici | small-clause, most frequent, VSIDS-like, MOMS, DLIS, saved phase, polarity based, random phase, restart, greedy flip, noise, MRV-like |
| Optimizări | watched literals, clause learning, non-chronological backtracking, learned clause pruning, incremental unsatisfied tracking |
| Reguli de verificare | validarea inputului, eliminarea tautologiilor, detectarea clauzei vide, constrângeri exactly-one, clamp la graf complet |

