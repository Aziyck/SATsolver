# Checklist pentru capturi de ecran

Acest document listează capturile recomandate pentru raportul aplicativ. Denumirile dintre paranteze pătrate pot fi folosite direct ca placeholders în document.

## Interfața generală

- [ ] [Figura 1: Interfața principală a aplicației SAT Solver]
- [ ] [Figura 2: Fila Solve cu selectarea tipului de problemă]
- [ ] [Figura 3: Fila Benchmarks cu panoul de configurare]
- [ ] [Figura 4: Panoul global de log și joburi]

## Generare și rezolvare CNF

- [ ] [Figura 5: Generarea unei formule CNF pentru Sudoku]
- [ ] [Figura 6: Previzualizarea formulei CNF generate]
- [ ] [Figura 7: Selectarea solverului CDCL]
- [ ] [Figura 8: Rezultatul brut SAT și soluția decodificată]
- [ ] [Figura 9: Salvarea unei formule DIMACS]
- [ ] [Figura 10: Încărcarea unei formule DIMACS]

## Probleme pe grafuri

- [ ] [Figura 11: Introducerea manuală a muchiilor unui graf]
- [ ] [Figura 12: Generarea unui graf aleator G(n,p)]
- [ ] [Figura 13: Previzualizarea grafului în aplicație]
- [ ] [Figura 14: Fereastra Open Graph pentru un rezultat de benchmark]
- [ ] [Figura 15: Exportul grafului ca imagine PNG]

## Opțiuni de solver

- [ ] [Figura 16: Opțiunile CDCL pentru branching, phase și restarts]
- [ ] [Figura 17: Opțiunile WalkSAT și selectarea strategiei ProbSAT]
- [ ] [Figura 18: Configurarea timeout-ului și a seed-ului]

## Benchmark

- [ ] [Figura 19: Configurarea unui benchmark Graph Coloring]
- [ ] [Figura 20: Configurarea unui benchmark Random 3-SAT]
- [ ] [Figura 21: Rezultatele benchmark în tabel]
- [ ] [Figura 22: Graficul comparativ generat în aplicație]
- [ ] [Figura 23: Exportul rezultatelor în CSV]
- [ ] [Figura 24: Detaliile unei instanțe selectate din benchmark]

## Vizualizări educaționale

Fișiere relevante:

- `docs/visualisations/dpll/index.html`
- `docs/visualisations/cdcl/index.html`
- `docs/visualisations/walksat/index.html`

Capturi recomandate:

- [ ] [Figura 25: Vizualizatorul DPLL]
- [ ] [Figura 26: Vizualizatorul CDCL și clauza învățată]
- [ ] [Figura 27: Vizualizatorul WalkSAT și alegerea unei clauze nesatisfăcute]

## Recomandări pentru consistență

1. Folosește aceeași temă vizuală și aceeași rezoluție pentru toate capturile.
2. Ascunde ferestrele inutile înainte de captură.
3. Pentru benchmark, folosește date reale, dar păstrează dimensiuni mici dacă scopul capturii este doar demonstrarea UI.
4. Pentru grafuri, folosește un seed fix ca imaginea să poată fi refăcută.
5. În textul raportului, fiecare captură trebuie explicată în 2-4 fraze.
