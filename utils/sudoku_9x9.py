from utils.general_utils import var

grid0_9x9 = [
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],

    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],

    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
    [0, 0, 0, 0, 0, 0, 0, 0, 0],
]

grid_example_9x9 = [
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

def generate_sudoku_9x9_clauses(grid):
    clauses = []

    # -----------------------------
    # 1️⃣ fiecare celula are cel putin o valoare
    # -----------------------------
    for r in range(1, 10):
        for c in range(1, 10):
            clauses.append([var(r,c,v) for v in range(1,10)])

    # -----------------------------
    # 2️⃣ fiecare celula are maxim o valoare
    # -----------------------------
    for r in range(1, 10):
        for c in range(1, 10):
            for v1 in range(1, 10):
                for v2 in range(v1+1, 10):
                    clauses.append([-var(r,c,v1), -var(r,c,v2)])

    # -----------------------------
    # 3️⃣ fiecare numar apare o data pe rand
    # -----------------------------
    for r in range(1, 10):
        for v in range(1, 10):
            for c1 in range(1, 10):
                for c2 in range(c1+1, 10):
                    clauses.append([-var(r,c1,v), -var(r,c2,v)])

    # -----------------------------
    # 4️⃣ fiecare numar apare o data pe coloana
    # -----------------------------
    for c in range(1, 10):
        for v in range(1, 10):
            for r1 in range(1, 10):
                for r2 in range(r1+1, 10):
                    clauses.append([-var(r1,c,v), -var(r2,c,v)])

    # -----------------------------
    # 5️⃣ fiecare bloc 3x3
    # -----------------------------
    for br in range(0, 3):
        for bc in range(0, 3):
            for v in range(1, 10):

                cells = []

                for r in range(1+3*br, 4+3*br):
                    for c in range(1+3*bc, 4+3*bc):
                        cells.append((r,c))

                for i in range(len(cells)):
                    for j in range(i+1, len(cells)):
                        r1,c1 = cells[i]
                        r2,c2 = cells[j]
                        clauses.append([
                            -var(r1,c1,v),
                            -var(r2,c2,v)
                        ])
        
    # -----------------------------
    # 6️⃣ valori initiale (date)
    # -----------------------------
    for r in range(9):
        for c in range(9):
            if grid[r][c] != 0:
                clauses.append([var(r+1, c+1, grid[r][c])])
    
    return clauses


def decode_sudoku_9x9_solution(solution):
    grid = [[0]*9 for _ in range(9)]

    for key, value in solution.items():
        if value:
            r = key // 100
            c = (key // 10) % 10
            v = key % 10

            grid[r-1][c-1] = v

    return grid

def print_sudoku_9x9_solution(solution):
    if solution:
        board = decode_sudoku_9x9_solution(solution)

        for i in range(9):
            row = board[i]

            if (i % 3 == 0):
                print('-'*31)
            
            for j in range(9):
                if(j == 0):
                    print(f"|{row[j]:^3}", end="")
                elif((j+1) % 3 == 0):
                    print(f"{row[j]:^3}|", end="")
                else:
                    print(f"{row[j]:^3}", end="")
            print()
        print('-'*31)