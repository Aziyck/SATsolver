# Capitolul 2. Proiectarea și implementarea aplicației SAT Solver

Acest capitol descrie partea practică a proiectului: o aplicație desktop pentru generarea, rezolvarea și compararea unor instanțe SAT. Textul este construit pe baza structurii actuale a repository-ului și urmărește implementarea din `app.py`, `sat_core/`, `problems/`, `solvers/`, `utils/` și `docs/visualisations/`.

Partea teoretică a lucrării prezintă problemele P vs NP, SAT, 3-SAT, reducerile polinomiale și familiile de algoritmi SAT. În această parte aplicativă accentul cade pe felul în care aceste concepte sunt transformate într-un program concret: problemele sunt codificate în CNF, formulele sunt transmise către solvere, iar rezultatele sunt decodificate și afișate în interfață.

## 2.1 Scopul aplicației și cerințele funcționale

Scopul aplicației este de a oferi un mediu experimental pentru lucrul cu formule SAT și cu probleme clasice reduse la SAT. Aplicația permite utilizatorului să construiască instanțe de probleme, să vizualizeze formula CNF generată, să aleagă un solver și să compare comportamentul algoritmilor pe aceeași familie de instanțe.

Funcționalitățile principale implementate sunt:

1. construirea de instanțe SAT pentru probleme precum Sudoku, N-Queens, Graph Coloring, Hamiltonian Path, Clique, Independent Set și Random 3-SAT;
2. introducerea sau încărcarea formulelor în format DIMACS/CNF;
3. rezolvarea formulelor cu DPLL, CDCL sau WalkSAT;
4. folosirea strategiei ProbSAT ca mod de selecție în solverul WalkSAT;
5. afișarea rezultatului brut SAT și a soluției decodificate pentru problema inițială;
6. generarea, salvarea și încărcarea fișierelor CNF;
7. rularea de benchmark-uri cu repetări, timeout, seed și opțiuni de solver;
8. exportul rezultatelor de benchmark în CSV și exportul graficelor;
9. previzualizarea grafurilor pentru problemele bazate pe grafuri.

[Figura 1: Interfața principală a aplicației SAT Solver]

Aplicația are două zone majore de lucru:

- fila `Solve`, destinată unei instanțe individuale;
- fila `Benchmarks`, destinată rulării sistematice a mai multor instanțe și solvere.

În plus, aplicația include vizualizări educaționale HTML pentru DPLL, CDCL și WalkSAT în `docs/visualisations/dpll/index.html`, `docs/visualisations/cdcl/index.html` și `docs/visualisations/walksat/index.html`. Aceste fișiere pot fi folosite în raport pentru a ilustra intuitiv pașii algoritmilor.

## 2.2 Arhitectura generală a aplicației

Aplicația este organizată pe straturi. Această separare este importantă deoarece interfața grafică nu conține direct logica de reducere la SAT sau implementarea solverelor.

Rolurile principale ale modulelor sunt:

| Zonă | Rol în aplicație |
|---|---|
| `app.py` | interfața Tkinter, formularele de input, afișarea CNF, afișarea rezultatului, joburile, exporturile și graficele |
| `problems/` | encodere pentru transformarea problemelor în `ProblemInstance` |
| `sat_core/models.py` | modelele comune `ProblemInstance`, `SolveResult` și `BenchmarkRow` |
| `sat_core/solver_runner.py` | punctul comun de apelare a solverelor și normalizarea rezultatului |
| `sat_core/process_workers.py` | worker processes pentru generare CNF, solve și benchmark |
| `sat_core/runtime.py` | evenimente de rulare, progres, anulare, timeout și skip |
| `sat_core/benchmark.py` | generarea seriilor de benchmark și exportul în CSV |
| `sat_core/dimacs.py` | parsare, formatare, încărcare și salvare DIMACS/CNF |
| `solvers/` | implementările DPLL, CDCL și WalkSAT |
| `utils/` | funcții auxiliare pentru variabile Sudoku, colorare, grafuri și generarea clauzelor |

Fluxul general poate fi descris astfel:

```text
Input UI
-> encoder din problems/
-> ProblemInstance
-> sat_core/solver_runner.py
-> solver din solvers/
-> SolveResult
-> decoder specific problemei
-> afișare, export sau benchmark
```

Modelul central este `ProblemInstance` din `sat_core/models.py`. Acesta conține numele instanței, tipul problemei, lista de clauze CNF, metadate și o funcție opțională de decodare. Prin acest model, Sudoku, N-Queens sau Clique ajung să fie tratate uniform de solverele SAT.

`SolveResult`, tot din `sat_core/models.py`, normalizează rezultatul unui solver: status, timp, soluție, statistici, număr de clauze și număr de variabile. Pentru benchmark, `BenchmarkRow` păstrează în plus informații precum repeat, solver, timp, conflicte, decizii, propagări, opțiuni de solver și metadate ale problemei.

Lucrările mai costisitoare nu sunt executate direct în thread-ul Tkinter. `sat_core/process_workers.py` definește procese separate pentru generare CNF, solve și benchmark. Comunicarea cu UI se face prin evenimente, iar `sat_core/runtime.py` oferă mecanismele pentru progres, anulare și timeout. Astfel, fereastra rămâne utilizabilă în timpul execuțiilor mai lungi.

[Figura 2: Schema arhitecturală a aplicației]

## 2.3 Reprezentarea formulelor CNF

În aplicație, o formulă CNF este reprezentată ca o listă de clauze, iar fiecare clauză este o listă de literali întregi:

```python
[[1, -2], [2, 3], [-1]]
```

Interpretarea este standard:

- literalul pozitiv `x` înseamnă că variabila booleană `x` apare pozitiv;
- literalul negativ `-x` înseamnă negația variabilei `x`;
- o clauză este satisfăcută dacă cel puțin un literal este adevărat;
- formula este satisfăcută dacă toate clauzele sunt satisfăcute.

Formatarea și parsarea DIMACS sunt implementate în `sat_core/dimacs.py`. Funcția `clauses_to_dimacs` transformă lista internă de clauze în text DIMACS, `parse_dimacs_text` citește textul DIMACS, iar `save_dimacs` și `load_dimacs` lucrează cu fișiere. Acest strat este folosit de UI pentru salvarea CNF-urilor generate și pentru încărcarea problemelor introduse de utilizator.

Exemplu de reprezentare DIMACS:

```text
c exemplu minimal
p cnf 3 2
1 -2 0
2 3 0
```

În aplicație, clauzele generate pot fi vizualizate în fila `Solve`, salvate în `input/generated/` sau exportate din detaliile unui benchmark.

## 2.4 Codificarea problemelor în SAT

Fiecare problemă este transformată într-un obiect `ProblemInstance`. Encoderele nu apelează interfața Tkinter și nu cunosc detalii despre solvere. Ele produc doar clauze CNF, metadate și, când este posibil, un decoder al soluției.

### 2.4.1 Sudoku

Codificarea Sudoku este implementată în `problems/sudoku.py` și `utils/sudoku_general.py`. Funcția `sudoku_problem` validează grila, generează clauzele și returnează un `ProblemInstance`.

Variabila SAT pentru Sudoku este produsă de `sudoku_var(r, c, v)` din `utils/general_utils.py`:

```python
sudoku_var(r, c, v) = r * 10000 + c * 100 + v
```

Semnificația variabilei este: în linia `r`, coloana `c`, valoarea `v` este plasată în celulă.

Clauzele generate în `generate_sudoku_clauses` acoperă următoarele constrângeri:

1. fiecare celulă are cel puțin o valoare;
2. fiecare celulă are cel mult o valoare;
3. aceeași valoare nu apare de două ori pe aceeași linie;
4. aceeași valoare nu apare de două ori pe aceeași coloană;
5. aceeași valoare nu apare de două ori în același bloc;
6. valorile inițiale din grilă sunt introduse ca unit clauses.

Decoderul `decode_sudoku` transformă asignarea booleană întoarsă de solver într-o grilă numerică. În UI, utilizatorul poate selecta dimensiuni precum `4`, `9`, `16` sau `25`, conform constantelor din `app.py`.

[Figura 3: Exemplu de input Sudoku și CNF generat]

### 2.4.2 N-Queens

Problema N-Queens este implementată în `problems/n_queens.py`. Variabila SAT este:

```python
n_queens_var(row, col, size) = readable_pair_var(row, col, size)
```

Pentru valori până la 99, al doilea câmp folosește două cifre. Exemplu:
`n_queens_var(1, 1, 4) = 101`.

Aceasta reprezintă afirmația: există o regină pe linia `row` și coloana `col`.

Funcția `n_queens_problem` construiește clauze pentru:

1. cel puțin o regină pe fiecare linie;
2. cel mult o regină pe fiecare linie;
3. cel mult o regină pe fiecare coloană;
4. absența conflictelor pe diagonale.

Soluția este decodificată prin `decode_n_queens`, care întoarce atât pozițiile reginelor, cât și o reprezentare textuală a tablei cu `Q` și `.`.

### 2.4.3 Graph Coloring

Graph Coloring este implementat în `problems/graph_coloring.py`, iar funcțiile comune pentru grafuri și clauze sunt în `utils/graph_utils.py`.

Aplicația acceptă mai multe moduri de construire a grafului:

- introducere manuală de muchii;
- graf aleator `G(n,p)`, prin probabilitate de muchie;
- graf cu număr exact de muchii `G(n,m)`;
- graf pe baza gradului mediu `G(n,d)`, convertit în `m = round(n*d/2)`.

Variabila SAT este produsă prin `color_var(node, color, colors)` din `utils/general_utils.py`:

```python
color_var(node, color, colors) = readable_pair_var(node, color, colors)
```

Exemplu: `color_var(2, 3, 10) = 203`. Dacă al doilea câmp depășește 99,
lățimea se extinde automat: `color_var(2, 101, 101) = 2101`.

Semnificația variabilei este: nodul `node` are culoarea `color`.

Funcția `generate_coloring_clauses` construiește:

1. clauze care impun ca fiecare nod să primească cel puțin o culoare;
2. clauze care impun ca fiecare nod să nu primească două culori simultan;
3. clauze pentru muchii, astfel încât două noduri adiacente să nu aibă aceeași culoare.

Decoderul `decode_coloring` transformă modelul SAT într-o mapare `nod -> culoare`.

[Figura 4: Previzualizare graf pentru Graph Coloring]

### 2.4.4 Hamiltonian Path

Hamiltonian Path este implementat în `problems/hamiltonian_path.py`. Variabila SAT este:

```python
hamiltonian_var(position, node, node_count) = readable_pair_var(position, node, node_count)
```

Exemplu: `hamiltonian_var(1, 3, 10) = 103`.

Semnificația este: nodul `node` se află pe poziția `position` în drum.

Codificarea construiește:

1. pentru fiecare poziție, cel puțin un nod este ales;
2. pentru fiecare poziție, nu pot fi alese două noduri diferite;
3. fiecare nod apare cel puțin o dată în drum;
4. fiecare nod nu poate apărea pe două poziții diferite;
5. două poziții consecutive nu pot conține noduri fără muchie între ele.

Decoderul `decode_hamiltonian_path` întoarce lista nodurilor în ordinea drumului.

### 2.4.5 Clique și Independent Set

Clique este implementată în `problems/clique.py`, iar Independent Set în `problems/independent_set.py`. Cele două probleme au o structură asemănătoare: se caută o selecție de `k` noduri, reprezentată prin sloturi.

Pentru Clique:

```python
clique_var(slot, node, node_count) = readable_pair_var(slot, node, node_count)
```

Pentru Independent Set:

```python
independent_var(slot, node, node_count) = readable_pair_var(slot, node, node_count)
```

În ambele cazuri, clauzele impun:

1. fiecare slot să conțină un nod;
2. un slot să nu conțină două noduri;
3. același nod să nu fie folosit în două sloturi;
4. condiția specifică problemei:
   - pentru Clique, nodurile selectate trebuie să fie toate conectate între ele;
   - pentru Independent Set, nodurile selectate nu trebuie să aibă muchii între ele.

Aplicația permite generarea acestor probleme pe grafuri introduse manual sau generate aleator, reutilizând funcțiile din `utils/graph_utils.py`.

### 2.4.6 Random 3-SAT

Random 3-SAT este implementat în `problems/random_3sat.py`. Modulul definește trei moduri:

- `Planted SAT`, unde se generează o atribuire ascunsă și se acceptă numai clauze satisfăcute de aceasta;
- `Forced UNSAT`, unde se introduce un nucleu nesatisfiabil pe trei variabile;
- `Random`, unde se pot genera formule aleatoare sau un amestec controlat între instanțe satisfiabile și nesatisfiabile.

Fiecare clauză are trei literali, iar metadatele includ numărul de variabile, numărul de clauze, raportul clauze/variabile, seed-ul și modul selectat.

Acest generator este util în partea experimentală deoarece permite compararea solverelor pe formule apropiate de SAT clasic, nu doar pe probleme structurate precum Sudoku sau grafuri.

## 2.5 Implementarea solverelor

Solverele active sunt apelate prin `sat_core/solver_runner.py`. Lista de solvere de nivel principal este:

```python
SOLVERS = ("CDCL", "DPLL", "WalkSAT")
```

Toate solverele întorc o soluție sub forma `dict[int, bool]` sau `None`, iar când sunt apelate cu `return_stats=True`, întorc și statistici.

### 2.5.1 DPLL

DPLL este implementat în `solvers/dpll.py`. Este un solver complet: dacă formula este satisfiabilă, poate găsi un model; dacă este nesatisfiabilă, poate demonstra acest lucru prin explorarea arborelui de căutare.

Pașii principali sunt:

1. aplicarea propagării unitare prin funcția internă `_unit_propagate`;
2. detectarea conflictelor produse de clauze vide;
3. alegerea unei variabile neasignate;
4. încercarea valorilor `True` și `False`;
5. backtracking cronologic atunci când o ramură eșuează.

DPLL folosește implicit o euristică de tip small-clause, implementată în `_choose_variable_small_clause`: variabila este aleasă din cele mai scurte clauze disponibile, deoarece acestea sunt mai restrictive.

Statistici colectate: status, decizii, propagări, conflicte și timp.

### 2.5.2 CDCL

CDCL este implementat în `solvers/cdcl.py`. Acesta extinde ideea DPLL prin învățarea de clauze din conflicte și prin backjumping necronologic.

Elementele importante din implementare sunt:

- clasa `Clause`, care reține literalii și metadate pentru clauzele învățate;
- watched literals pentru propagare eficientă;
- trail și niveluri de decizie;
- analiza conflictelor de tip First-UIP;
- clauze învățate;
- calcul LBD pentru clauzele învățate;
- ștergere controlată a clauzelor învățate;
- restarturi opționale.

Aplicația expune mai multe opțiuni CDCL prin UI:

- branching: `VSIDS`, `Most frequent`, `MOMS`, `DLIS`, `Random`;
- fază inițială: `Positive first`, `Negative first`, `Polarity based`, `Random`;
- restarturi la un interval de conflicte;
- limită pentru numărul de clauze învățate;
- seed pentru alegeri random reproductibile.

Aceste opțiuni sunt citite din `app.py`, normalizate în `sat_core/solver_runner.py` și transmise către `cdcl` prin `logging_options`.

### 2.5.3 WalkSAT

WalkSAT este implementat în `solvers/walksat.py`. Spre deosebire de DPLL și CDCL, WalkSAT este incomplet: poate găsi rapid o soluție pentru formule satisfiabile, dar nu poate demonstra nesatisfiabilitatea. Dacă nu găsește o soluție în bugetul de căutare, statusul este `UNKNOWN`.

Algoritmul pornește de la o atribuire completă aleatoare și repetă:

1. identifică o clauză nesatisfăcută;
2. alege o variabilă din acea clauză;
3. schimbă valoarea variabilei;
4. actualizează incremental numărul de clauze nesatisfăcute;
5. se oprește la SAT, timeout, anulare sau epuizarea bugetului.

Implementarea folosește `_UnsatisfiedTracker`, o structură care păstrează liste de apariții, numărul de literali satisfăcuți pe clauză și lista clauzelor nesatisfăcute. Astfel, după un flip sunt actualizate doar clauzele care conțin variabila schimbată.

Opțiunile WalkSAT includ:

- `max_tries`, numărul de restarturi aleatoare;
- `max_flips`, numărul maxim de flip-uri per try;
- `noise`, probabilitatea de a alege aleator;
- `selection_mode`, strategia de alegere;
- `adaptive_noise`, ajustarea zgomotului după stagnare;
- `random_seed`, pentru reproductibilitate.

Statistici relevante: tries, flips, best_unsatisfied, best_assignment, make/break totals, final_noise și termination_reason.

### 2.5.4 ProbSAT

ProbSAT este prezent în aplicație ca strategie de selecție în solverul WalkSAT, nu ca solver separat în lista top-level. În interfață, strategia este aleasă prin `WALKSAT_STRATEGIES = ("Classic WalkSAT", "ProbSAT")` din `app.py`. În codul solverului, această alegere ajunge ca `selection_mode="probsat"` în `solvers/walksat.py`.

În modul ProbSAT, variabila de flip nu este aleasă strict greedy, ci probabilistic. Greutatea unui candidat favorizează variabilele care repară multe clauze și strică puține clauze deja satisfăcute:

```text
weight = (make + 1) / ((break + 1) ^ 2)
```

Această strategie păstrează caracterul stochastic al local search-ului, dar orientează căutarea spre mutări promițătoare.

### Observații tehnice

- `sat_core/solver_runner.py` expune solverele top-level `CDCL`, `DPLL` și `WalkSAT`.
- ProbSAT este selectat ca opțiune internă a WalkSAT prin `selection_mode="probsat"`.
- WalkSAT și ProbSAT nu produc demonstrații de nesatisfiabilitate; un rezultat `UNKNOWN` înseamnă doar că nu s-a găsit model în bugetul alocat.
- Nu există rezultate de benchmark incluse direct în cod; acestea trebuie colectate experimental și completate manual în tabele.

## 2.6 Interfața aplicației și fluxul de utilizare

Interfața este implementată în `app.py` cu Tkinter. Fila `Solve` este orientată spre rezolvarea unei singure instanțe:

1. utilizatorul alege tipul problemei;
2. completează parametrii;
3. generează CNF-ul;
4. selectează solverul și opțiunile;
5. rulează solve;
6. inspectează rezultatul, soluția decodificată și metadatele.

[Figura 5: Fluxul de utilizare în fila Solve]

Pentru problemele pe grafuri, aplicația afișează o previzualizare a grafului și permite exportul imaginii sau al datelor grafului. Pentru formule DIMACS, utilizatorul poate lipi textul sau încărca un fișier.

Fila `Benchmarks` permite rularea seriilor de teste. Utilizatorul selectează familia de probleme, parametrii de sweep, solverele, numărul de repetări, timeout-ul și opțiunile solverelor. Rezultatele sunt afișate într-un tabel și într-un grafic Matplotlib. Exportul CSV este realizat prin `write_benchmark_csv` din `sat_core/benchmark.py`.

[Figura 6: Fila Benchmarks cu tabel și grafic]

Aplicația folosește joburi pentru solve, generate și benchmark. Panourile de joburi permit anularea execuțiilor, selectarea rezultatelor finalizate și reîncărcarea detaliilor.

## 2.7 Benchmark și metodologia testării

Benchmark-urile sunt implementate în `sat_core/benchmark.py`. Acest modul conține funcții de sweep pentru:

- Sudoku;
- N-Queens;
- Random 3-SAT;
- Graph Coloring;
- Hamiltonian Path;
- Independent Set;
- Clique;
- Graph Suite.

Metodologia recomandată este:

1. se fixează un set de probleme și parametri;
2. se rulează aceleași instanțe cu mai multe solvere;
3. se folosește un seed pentru generare reproductibilă;
4. se păstrează același timeout pentru toate solverele;
5. se repetă fiecare configurație de mai multe ori;
6. se exportă rezultatele în CSV;
7. se raportează atât statusul, cât și timpul și statisticile interne.

Pentru comparații corecte, WalkSAT și ProbSAT trebuie interpretate diferit de DPLL/CDCL. DPLL și CDCL sunt complete, în timp ce WalkSAT/ProbSAT sunt incomplete. Prin urmare, `UNKNOWN` nu este echivalent cu `UNSAT`.

Exemplu de tabel pentru metodologia experimentală:

| Familie | Parametri | Solvere | Repetări | Timeout | Seed |
|---|---|---|---:|---:|---:|
| Sudoku | TODO | CDCL, DPLL | TODO | TODO | TODO |
| Random 3-SAT | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |
| Graph Coloring | TODO | CDCL, DPLL, WalkSAT, ProbSAT | TODO | TODO | TODO |

## 2.8 Rezultate experimentale

Rezultatele experimentale trebuie completate după rularea benchmark-urilor în aplicație. Nu se introduc valori numerice fără execuții reale.

Tabel propus pentru rezultate:

| Instanță | Solver | Status | Timp mediu (s) | Conflicte | Decizii | Propagări | Observații |
|---|---|---|---:|---:|---:|---:|---|
| TODO | CDCL | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | DPLL | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | WalkSAT | TODO | TODO | TODO | TODO | TODO | TODO |
| TODO | ProbSAT | TODO | TODO | TODO | TODO | TODO | TODO |

[Figura 7: Grafic comparativ al timpilor de execuție]

În interpretarea rezultatelor se recomandă discutarea următoarelor aspecte:

- diferența dintre solvere complete și incomplete;
- impactul clauzelor învățate în CDCL;
- cazurile în care DPLL devine mai lent din cauza backtracking-ului simplu;
- influența seed-ului asupra WalkSAT și ProbSAT;
- comportamentul pe instanțe satisfiabile față de instanțe nesatisfiabile;
- influența densității grafului sau a raportului clauze/variabile.

## 2.9 Limitări și direcții de dezvoltare

Limitări actuale:

1. aplicația este orientată spre experimentare educațională, nu spre performanța unui solver industrial;
2. DPLL folosește o euristică fixă și nu expune opțiuni dedicate în UI;
3. WalkSAT și ProbSAT nu pot demonstra `UNSAT`;
4. benchmark-urile măsoară în principal timpul și statisticile solverelor, nu memoria;
5. rezultatele pentru formule aleatoare depind de seed și trebuie interpretate statistic;
6. interfața Tkinter poate deveni încărcată vizual la benchmark-uri foarte mari.

Direcții de dezvoltare:

1. adăugarea unor verificări formale pentru soluțiile decodificate;
2. extinderea benchmark-urilor cu măsurarea memoriei;
3. adăugarea unor preprocesări SAT, precum pure literal elimination sau subsumption;
4. export mai detaliat al statisticilor solverelor;
5. comparații dedicate pe pragul de fază Random 3-SAT;
6. integrarea mai strânsă a vizualizărilor HTML în aplicația desktop.

## 2.10 Concluzii ale capitolului

Aplicația SAT Solver transformă conceptele teoretice despre SAT și reduceri polinomiale într-un instrument practic. Probleme diferite sunt exprimate într-o reprezentare comună CNF, apoi sunt rezolvate prin solvere cu paradigme diferite: DPLL ca algoritm complet clasic, CDCL ca variantă modernă cu învățare din conflicte și WalkSAT/ProbSAT ca metode incomplete de căutare locală.

Prin separarea dintre UI, encodere, modele comune, solvere și benchmark-uri, proiectul permite atât demonstrarea reducerilor la SAT, cât și compararea experimentală a algoritmilor. Capitolul aplicativ poate fi folosit ca bază pentru descrierea implementării, iar valorile numerice ale benchmark-urilor trebuie completate după rulări reale în aplicație.
