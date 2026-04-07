import utils.colored_text as txt

def unit_propagate_debug(clauses, assignment):
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

def unit_propagate(clauses, assignment):
    """
    clauses = lista de clauze
    assignment = dict {var: True/False}
    """

    changed = True

    while changed:
        changed = False

        for clause in clauses:

            if len(clause) == 1:
                lit = clause[0]
                var = abs(lit)
                val = lit > 0

                # conflict
                if var in assignment:
                    if assignment[var] != val:
                        return None
                else:
                    assignment[var] = val
                    changed = True

                    new_clauses = []

                    for c in clauses:

                        # clauza satisfacuta
                        if lit in c:
                            continue

                        # elimina negatia
                        if -lit in c:
                            new_c = [x for x in c if x != -lit]

                            if not new_c:
                                return None

                            new_clauses.append(new_c)
                        else:
                            new_clauses.append(c)

                    clauses = new_clauses
                    break

    return clauses, assignment



def unit_propagate_cdcl(clauses, assignment, level):
    changed = True

    while changed:
        changed = False

        for clause in clauses:
            unassigned = []
            satisfied = False

            for lit in clause:
                var = abs(lit)

                if var in assignment:
                    val = assignment[var][0]

                    if (lit > 0 and val) or (lit < 0 and not val):
                        satisfied = True
                        break
                else:
                    unassigned.append(lit)

            if satisfied:
                continue

            if not unassigned:
                # conflict
                return None

            if len(unassigned) == 1:
                lit = unassigned[0]
                var = abs(lit)
                val = lit > 0

                print(txt.YELLOW + f"Unit propagate: {var} = {val}" + txt.RESET)

                assignment[var] = (val, level)
                changed = True
                break

    return clauses, assignment