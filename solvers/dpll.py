from utils.general_utils import  indent
from solvers.solver_utils import unit_propagate_debug, unit_propagate
from solvers.heuristics import choose_variable_basic
import utils.colored_text as txt



def dpll_debug(clauses, assignment=None, level=0, choose_var_fn=None):
    """
    returneaza:
    - dict (solutie) daca SAT
    - None daca UNSAT
    """
    if assignment is None:
        assignment = {}

    if choose_var_fn is None:
        choose_var_fn = choose_variable_basic

    print(indent(level) + txt.BOLD + txt.CYAN + "Entering DPLL" + txt.RESET)

    # 1️⃣ simplificare
    result = unit_propagate_debug(clauses, assignment.copy())

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
    var = choose_var_fn(clauses, assignment)
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
            result = dpll_debug(new_clauses, new_assignment, level+1, choose_var_fn)

            if result is not None:
                return result
            
        print(indent(level) + txt.RED + f"Backtracking on {var} = {value}" + txt.RESET)

    # daca nici True nici False nu merg
    return None



def dpll(clauses, assignment=None, choose_var_fn=None):
    """
    returneaza:
    - dict (solutie) daca SAT
    - None daca UNSAT
    """
    if assignment is None:
        assignment = {}

    if choose_var_fn is None:
        choose_var_fn = choose_variable_basic

    # 1️⃣ simplificare
    result = unit_propagate(clauses, assignment.copy())

    if result is None:
        return None

    clauses, assignment = result

    # 2️⃣ SAT check
    if not clauses:
        return assignment

    # 3️⃣ alegem variabila
    var = choose_var_fn(clauses, assignment)

    # 4️⃣ backtracking search
    for value in [True, False]:

        new_assignment = assignment.copy()
        new_assignment[var] = value

        lit = var if value else -var
        new_clauses = []

        for c in clauses:

            # clauza e satisfacuta
            if lit in c:
                continue

            # eliminam negatia
            if -lit in c:
                new_c = [x for x in c if x != -lit]

                if not new_c:
                    break  # conflict

                new_clauses.append(new_c)
            else:
                new_clauses.append(c)

        else:
            result = dpll(new_clauses, new_assignment, choose_var_fn)

            if result is not None:
                return result

    return None