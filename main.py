from solvers.heuristics import choose_variable_smart, choose_variable_basic, choose_variable_small_clause

from utils.general_utils import clear_console, indent
import utils.colored_text as txt
from utils.sudoku_4x4 import generate_sudoku_4x4_clauses 
from utils.sudoku_9x9 import generate_sudoku_9x9_clauses 
from utils.sudoku_general import generate_sudoku_clauses, print_sudoku, decode_sudoku, solve_sudoku
from utils.dimacs import read_dimacs_cnf, write_dimacs_cnf

from solvers.dpll import dpll,dpll_debug
# from solvers.cdcl import cdcl
# from solvers.cdcl2 import cdcl_debug as cdcl




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
        [0, 4, 0, 0],
        [3, 1, 2, 0],
        [0, 0, 0, 0],
        [0, 3, 0, 2]
    ]

    # UNCOMENT for sudoku 4x4 solution
    write_dimacs_cnf("input/sudoku_4x4.cnf", generate_sudoku_clauses(grid_4x4))
    formula_sudoku_4x4 = read_dimacs_cnf("input/sudoku_4x4.cnf")


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
        [5, 0, 0, 0, 7, 0, 0, 0, 0],
        [6, 0, 0, 1, 0, 5, 0, 0, 0],
        [0, 9, 8, 0, 0, 0, 0, 6, 0],

        [8, 0, 0, 0, 6, 0, 0, 0, 3],
        [4, 0, 0, 8, 0, 3, 0, 0, 1],
        [7, 0, 0, 0, 2, 0, 0, 0, 6],

        [0, 6, 0, 0, 0, 0, 0, 8, 0],
        [0, 0, 0, 4, 0, 9, 0, 0, 0],
        [0, 0, 0, 0, 8, 0, 0, 0, 0]
    ]
    write_dimacs_cnf("input/sudoku_9x9.cnf", generate_sudoku_clauses(grid_9x9))
    formula_sudoku_9x9 = read_dimacs_cnf("input/sudoku_9x9.cnf")

    grid_16x16 = [
        # [ 1,  0,  0,  4,   5,  0,  7,  0,   9,  0, 11,  0,  13,  0, 15,  0],
        # [ 0,  6,  0,  8,   0, 10,  0, 12,   0, 14,  0, 16,   0,  2,  0,  4],
        # [ 0,  0,  3,  0,   0,  0,  0,  0,   13, 0, 15,  0,   0,  0,  1,  0],
        # [ 0,  0,  0,  2,   0,  0,  0,  0,   0, 12,  0, 14,   0,  0,  0, 16],

        # [ 5,  0,  7,  0,   1,  0,  3,  0,   0,  0,  0,  0,   9,  0, 11,  0],
        # [ 0, 10,  0, 12,   0,  6,  0,  8,   0,  4,  0,  2,   0, 14,  0, 16],
        # [ 0,  0,  0,  0,   0,  0,  0,  0,   5,  0,  7,  0,   0,  0,  0,  0],
        # [ 0,  0,  0,  0,   0,  0,  0,  0,   0,  6,  0,  8,   0, 10,  0, 12],

        # [ 9,  0, 11,  0,   13, 0, 15,  0,   1,  0,  3,  0,   5,  0,  7,  0],
        # [ 0, 14,  0, 16,   0, 12,  0, 10,   0,  8,  0,  6,   0,  4,  0,  2],
        # [ 0,  0,  0,  0,   0,  0,  0,  0,   9,  0, 11,  0,   0,  0,  0,  0],
        # [ 0,  0,  0,  0,   0,  0,  0,  0,   0, 10,  0, 12,   0,  6,  0,  8],

        # [13,  0, 15,  0,   9,  0, 11,  0,   5,  0,  7,  0,   1,  0,  3,  0],
        # [ 0,  2,  0,  4,   0, 16,  0, 14,   0, 12,  0, 10,   0,  8,  0,  6],
        # [ 0,  0,  0,  0,   0,  0,  0,  0,   13, 0, 15,  0,   0,  0,  0,  0],
        # [ 0,  0,  0,  0,   0,  0,  0,  0,   0, 14,  0, 16,   0, 10,  0, 12],
        
        [ 0]*16,
        [ 0]*16,
        [ 0]*16,
        [ 0]*16,

        [ 0]*16,
        [ 0]*16,
        [ 0]*16,
        [ 0]*16,

        [ 0]*16,
        [ 0]*16,
        [ 0]*16,
        [ 0]*16,

        [ 0]*16,
        [ 0]*16,
        [ 0]*16,
        [ 0]*16,
    ]

    write_dimacs_cnf("input/sudoku_16x16.cnf", generate_sudoku_clauses(grid_16x16))
    formula_sudoku_16x16 = read_dimacs_cnf("input/sudoku_16x16.cnf")

    grid_25x25 = [
        [ 1,  0,  0,  0,  5,   6,  0,  0,  0, 10,  0,  0, 13,  0, 15,  0, 17,  0,  0, 21,  0, 23,  0,  0, 25],
        [ 0,  2,  0,  4,  0,   0,  7,  0,  9,  0, 11,  0,  0, 14,  0, 16,  0, 18,  0,  0, 22,  0, 24,  0,  0],
        [ 0,  0,  3,  0,  0,   0,  0,  8,  0,  0,  0, 12,  0,  0, 15,  0,  0, 19,  0,  0, 0,  23,  0, 25,  0],
        [ 0,  0,  0,  0,  0,   6,  0,  0, 10,  0, 12,  0, 14,  0,  0, 17,  0,  0, 20,  0, 22,  0, 24,  0,  0],
        [ 0,  0,  0,  0,  5,   0,  0,  0,  0,  0, 11,  0, 13,  0, 15,  0, 17,  0,  0, 21,  0, 23,  0,  0, 25],

        [ 6,  0,  8,  0, 10,   1,  0,  3,  0,  5,  0,  7,  0,  9,  0, 11,  0, 13,  0, 15,  0, 17,  0, 19,  0],
        [ 0,  7,  0,  9,  0,   0,  2,  0,  4,  0,  6,  0,  8,  0, 10,  0, 12,  0, 14,  0, 16,  0, 18,  0, 20],
        [ 0,  0,  8,  0,  0,   0,  0,  3,  0,  0,  0,  9,  0,  0, 11,  0,  0, 13,  0,  0, 0, 15,  0, 17,  0],
        [ 0,  0,  0,  0,  0,   7,  0,  0, 11,  0, 13,  0, 15,  0,  0, 18,  0,  0, 21,  0, 23,  0, 25,  0,  0],
        [ 0,  0,  0,  0, 10,   0,  0,  0,  0,  0, 12,  0, 14,  0, 16,  0, 18,  0,  0, 22,  0, 24,  0,  0, 25],

        # rest mostly empty pattern (kept consistent structure)
        [ 0]*25,
        [ 0]*25,
        [ 0]*25,
        [ 0]*25,
        [ 0]*25,
        [ 0]*25,
        [ 0]*25,
        [ 0]*25,
        [ 0]*25,
        [ 0]*25,
    ]

    write_dimacs_cnf("input/sudoku_25x25.cnf", generate_sudoku_clauses(grid_25x25))
    formula_sudoku_25x25 = read_dimacs_cnf("input/sudoku_25x25.cnf")



    # Set formula HERE
    # used_formula = formula_sudoku_9x9

    clear_console()
    # print('\n'+'-'*txt.separator_lenght)
    # print(txt.BLUE + f"Clauses: {used_formula}" + txt.RESET)
    # print(txt.GREEN + f"Assignment: {{}}" + txt.RESET)
    # print('-'*txt.separator_lenght)

    # solution = dpll(used_formula)
    
    # print(solution)

    # print_sudoku(decode_sudoku(solution,9))
    
    solution = dpll(formula_sudoku_4x4)
    print_sudoku(decode_sudoku(solution, 4))

    solution = dpll(formula_sudoku_9x9, choose_var_fn=choose_variable_small_clause)
    print_sudoku(decode_sudoku(solution, 9))

    # solution = solve_sudoku(grid_16x16)
    # print_sudoku(solution)

    solution = dpll(formula_sudoku_16x16,choose_var_fn=choose_variable_small_clause)
    print_sudoku(decode_sudoku(solution, 16))

    




    

