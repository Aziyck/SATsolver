def cdcl_debug(clauses, max_steps=5000):
    assignment = {}
    decision_level = 0
    trail = []
    step = 0
    seen_conflicts = set()

    def log(msg):
        nonlocal step
        if step % 50 == 0:  # nu spam
            print(f"[step {step}] {msg}")

    def val(lit):
        v = abs(lit)
        if v not in assignment:
            return None
        return assignment[v] if lit > 0 else not assignment[v]

    def print_state():
        if step % 100 == 0:
            small = {k: assignment[k] for k in list(assignment)[:10]}
            print(f"   assignment size={len(assignment)} sample={small}")

    def unit_propagate():
        changed = True

        while changed:
            changed = False

            for c in clauses:
                vals = [val(l) for l in c]

                if True in vals:
                    continue

                unassigned = [l for l, v in zip(c, vals) if v is None]

                if len(unassigned) == 0:
                    print(f"❌ CONFLICT clause={c} level={decision_level}")
                    return tuple(sorted(c))

                if len(unassigned) == 1:
                    lit = unassigned[0]
                    v = abs(lit)

                    if v in assignment and assignment[v] != (lit > 0):
                        print(f"⚠️ DIRECT CONFLICT on var {v}")
                        return tuple(sorted(c))

                    if v not in assignment:
                        assignment[v] = (lit > 0)
                        trail.append(v)
                        log(f"🔵 UNIT PROP: {v} = {assignment[v]}")

                        changed = True

        return None

    def pick_var():
        for c in clauses:
            for l in c:
                v = abs(l)
                if v not in assignment:
                    return v
        return None

    def backjump():
        nonlocal decision_level

        if trail:
            v = trail.pop()
            print(f"↩️ BACKTRACK remove {v}")

            if v in assignment:
                del assignment[v]

        decision_level = max(0, decision_level - 1)

    print("🚀 START CDCL DEBUG")

    while step < max_steps:
        step += 1

        conflict = unit_propagate()

        # 🔴 CONFLICT
        if conflict:
            print(f"💥 CONFLICT at level {decision_level}")

            if decision_level == 0:
                print("💀 UNSAT")
                return None

            if conflict in seen_conflicts:
                print("♻️ repeated conflict → backjump harder")
                backjump()
                continue

            seen_conflicts.add(conflict)

            print(f"📌 learning conflict clause: {conflict}")

            backjump()
            continue

        # SAT CHECK
        if all(any(val(l) for l in c) for c in clauses):
            print("✅ SAT FOUND")
            return assignment

        var = pick_var()

        if var is None:
            print("⚠️ no variable left")
            return assignment

        decision_level += 1

        value = (decision_level % 2 == 0)
        assignment[var] = value
        trail.append(var)

        log(f"🟢 DECISION: {var} = {value} (level {decision_level})")
        print_state()

    print("⛔ STOP: max steps reached")
    return None