from utils.general_utils import clear_console, indent
import utils.colored_text as txt
from utils.sudoku_4x4 import generate_sudoku_4x4_clauses, print_sudoku_4x4_solution
from utils.sudoku_9x9 import generate_sudoku_9x9_clauses, print_sudoku_9x9_solution
from utils.dimacs import read_dimacs_cnf, write_dimacs_cnf




def unit_propagate(clauses, assignment):
    """
    clauses = lista de clauze
    assignment = dict {var: True/False}

    ideea:
    daca avem o clauza cu un singur literal -> trebuie sa fie adevarat
    """

    changed = True

    while changed:
        changed = False

        for clause in clauses:
            # daca clauza are un singur literal
            if len(clause) == 1:
                lit = clause[0]
                var = abs(lit)       # variabila
                val = lit > 0        # True sau False

                print(txt.YELLOW + f"Unit clause found: {clause}" + txt.RESET)
                # print(txt.YELLOW + f"Derived unit: {clause} → forces {var} = {val}" + txt.RESET)

                # daca variabila deja are valoare diferita -> conflict
                if var in assignment:
                    if assignment[var] != val:
                        print(txt.RED + "Conflict in unit propagation!" + txt.RESET)
                        return None
                else:
                    print(txt.GREEN + f"Assign {var} = {val} (unit propagation)" + txt.RESET)
                    # setam variabila
                    assignment[var] = val
                    changed = True

                    new_clauses = []

                    for c in clauses:
                        # daca clauza este deja satisfacuta -> o ignoram
                        if lit in c:
                            print(txt.CYAN + f"Clause satisfied and removed: {c}" + txt.RESET)
                            continue

                        # daca contine negatia -> eliminam literalul
                        if -lit in c:
                            new_c = [x for x in c if x != -lit]

                            print(txt.YELLOW + f"Removing {-lit} from {c} → {new_c}" + txt.RESET)

                            # daca clauza devine goala -> conflict
                            if not new_c:
                                print(txt.RED + "Empty clause after propagation!" + txt.RESET)
                                return None

                            new_clauses.append(new_c)
                        else:
                            new_clauses.append(c)

                    clauses = new_clauses
                    break

    return clauses, assignment

def choose_variable(clauses):
    """
    alegem prima variabila gasita
    (simplu, dar nu optim)
    """
    for clause in clauses:
        for lit in clause:
            return abs(lit)
    return None

def dpll(clauses, assignment={}, level=0):
    """
    returneaza:
    - dict (solutie) daca SAT
    - None daca UNSAT
    """

    print(indent(level) + txt.BOLD + txt.CYAN + "Entering DPLL" + txt.RESET)

    # 1️⃣ simplificare
    result = unit_propagate(clauses, assignment.copy())

    if result is None:
        print(indent(level) + txt.RED + "Conflict after propagation → BACKTRACK" + txt.RESET)
        return None

    clauses, assignment = result

    print('\n'+'-'*level + '-'*txt.separator_lenght)
    print(indent(level) + txt.BLUE + f"Clauses: {clauses}" + txt.RESET)
    print(indent(level) + txt.GREEN + f"Assignment: {assignment}" + txt.RESET)
    print('-'*level + '-'*txt.separator_lenght)

    # SAT
    # 2️⃣ daca nu mai avem clauze -> toate sunt satisfacute
    if not clauses:
        print(txt.BOLD + txt.RED + f'level = {level}' + txt.RESET)
        print(indent(level) + txt.GREEN + "SAT FOUND ✅" + txt.RESET)
        return assignment

    # 3️⃣ alegem variabila
    var = choose_variable(clauses)
    print(indent(level) + txt.YELLOW + f"Choose variable: {var}" + txt.RESET)

    # 4️⃣ incercam True si False
    for value in [True, False]:
        print(indent(level) + txt.CYAN + f"Trying {var} = {value}" + txt.RESET)

        new_assignment = assignment.copy()
        new_assignment[var] = value

        lit = var if value else -var

        new_clauses = []

        for c in clauses:
            # clauza devine adevarata
            if lit in c:
                continue

            # eliminam negatia
            if -lit in c:
                new_c = [x for x in c if x != -lit]

                if not new_c:
                    print(indent(level) + txt.RED + "Empty clause → conflict" + txt.RESET)
                    break

                new_clauses.append(new_c)
            else:
                new_clauses.append(c)

        else:
            # apel recursiv
            result = dpll(new_clauses, new_assignment, level+1)

            if result is not None:
                return result
            
        print(indent(level) + txt.RED + f"Backtracking on {var} = {value}" + txt.RESET)

    # daca nici True nici False nu merg
    return None



if __name__ == "__main__":
    formula1 = [
        [1, 2, 3],   # A OR B OR C
        [-1, 4],     # ¬A OR D
        [-2, 4],     # ¬B OR D
        [-3, 4],     # ¬C OR D
        [-4, 5],     # ¬D OR E
        [-5, 6],     # ¬E OR F
        [6]          # F
    ]

    # 1. Dacă plouă → iau umbrelă
    # 2. Dacă iau umbrelă → nu mă ud
    # 3. Plouă
    # INTREBARE
    # Ma ud?

    # A = plouă
    # B = iau umbrelă
    # C = mă ud 

    formula2 = [
        [-1, 2],   # ¬A OR B
        [-2, -3],  # ¬B OR ¬C
        [1]        # A
    ]
    # RASPUNS
    # 1 = True  → A = plouă ✔️
    # 2 = True  → B = iau umbrelă ✔️
    # 3 = False → C = NU mă ud ✔️

    formula3 = [
        [-1, 2],
        [-2, -3],
        [1],
        [3]     # C = True (mă ud)
    ]
    # RASPUNS
    # UNSAT - incosistenta logica

    unsat_formula = [
        [1],    # A
        [-1]    # ¬A
    ]

    # ----------------------- 
    # Pentru Sudoku 4x4
    # -----------------------
    
    # Definim problema 4x4
    # X(r, c, v)
    # r = rand (1..4)
    # c = coloana (1..4)
    # v = valoare (1..4)
    # -----------------
    # 4 x 4 x 4 = 64 variabile

    grid_4x4 = [
        [1, 0, 0, 2],
        [0, 0, 0, 0],
        [0, 0, 0, 0],
        [3, 0, 0, 4]
    ]

    # UNCOMENT for sudoku 4x4 solution
    write_dimacs_cnf("sudoku_4x4.cnf", generate_sudoku_4x4_clauses(grid_4x4))
    formula_sudoku_4x4 = read_dimacs_cnf("sudoku_4x4.cnf")


    # ----------------------- 
    # Pentru Sudoku 9x9
    # -----------------------

    # Definim problema 9x9
    # X(r, c, v)
    # r = rand (1..9)
    # c = coloana (1..9)
    # v = valoare (1..9)
    # -----------------
    # 9 × 9 × 9 = 729 variabile

    grid_9x9 = [
        [5, 3, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 0, 1, 9, 5, 0, 0, 0],
        [0, 9, 8, 0, 0, 0, 0, 6, 0],

        [8, 0, 0, 0, 6, 0, 0, 0, 3],
        [4, 0, 0, 8, 0, 3, 0, 0, 1],
        [7, 0, 0, 0, 2, 0, 0, 0, 6],

        [0, 6, 0, 0, 0, 0, 2, 8, 0],
        [0, 0, 0, 4, 1, 9, 0, 0, 5],
        [0, 0, 0, 0, 8, 0, 0, 7, 9]
    ]
    write_dimacs_cnf("sudoku_9x9.cnf", generate_sudoku_9x9_clauses(grid_9x9))
    formula_sudoku_9x9 = read_dimacs_cnf("sudoku_9x9.cnf")



    # Set formula HERE
    used_formula = formula_sudoku_9x9

    clear_console()
    print('\n'+'-'*txt.separator_lenght)
    print(txt.BLUE + f"Clauses: {used_formula}" + txt.RESET)
    print(txt.GREEN + f"Assignment: {{}}" + txt.RESET)
    print('-'*txt.separator_lenght)

    solution = dpll(used_formula)

    # UNCOMENT for sudoku 4x4 solution
    # print_sudoku_4x4_solution(solution)

    # UNCOMENT for sudoku 9x9 solution
    print_sudoku_9x9_solution(solution)

    

    

