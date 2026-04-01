from utils.general_utils import var


grid0_4x4 = [
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [0, 0, 0, 0]
]

grid_example_4x4 = [
    [1, 0, 0, 2],
    [0, 0, 0, 0],
    [0, 0, 0, 0],
    [3, 0, 0, 4]
]


def generate_sudoku_4x4_clauses(grid):
    clauses = []

    # -----------------------------
    # 1️⃣ fiecare celula are cel putin o valoare
    # -----------------------------
    for r in range(1, 5):
        for c in range(1, 5):
            clause = [var(r, c, v) for v in range(1, 5)]
            clauses.append(clause)

    # -----------------------------
    # 2️⃣ fiecare celula are maxim o valoare
    # -----------------------------
    for r in range(1, 5):
        for c in range(1, 5):
            for v1 in range(1, 5):
                for v2 in range(v1+1, 5):
                    clauses.append([-var(r,c,v1), -var(r,c,v2)])

    # -----------------------------
    # 3️⃣ fiecare numar apare o data pe rand
    # -----------------------------
    for r in range(1, 5):
        for v in range(1, 5):
            for c1 in range(1, 5):
                for c2 in range(c1+1, 5):
                    clauses.append([-var(r,c1,v), -var(r,c2,v)])

    # -----------------------------
    # 4️⃣ fiecare numar apare o data pe coloana
    # -----------------------------
    for c in range(1, 5):
        for v in range(1, 5):
            for r1 in range(1, 5):
                for r2 in range(r1+1, 5):
                    clauses.append([-var(r1,c,v), -var(r2,c,v)])

    # -----------------------------
    # 5️⃣ fiecare bloc 2x2
    # -----------------------------
    for br in range(0, 2):
        for bc in range(0, 2):
            for v in range(1, 5):
                cells = []

                for r in range(1+2*br, 3+2*br):
                    for c in range(1+2*bc, 3+2*bc):
                        cells.append((r,c))

                for i in range(len(cells)):
                    for j in range(i+1, len(cells)):
                        r1,c1 = cells[i]
                        r2,c2 = cells[j]
                        clauses.append([-var(r1,c1,v), -var(r2,c2,v)])

    # -----------------------------
    # 6️⃣ valori initiale (date)
    # -----------------------------
    for r in range(4):
        for c in range(4):
            if grid[r][c] != 0:
                clauses.append([var(r+1, c+1, grid[r][c])])

    return clauses


def decode_sudoku_4x4_solution(solution):
    grid = [[0]*4 for _ in range(4)]

    for key, value in solution.items():
        if value:
            r = key // 100
            c = (key // 10) % 10
            v = key % 10

            grid[r-1][c-1] = v

    return grid


def print_sudoku_4x4_solution(solution):
    if solution:
        sudoku_4x4_solution = decode_sudoku_4x4_solution(solution)

        for row in sudoku_4x4_solution:
            print(row)
