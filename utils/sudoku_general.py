import math
from utils.general_utils import var

def decode_sudoku(solution, n):
    grid = [[0] * n for _ in range(n)]

    for key, value in solution.items():
        if value:
            r = key // 10000
            c = (key // 100) % 100
            v = key % 100

            if 1 <= r <= n and 1 <= c <= n:
                grid[r - 1][c - 1] = v

    return grid

def print_sudoku(grid):
    n = len(grid)
    k = int(n ** 0.5)

    line = "-" * (n * 3 + k + 1)

    for i in range(n):
        if i % k == 0:
            print(line)

        for j in range(n):
            if j % k == 0:
                print("|", end="")

            print(f"{grid[i][j]:2}", end=" ")

        print("|")

    print(line)

def generate_sudoku_clauses(grid):
    n = len(grid)
    k = int(math.sqrt(n))

    clauses = []

    # -----------------------------
    # 1️⃣ fiecare celula are cel putin o valoare
    # -----------------------------
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            clauses.append([var(r, c, val) for val in range(1, n + 1)])

    # -----------------------------
    # 2️⃣ celula are max 1 valoare
    # -----------------------------
    for r in range(1, n + 1):
        for c in range(1, n + 1):
            for v1 in range(1, n + 1):
                for v2 in range(v1 + 1, n + 1):
                    clauses.append([-var(r, c, v1), -var(r, c, v2)])

    # -----------------------------
    # 3️⃣ fiecare valoare o data pe rand
    # -----------------------------
    for r in range(1, n + 1):
        for val in range(1, n + 1):
            for c1 in range(1, n + 1):
                for c2 in range(c1 + 1, n + 1):
                    clauses.append([-var(r, c1, val), -var(r, c2, val)])

    # -----------------------------
    # 4️⃣ fiecare valoare o data pe coloana
    # -----------------------------
    for c in range(1, n + 1):
        for val in range(1, n + 1):
            for r1 in range(1, n + 1):
                for r2 in range(r1 + 1, n + 1):
                    clauses.append([-var(r1, c, val), -var(r2, c, val)])

    # -----------------------------
    # 5️⃣ blocuri k x k
    # -----------------------------
    for br in range(0, k):
        for bc in range(0, k):
            cells = []

            for r in range(1 + br * k, 1 + (br + 1) * k):
                for c in range(1 + bc * k, 1 + (bc + 1) * k):
                    cells.append((r, c))

            for val in range(1, n + 1):
                for i in range(len(cells)):
                    for j in range(i + 1, len(cells)):
                        r1, c1 = cells[i]
                        r2, c2 = cells[j]
                        clauses.append([
                            -var(r1, c1, val),
                            -var(r2, c2, val)
                        ])

    # -----------------------------
    # 6️⃣ grid initial
    # -----------------------------
    for r in range(n):
        for c in range(n):
            if grid[r][c] != 0:
                clauses.append([var(r + 1, c + 1, grid[r][c])])

    return clauses


def solve_sudoku(grid):
    n = len(grid)
    root = int(math.sqrt(n))

    def is_valid(r, c, val):
        # row
        for j in range(n):
            if grid[r][j] == val:
                return False

        # col
        for i in range(n):
            if grid[i][c] == val:
                return False

        # box
        br = (r // root) * root
        bc = (c // root) * root

        for i in range(br, br + root):
            for j in range(bc, bc + root):
                if grid[i][j] == val:
                    return False

        return True

    def find_empty():
        for i in range(n):
            for j in range(n):
                if grid[i][j] == 0:
                    return i, j
        return None

    def backtrack():
        empty = find_empty()
        if not empty:
            return True

        r, c = empty

        for val in range(1, n + 1):
            if is_valid(r, c, val):
                grid[r][c] = val

                if backtrack():
                    return True

                grid[r][c] = 0

        return False

    if backtrack():
        return grid
    return None