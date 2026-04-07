import time
import matplotlib.pyplot as plt

from solvers.dpll import dpll
from utils.sudoku_general import solve_sudoku, decode_sudoku, print_sudoku
from experiments.puzzels import (
    formula_sudoku_4x4,
    formula_sudoku_9x9,
    formula_sudoku_16x16,
    grid_4x4,
    grid_9x9,
    grid_16x16
)
from solvers.heuristics import choose_variable_small_clause

def benchmark(name, func, *args, runs=3):
    times = []
    result = None

    for _ in range(runs):
        start = time.perf_counter()
        result = func(*args)
        end = time.perf_counter()
        times.append(end - start)

    avg = sum(times) / len(times)

    print(f"\n[{name}]")
    print(f"avg time: {avg:.6f}s")

    return result, avg

results = []

def run_case(size, formula, grid):
    print("\n" + "="*60)
    print(f"SIZE {size}")
    print("="*60)

    n = int(size.split("x")[0])

    # DPLL
    sol_dpll, t_dpll = benchmark(
        f"DPLL {size}",
        dpll,
        formula
    )

    # solver clasic
    sol_native, t_native = benchmark(
        f"NATIVE {size}",
        solve_sudoku,
        grid
    )

    # 🔥 NORMALIZARE
    norm_dpll = t_dpll / (n * n)
    norm_native = t_native / (n * n)

    results.append((size, "DPLL", t_dpll, norm_dpll))
    results.append((size, "NATIVE", t_native, norm_native))

    # optional print solution
    if sol_dpll:
        print("\nDPLL solution:")
        print_sudoku(decode_sudoku(sol_dpll, int(size.split('x')[0])))

    if sol_native:
        print("\nNative solution:")
        print_sudoku(sol_native)


def format_time(t):
    if t < 1:
        return f"{t*1000:.6f} ms"
    else:
        return f"{t:.7f} s"

def print_table():
    print("\n" + "="*70)
    print("BENCHMARK RESULTS")
    print("="*70)
    print(f"{'SIZE':6} | {'METHOD':10} | {'RAW TIME':15}   | {'NORM TIME'}")
    print("-"*70)

    for size, method, raw, norm in results:
        print(f"{size:6} | {method:10} | {format_time(raw):15}   | {norm:.8f}")

data = {}

def size_key(s):
    return int(s.split("x")[0])

def plot_results():
    sizes = sorted(data.keys(), key=size_key)

    dpll_times = [data[s]["DPLL"]["raw"] for s in sizes]
    native_times = [data[s]["NATIVE"]["raw"] for s in sizes]

    x = range(len(sizes))

    plt.figure()

    plt.plot(x, dpll_times, label="DPLL")
    plt.plot(x, native_times, label="Native")

    plt.xticks(x, sizes)
    plt.xlabel("Sudoku size")
    plt.ylabel("Time (seconds)")
    plt.title("Logarithmic performance comparison")
    plt.legend()

    # recomandat:
    plt.yscale("log")

    plt.show()

def plot_normalized():
    sizes = sorted(data.keys(), key=lambda s: int(s.split("x")[0]))

    dpll_norm = [data[s]["DPLL"]["norm"] for s in sizes]
    native_norm = [data[s]["NATIVE"]["norm"] for s in sizes]

    x = range(len(sizes))

    plt.figure()

    plt.plot(x, dpll_norm, label="DPLL (normalized)")
    plt.plot(x, native_norm, label="Native (normalized)")

    plt.xticks(x, sizes)
    plt.xlabel("Sudoku size")
    plt.ylabel("Time per cell")
    plt.title("Normalized performance comparison")
    plt.legend()

    plt.show()

if __name__ == "__main__":

    run_case("4x4", formula_sudoku_4x4, grid_4x4)
    run_case("9x9", formula_sudoku_9x9, grid_9x9)
    run_case("16x16", formula_sudoku_16x16, grid_16x16)


    for size, method, raw, norm in results:
        if size not in data:
            data[size] = {}
        data[size][method] = {
            "raw": raw,
            "norm": norm
        }

    print_table()
    plot_results()
    plot_normalized()
