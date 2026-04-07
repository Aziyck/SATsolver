# Alege simplu prima variabila intalnita
def choose_variable_basic(clauses, assignment):
    """
    alegem prima variabila gasita
    (simplu, dar nu optim)
    """
    for clause in clauses:
        for lit in clause:
            var = abs(lit)
            if var not in assignment:
                return var
    return None

# Frequency heuristic (simplu și bun)
# 👉 alege variabila care apare cel mai des
def choose_variable_smart(clauses, assignment):
    freq = {}

    for clause in clauses:
        for lit in clause:
            var = abs(lit)
            if var not in assignment:
                freq[var] = freq.get(var, 0) + 1

    return max(freq, key=freq.get)


# Preferă variabile din clauze mici
# 👉 foarte eficient în practică
def choose_variable_small_clause(clauses, assignment):
    clauses = sorted(clauses, key=len)

    for clause in clauses:
        for lit in clause:
            var = abs(lit)
            if var not in assignment:
                return var

class Heuristic:
    def choose(self, clauses, assignment):
        pass

    def on_conflict(self, clause):
        pass