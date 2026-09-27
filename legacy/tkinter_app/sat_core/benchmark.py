from __future__ import annotations

import csv
import math
from pathlib import Path
from typing import Iterable

from problems.clique import (
    average_degree_clique_problem,
    clique_problem,
    exact_edges_clique_problem,
    random_clique_problem,
)
from problems.graph_coloring import (
    average_degree_graph_coloring_problem,
    edge_count_from_average_degree,
    exact_edges_graph_coloring_problem,
    graph_coloring_problem,
    random_graph_coloring_problem,
)
from problems.hamiltonian_path import (
    average_degree_hamiltonian_path_problem,
    exact_edges_hamiltonian_path_problem,
    hamiltonian_path_problem,
    random_hamiltonian_path_problem,
)
from problems.independent_set import (
    average_degree_independent_set_problem,
    exact_edges_independent_set_problem,
    independent_set_problem,
    random_independent_set_problem,
)
from problems.n_queens import n_queens_problem
from problems.random_3sat import random_3sat_problem
from problems.sudoku import sudoku_problem, validate_sudoku_grid
from sat_core.models import BENCHMARK_HEADERS, BenchmarkRow, ProblemInstance, SolveResult
from sat_core.benchmark_presets.random_3sat_presets import (
    RANDOM_3SAT_PRESET_A,
    RANDOM_3SAT_PRESET_B,
    RANDOM_3SAT_PRESET_C,
    RANDOM_3SAT_PRESET_CUSTOM,
    RANDOM_3SAT_PRESETS,
    random_3sat_preset_case_count,
    random_3sat_preset_cases,
    random_3sat_preset_default_solvers,
    random_3sat_preset_should_skip_solver,
    random_3sat_preset_solver_timeout,
)
from sat_core.runtime import (
    EVENT_CANCELLED,
    EVENT_LOG,
    EVENT_PROGRESS,
    EVENT_ROW,
    RunToken,
    cancel_requested,
    emit,
    skip_requested,
)
from sat_core.solver_runner import solve_problem
from utils.graph_utils import generate_random_graph, generate_random_graph_exact_edges, graph_edges


SUDOKU_BENCHMARK_SIZES = (4, 9, 16, 25)
MAX_STORED_BENCHMARK_CLAUSES = 50_000
RANDOM_3SAT_CSV_HEADERS = [
    "problem_mode",
    "n_vars",
    "ratio",
    "n_clauses",
    "sat_fraction",
    "seed",
    "solver",
    "status",
    "elapsed",
    "decisions",
    "conflicts",
    "propagations",
    "learned_clauses",
    "flips",
    "tries",
    "best_unsatisfied",
    "timeout",
]


def stored_benchmark_clauses(problem: ProblemInstance) -> list[list[int]]:
    if problem.clause_count > MAX_STORED_BENCHMARK_CLAUSES:
        return []
    return [clause[:] for clause in problem.clauses]


def result_to_row(problem: ProblemInstance, result: SolveResult, repeat: int) -> BenchmarkRow:
    stats = result.stats or {}
    metadata = dict(problem.metadata)
    if problem.clause_count > MAX_STORED_BENCHMARK_CLAUSES:
        metadata["cnf_storage"] = f"skipped; {problem.clause_count} clauses exceeds {MAX_STORED_BENCHMARK_CLAUSES}"
    return BenchmarkRow(
        case_name=problem.name,
        problem_type=problem.problem_type,
        solver=result.solver,
        status=result.status,
        elapsed=result.elapsed,
        clauses=problem.clause_count,
        variables=problem.variable_count,
        repeat=repeat,
        detail=benchmark_detail(problem),
        conflicts=stats.get("conflicts", "-"),
        decisions=stats.get("decisions", "-"),
        propagations=stats.get("propagations", "-"),
        learned_clauses=stats.get("learned_clauses", "-"),
        generation_mode=problem.metadata.get("mode", ""),
        edge_count=problem.metadata.get("edges", "-"),
        node_count=problem.metadata.get("nodes", "-"),
        graph_edges=problem.metadata.get("graph_edges", []),
        decoded=result.decoded,
        seed=problem.metadata.get("seed", "-"),
        solver_options=stats.get("solver_options", ""),
        problem_metadata=metadata,
        problem_clauses=stored_benchmark_clauses(problem),
        flips=stats.get("flips", "-"),
        tries=stats.get("tries", "-"),
        best_unsatisfied=stats.get("best_unsatisfied", "-"),
        timeout=stats.get("timeout", "-"),
    )


def skipped_result(problem: ProblemInstance, solver: str) -> SolveResult:
    return SolveResult(
        solver=solver,
        status="SKIPPED",
        elapsed=0.0,
        solution=None,
        stats={"status": "SKIPPED", "elapsed": 0.0},
        clauses=problem.clause_count,
        variables=problem.variable_count,
    )


def _emit_benchmark_result(
    rows: list[BenchmarkRow],
    event_callback,
    problem: ProblemInstance,
    result: SolveResult,
    repeat: int,
    run_index: int,
    total_runs: int,
) -> int:
    run_index += 1
    row = result_to_row(problem, result, repeat)
    rows.append(row)
    emit(event_callback, EVENT_ROW, payload={"row": row}, current=run_index, total=total_runs)
    emit(event_callback, EVENT_PROGRESS, f"{run_index}/{total_runs} solver runs finished", current=run_index, total=total_runs)
    emit(event_callback, EVENT_LOG, f"      {result.solver} time: {result.elapsed:.5f}s ({result.status})")
    return run_index


def _clear_skip(cancel_token: RunToken | None) -> None:
    if cancel_token is not None:
        cancel_token.clear_skip()


def _run_case_solvers(
    problem: ProblemInstance,
    solvers: list[str],
    repeat: int,
    rows: list[BenchmarkRow],
    run_index: int,
    total_runs: int,
    event_callback,
    cancel_token: RunToken | None,
    logging_options: dict | None,
    timeout_seconds: float | None,
    timeout_for_solver=None,
    skip_solver=None,
) -> tuple[int, bool]:
    for solver_index, solver in enumerate(solvers):
        if cancel_requested(cancel_token):
            emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled.", current=run_index, total=total_runs)
            return run_index, False

        if skip_requested(cancel_token):
            emit(event_callback, EVENT_LOG, "   -> Skip requested; marking current case as SKIPPED.")
            for skipped_solver in solvers[solver_index:]:
                run_index = _emit_benchmark_result(
                    rows,
                    event_callback,
                    problem,
                    skipped_result(problem, skipped_solver),
                    repeat,
                    run_index,
                    total_runs,
                )
            _clear_skip(cancel_token)
            return run_index, True

        if skip_solver is not None and skip_solver(solver, problem):
            emit(event_callback, EVENT_LOG, f"   -> Skipping {solver} solver by preset policy.")
            run_index = _emit_benchmark_result(
                rows,
                event_callback,
                problem,
                skipped_result(problem, solver),
                repeat,
                run_index,
                total_runs,
            )
            continue

        emit(event_callback, EVENT_LOG, f"   -> Running {solver} solver...")
        solver_timeout = timeout_for_solver(solver, problem, timeout_seconds) if timeout_for_solver else timeout_seconds
        result = solve_problem(
            problem,
            solver,
            event_callback=event_callback,
            cancel_token=cancel_token,
            logging_options=logging_options,
            timeout_seconds=solver_timeout,
        )

        if result.status == "CANCELLED":
            emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled during solver run.", current=run_index, total=total_runs)
            return run_index, False

        run_index = _emit_benchmark_result(
            rows,
            event_callback,
            problem,
            result,
            repeat,
            run_index,
            total_runs,
        )

        if result.status == "SKIPPED":
            remaining_solvers = solvers[solver_index + 1:]
            if remaining_solvers:
                emit(event_callback, EVENT_LOG, "   -> Skipping remaining solvers for this case.")
            for skipped_solver in remaining_solvers:
                run_index = _emit_benchmark_result(
                    rows,
                    event_callback,
                    problem,
                    skipped_result(problem, skipped_solver),
                    repeat,
                    run_index,
                    total_runs,
                )
            _clear_skip(cancel_token)
            return run_index, True

    _clear_skip(cancel_token)
    return run_index, True


def benchmark_detail(problem: ProblemInstance) -> str:
    mode = problem.metadata.get("mode", "")
    edges = problem.metadata.get("edges", "-")

    if problem.metadata.get("suite"):
        graph_label = problem.metadata.get("suite_graph_label", "-")
        if problem.problem_type in ("Independent Set", "Clique"):
            return f"graph={graph_label}, k={problem.metadata.get('target', '?')}, edges={edges}"
        if problem.problem_type == "Graph Coloring":
            return f"graph={graph_label}, colors={problem.metadata.get('colors', '?')}, edges={edges}"
        return f"graph={graph_label}, edges={edges}"

    if problem.problem_type == "Sudoku":
        size = problem.metadata.get("size", "?")
        givens = problem.metadata.get("givens", "?")
        return f"size={size}, givens={givens}"

    if problem.problem_type == "N-Queens":
        return f"n={problem.metadata.get('size', '?')}"

    if problem.problem_type == "Random 3-SAT":
        mode = problem.metadata.get("mode", "random")
        if mode == "Random" and problem.metadata.get("sat_percentage") is not None:
            mode = (
                f"{mode} ({problem.metadata.get('sat_percentage'):g}% SAT, "
                f"selected {problem.metadata.get('selected_mode', '-')})"
            )
        return (
            f"n={problem.metadata.get('variables', '?')}, "
            f"m={problem.metadata.get('clauses_requested', '?')}, "
            f"ratio={problem.metadata.get('ratio', 0):.2f}, "
            f"{mode}"
        )

    if problem.problem_type in ("Independent Set", "Clique"):
        return f"k={problem.metadata.get('target', '?')}, edges={edges}"

    if problem.problem_type in ("Graph Coloring", "Hamiltonian Path"):
        return f"{mode}, edges={edges}" if mode else f"edges={edges}"

    return ""


def graph_coloring_sweep(
    node_counts: Iterable[int],
    probabilities: Iterable[float],
    color_counts: Iterable[int],
    solvers: Iterable[str],
    repeats: int,
    seed: int | None = None,
) -> list[BenchmarkRow]:
    return run_graph_coloring_sweep(
        node_counts,
        probabilities,
        color_counts,
        solvers,
        repeats,
        seed=seed,
    )


def solved_sudoku_grid(size: int) -> list[list[int]]:
    root = int(math.sqrt(size))
    validate_sudoku_grid([[0] * size for _ in range(size)])

    return [
        [((row * root + row // root + col) % size) + 1 for col in range(size)]
        for row in range(size)
    ]


def sudoku_benchmark_grid(size: int) -> list[list[int]]:
    solved = solved_sudoku_grid(size)
    return [
        [solved[row][col] if (row + col) % 2 == 0 else 0 for col in range(size)]
        for row in range(size)
    ]


def sudoku_benchmark_problem(size: int) -> ProblemInstance:
    grid = sudoku_benchmark_grid(size)
    problem = sudoku_problem(grid, name=f"Sudoku {size}x{size} benchmark")
    problem.metadata.update({"mode": "benchmark", "benchmark_size": size})
    return problem


def run_sudoku_sweep(
    sizes: Iterable[int],
    solvers: Iterable[str],
    repeats: int,
    event_callback=None,
    cancel_token: RunToken | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> list[BenchmarkRow]:
    sizes = list(sizes)
    solvers = list(solvers)
    rows = []
    total_cases = len(sizes) * repeats
    total_runs = total_cases * len(solvers)
    case_index = 0
    run_index = 0

    if cancel_requested(cancel_token):
        emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled before start.", current=0, total=total_runs)
        return rows

    for size in sizes:
        if size not in SUDOKU_BENCHMARK_SIZES:
            raise ValueError(f"Unsupported Sudoku benchmark size: {size}")

        for repeat in range(1, repeats + 1):
            if cancel_requested(cancel_token):
                emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled.", current=run_index, total=total_runs)
                return rows

            case_index += 1
            case_label = f"Sudoku {size}x{size} benchmark"
            emit(event_callback, EVENT_LOG, f"[{case_index}/{total_cases}] {case_label} repeat {repeat}")
            emit(event_callback, EVENT_LOG, "   -> Generating CNF...")
            problem = sudoku_benchmark_problem(size)
            emit(event_callback, EVENT_LOG, _sudoku_generation_summary(problem))

            run_index, should_continue = _run_case_solvers(
                problem,
                solvers,
                repeat,
                rows,
                run_index,
                total_runs,
                event_callback,
                cancel_token,
                logging_options,
                timeout_seconds,
            )
            if not should_continue:
                return rows

    return rows


def run_n_queens_sweep(
    sizes: Iterable[int],
    solvers: Iterable[str],
    repeats: int,
    event_callback=None,
    cancel_token: RunToken | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> list[BenchmarkRow]:
    sizes = list(sizes)
    solvers = list(solvers)
    rows = []
    total_cases = len(sizes) * repeats
    total_runs = total_cases * len(solvers)
    case_index = 0
    run_index = 0

    if cancel_requested(cancel_token):
        emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled before start.", current=0, total=total_runs)
        return rows

    for size in sizes:
        for repeat in range(1, repeats + 1):
            if cancel_requested(cancel_token):
                emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled.", current=run_index, total=total_runs)
                return rows

            case_index += 1
            emit(event_callback, EVENT_LOG, f"[{case_index}/{total_cases}] N-Queens n{size} repeat {repeat}")
            emit(event_callback, EVENT_LOG, "   -> Generating CNF...")
            problem = n_queens_problem(size)
            emit(event_callback, EVENT_LOG, _generic_generation_summary(problem))

            run_index, should_continue = _run_case_solvers(
                problem,
                solvers,
                repeat,
                rows,
                run_index,
                total_runs,
                event_callback,
                cancel_token,
                logging_options,
                timeout_seconds,
            )
            if not should_continue:
                return rows

    return rows


def _random_3sat_preset_timeout(solver: str, problem: ProblemInstance, timeout_seconds: float | None) -> float | None:
    return random_3sat_preset_solver_timeout(
        solver,
        int(problem.metadata.get("variables", 0)),
        timeout_seconds,
        problem.metadata.get("preset"),
    )


def _random_3sat_preset_skip(solver: str, problem: ProblemInstance) -> bool:
    return random_3sat_preset_should_skip_solver(
        solver,
        int(problem.metadata.get("variables", 0)),
        problem.metadata.get("preset"),
    )


def run_random_3sat_preset(
    preset_name: str,
    solvers: Iterable[str],
    event_callback=None,
    cancel_token: RunToken | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> list[BenchmarkRow]:
    cases = random_3sat_preset_cases(preset_name)
    solvers = list(solvers)
    rows = []
    total_runs = len(cases) * len(solvers)
    run_index = 0

    if cancel_requested(cancel_token):
        emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled before start.", current=0, total=total_runs)
        return rows

    for case_index, case in enumerate(cases, start=1):
        if cancel_requested(cancel_token):
            emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled.", current=run_index, total=total_runs)
            return rows

        problem = random_3sat_problem(
            case["variable_count"],
            case["clause_count"],
            seed=case["seed"],
            formula_mode=case["formula_mode"],
            sat_percentage=case["sat_percentage"],
        )
        problem.metadata.update({
            "preset": preset_name,
            "preset_case_index": case_index,
            "preset_sat_fraction": case["sat_fraction"],
        })
        emit(event_callback, EVENT_LOG, f"[{case_index}/{len(cases)}] {preset_name}: {problem.name} seed {case['seed']}")
        emit(event_callback, EVENT_LOG, "   -> Generating CNF...")
        emit(event_callback, EVENT_LOG, _random_3sat_generation_summary(problem))

        run_index, should_continue = _run_case_solvers(
            problem,
            solvers,
            case["seed"],
            rows,
            run_index,
            total_runs,
            event_callback,
            cancel_token,
            logging_options,
            timeout_seconds,
            timeout_for_solver=_random_3sat_preset_timeout,
            skip_solver=_random_3sat_preset_skip,
        )
        if not should_continue:
            return rows

    return rows


def run_random_3sat_sweep(
    variable_counts: Iterable[int],
    clause_ratios: Iterable[float],
    solvers: Iterable[str],
    repeats: int,
    seed: int | None = None,
    planted: bool = True,
    formula_mode: str | None = None,
    sat_percentage: float | None = None,
    event_callback=None,
    cancel_token: RunToken | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> list[BenchmarkRow]:
    variable_counts = list(variable_counts)
    clause_ratios = list(clause_ratios)
    solvers = list(solvers)
    rows = []
    total_cases = len(variable_counts) * len(clause_ratios) * repeats
    total_runs = total_cases * len(solvers)
    case_index = 0
    run_index = 0

    if cancel_requested(cancel_token):
        emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled before start.", current=0, total=total_runs)
        return rows

    for variable_count in variable_counts:
        for ratio in clause_ratios:
            clause_count = max(1, round(variable_count * ratio))
            for repeat in range(1, repeats + 1):
                if cancel_requested(cancel_token):
                    emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled.", current=run_index, total=total_runs)
                    return rows

                case_index += 1
                ratio_seed = int(ratio * 1000)
                case_seed = None if seed is None else seed + repeat + variable_count * 1000 + ratio_seed
                problem = random_3sat_problem(
                    variable_count,
                    clause_count,
                    seed=case_seed,
                    planted=planted,
                    formula_mode=formula_mode,
                    sat_percentage=sat_percentage,
                )
                emit(event_callback, EVENT_LOG, f"[{case_index}/{total_cases}] {problem.name} repeat {repeat}")
                emit(event_callback, EVENT_LOG, "   -> Generating CNF...")
                emit(event_callback, EVENT_LOG, _random_3sat_generation_summary(problem))

                run_index, should_continue = _run_case_solvers(
                    problem,
                    solvers,
                    repeat,
                    rows,
                    run_index,
                    total_runs,
                    event_callback,
                    cancel_token,
                    logging_options,
                    timeout_seconds,
                )
                if not should_continue:
                    return rows

    return rows


def run_graph_coloring_sweep(
    node_counts: Iterable[int],
    probabilities: Iterable[float] | None,
    color_counts: Iterable[int],
    solvers: Iterable[str],
    repeats: int,
    seed: int | None = None,
    edge_counts: Iterable[int] | None = None,
    generation_mode: str = "probability",
    event_callback=None,
    cancel_token: RunToken | None = None,
    average_degrees: Iterable[float] | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> list[BenchmarkRow]:
    node_counts = list(node_counts)
    if generation_mode == "exact_edges":
        values = list(edge_counts or [])
    elif generation_mode == "average_degree":
        values = list(average_degrees or [])
    else:
        values = list(probabilities or [])
    color_counts = list(color_counts)
    solvers = list(solvers)
    rows = []
    total_cases = len(node_counts) * len(values) * len(color_counts) * repeats
    total_runs = total_cases * len(solvers)
    case_index = 0
    run_index = 0

    if cancel_requested(cancel_token):
        emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled before start.", current=0, total=total_runs)
        return rows

    for n in node_counts:
        for graph_value in values:
            for colors in color_counts:
                for repeat in range(1, repeats + 1):
                    if cancel_requested(cancel_token):
                        emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled.", current=run_index, total=total_runs)
                        return rows

                    case_index += 1
                    seed_component = int(float(graph_value) * 100) if generation_mode in ("probability", "average_degree") else int(graph_value)
                    case_seed = None if seed is None else seed + repeat + n * 1000 + seed_component * 10 + colors
                    if generation_mode == "exact_edges":
                        case_label = f"Graph Coloring n{n}_m{int(graph_value)}_k{colors}"
                    elif generation_mode == "average_degree":
                        case_label = f"Graph Coloring n{n}_d{float(graph_value):g}_k{colors}"
                    else:
                        case_label = f"Graph Coloring n{n}_p{int(float(graph_value) * 100)}_k{colors}"
                    emit(
                        event_callback,
                        EVENT_LOG,
                        f"[{case_index}/{total_cases}] {case_label} repeat {repeat}",
                    )
                    emit(event_callback, EVENT_LOG, "   -> Generating CNF...")
                    if generation_mode == "exact_edges":
                        problem = exact_edges_graph_coloring_problem(n, int(graph_value), colors, seed=case_seed)
                    elif generation_mode == "average_degree":
                        problem = average_degree_graph_coloring_problem(n, float(graph_value), colors, seed=case_seed)
                    else:
                        problem = random_graph_coloring_problem(n, float(graph_value), colors, seed=case_seed)
                    emit(
                        event_callback,
                        EVENT_LOG,
                        _graph_generation_summary(problem),
                    )

                    run_index, should_continue = _run_case_solvers(
                        problem,
                        solvers,
                        repeat,
                        rows,
                        run_index,
                        total_runs,
                        event_callback,
                        cancel_token,
                        logging_options,
                        timeout_seconds,
                    )
                    if not should_continue:
                        return rows

    return rows


def run_hamiltonian_path_sweep(
    node_counts: Iterable[int],
    probabilities: Iterable[float] | None,
    solvers: Iterable[str],
    repeats: int,
    seed: int | None = None,
    edge_counts: Iterable[int] | None = None,
    generation_mode: str = "probability",
    event_callback=None,
    cancel_token: RunToken | None = None,
    average_degrees: Iterable[float] | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> list[BenchmarkRow]:
    return _run_graph_problem_sweep(
        "Hamiltonian Path",
        _hamiltonian_problem_for_mode,
        node_counts,
        probabilities,
        None,
        solvers,
        repeats,
        seed=seed,
        edge_counts=edge_counts,
        generation_mode=generation_mode,
        event_callback=event_callback,
        cancel_token=cancel_token,
        average_degrees=average_degrees,
        logging_options=logging_options,
        timeout_seconds=timeout_seconds,
    )


def run_independent_set_sweep(
    node_counts: Iterable[int],
    probabilities: Iterable[float] | None,
    target_sizes: Iterable[int],
    solvers: Iterable[str],
    repeats: int,
    seed: int | None = None,
    edge_counts: Iterable[int] | None = None,
    generation_mode: str = "probability",
    event_callback=None,
    cancel_token: RunToken | None = None,
    average_degrees: Iterable[float] | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> list[BenchmarkRow]:
    return _run_graph_problem_sweep(
        "Independent Set",
        _independent_set_problem_for_mode,
        node_counts,
        probabilities,
        list(target_sizes),
        solvers,
        repeats,
        seed=seed,
        edge_counts=edge_counts,
        generation_mode=generation_mode,
        event_callback=event_callback,
        cancel_token=cancel_token,
        average_degrees=average_degrees,
        logging_options=logging_options,
        timeout_seconds=timeout_seconds,
    )


def run_clique_sweep(
    node_counts: Iterable[int],
    probabilities: Iterable[float] | None,
    target_sizes: Iterable[int],
    solvers: Iterable[str],
    repeats: int,
    seed: int | None = None,
    edge_counts: Iterable[int] | None = None,
    generation_mode: str = "probability",
    event_callback=None,
    cancel_token: RunToken | None = None,
    average_degrees: Iterable[float] | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> list[BenchmarkRow]:
    return _run_graph_problem_sweep(
        "Clique",
        _clique_problem_for_mode,
        node_counts,
        probabilities,
        list(target_sizes),
        solvers,
        repeats,
        seed=seed,
        edge_counts=edge_counts,
        generation_mode=generation_mode,
        event_callback=event_callback,
        cancel_token=cancel_token,
        average_degrees=average_degrees,
        logging_options=logging_options,
        timeout_seconds=timeout_seconds,
    )


def run_graph_suite_sweep(
    node_counts: Iterable[int],
    probabilities: Iterable[float] | None,
    suite_problems: Iterable[str],
    solvers: Iterable[str],
    repeats: int,
    seed: int | None = None,
    target_sizes: Iterable[int] | None = None,
    color_counts: Iterable[int] | None = None,
    edge_counts: Iterable[int] | None = None,
    generation_mode: str = "probability",
    event_callback=None,
    cancel_token: RunToken | None = None,
    average_degrees: Iterable[float] | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> list[BenchmarkRow]:
    node_counts = list(node_counts)
    graph_values = _graph_values_for_mode(generation_mode, probabilities, edge_counts, average_degrees)
    suite_problems = list(suite_problems)
    solvers = list(solvers)
    target_sizes = list(target_sizes or [])
    color_counts = list(color_counts or [])
    _validate_graph_suite_inputs(suite_problems, target_sizes, color_counts)

    rows = []
    total_graph_cases = len(node_counts) * len(graph_values) * repeats
    case_problem_count = _graph_suite_problem_count(suite_problems, target_sizes, color_counts)
    total_runs = total_graph_cases * case_problem_count * len(solvers)
    case_index = 0
    run_index = 0

    if cancel_requested(cancel_token):
        emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled before start.", current=0, total=total_runs)
        return rows

    for node_count in node_counts:
        for graph_value in graph_values:
            graph_label = _graph_suite_label(node_count, graph_value, generation_mode)
            seed_component = int(float(graph_value) * 100) if generation_mode in ("probability", "average_degree") else int(graph_value)
            for repeat in range(1, repeats + 1):
                if cancel_requested(cancel_token):
                    emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled.", current=run_index, total=total_runs)
                    return rows

                case_index += 1
                case_seed = None if seed is None else seed + repeat + node_count * 1000 + seed_component * 10
                graph, graph_metadata = _graph_suite_graph(node_count, graph_value, generation_mode, case_seed)
                shared_graph_id = f"{graph_label}_r{repeat}"
                emit(event_callback, EVENT_LOG, f"[{case_index}/{total_graph_cases}] Graph Suite {shared_graph_id}")
                emit(event_callback, EVENT_LOG, "   -> Generating shared graph...")
                emit(event_callback, EVENT_LOG, _graph_generation_summary(_graph_suite_summary_problem(graph, graph_label, graph_metadata)))

                for problem in _graph_suite_problems(
                    graph,
                    graph_label,
                    shared_graph_id,
                    repeat,
                    suite_problems,
                    target_sizes,
                    color_counts,
                    graph_metadata,
                ):
                    emit(event_callback, EVENT_LOG, f"   -> Encoding {problem.name}...")
                    run_index, should_continue = _run_case_solvers(
                        problem,
                        solvers,
                        repeat,
                        rows,
                        run_index,
                        total_runs,
                        event_callback,
                        cancel_token,
                        logging_options,
                        timeout_seconds,
                    )
                    if not should_continue:
                        return rows

    return rows


def _graph_values_for_mode(
    generation_mode: str,
    probabilities: Iterable[float] | None,
    edge_counts: Iterable[int] | None,
    average_degrees: Iterable[float] | None,
) -> list:
    if generation_mode == "exact_edges":
        return list(edge_counts or [])
    if generation_mode == "average_degree":
        return list(average_degrees or [])
    return list(probabilities or [])


def _validate_graph_suite_inputs(suite_problems: list[str], target_sizes: list[int], color_counts: list[int]) -> None:
    valid = {"Graph Coloring", "Hamiltonian Path", "Independent Set", "Clique"}
    if not suite_problems:
        raise ValueError("Select at least one Graph Suite problem")
    unknown = [problem for problem in suite_problems if problem not in valid]
    if unknown:
        raise ValueError(f"Unknown Graph Suite problem: {unknown[0]}")
    if any(problem in suite_problems for problem in ("Independent Set", "Clique")) and not target_sizes:
        raise ValueError("Graph Suite target problems need at least one target k value")
    if "Graph Coloring" in suite_problems and not color_counts:
        raise ValueError("Graph Suite graph coloring needs at least one color count")


def _graph_suite_problem_count(suite_problems: list[str], target_sizes: list[int], color_counts: list[int]) -> int:
    total = 0
    if "Graph Coloring" in suite_problems:
        total += len(color_counts)
    if "Hamiltonian Path" in suite_problems:
        total += 1
    if "Independent Set" in suite_problems:
        total += len(target_sizes)
    if "Clique" in suite_problems:
        total += len(target_sizes)
    return total


def _graph_suite_label(node_count: int, graph_value, generation_mode: str) -> str:
    if generation_mode == "exact_edges":
        return f"n{node_count}_m{int(graph_value)}"
    if generation_mode == "average_degree":
        return f"n{node_count}_d{float(graph_value):g}"
    return f"n{node_count}_p{int(float(graph_value) * 100)}"


def _graph_suite_graph(node_count: int, graph_value, generation_mode: str, seed: int | None):
    import random

    rng = random.Random(seed) if seed is not None else random
    if generation_mode == "exact_edges":
        requested_edges = int(graph_value)
        graph = generate_random_graph_exact_edges(node_count, requested_edges, rng=rng)
        max_edges = node_count * (node_count - 1) // 2
        return graph, {
            "mode": "exact_edges",
            "requested_edges": requested_edges,
            "max_edges": max_edges,
            "edge_request_clamped": requested_edges > max_edges,
            "seed": seed,
        }
    if generation_mode == "average_degree":
        average_degree = float(graph_value)
        requested_edges = round(node_count * average_degree / 2)
        edges = edge_count_from_average_degree(node_count, average_degree)
        graph = generate_random_graph_exact_edges(node_count, edges, rng=rng)
        max_edges = node_count * (node_count - 1) // 2
        return graph, {
            "mode": "average_degree",
            "average_degree": average_degree,
            "requested_edges": requested_edges,
            "max_edges": max_edges,
            "edge_request_clamped": requested_edges > max_edges,
            "seed": seed,
        }

    probability = float(graph_value)
    graph = generate_random_graph(node_count, probability, rng=rng)
    return graph, {"mode": "probability", "probability": probability, "seed": seed}


def _graph_suite_summary_problem(graph, graph_label: str, graph_metadata: dict) -> ProblemInstance:
    metadata = {
        "nodes": len(graph),
        "edges": len(graph_edges(graph)),
        "graph_edges": graph_edges(graph),
        **graph_metadata,
    }
    return ProblemInstance(
        name=f"Graph Suite {graph_label}",
        problem_type="Graph Suite",
        clauses=[],
        metadata=metadata,
    )


def _apply_graph_suite_metadata(
    problem: ProblemInstance,
    graph_label: str,
    shared_graph_id: str,
    suite_problem: str,
    repeat: int,
    graph_metadata: dict,
) -> ProblemInstance:
    problem.metadata.update(graph_metadata)
    problem.metadata.update({
        "suite": True,
        "shared_graph_id": shared_graph_id,
        "suite_graph_label": graph_label,
        "suite_problem": suite_problem,
        "repeat": repeat,
    })
    return problem


def _graph_suite_problems(
    graph,
    graph_label: str,
    shared_graph_id: str,
    repeat: int,
    suite_problems: list[str],
    target_sizes: list[int],
    color_counts: list[int],
    graph_metadata: dict,
) -> list[ProblemInstance]:
    problems = []
    if "Graph Coloring" in suite_problems:
        for colors in color_counts:
            problem = graph_coloring_problem(
                graph,
                int(colors),
                name=f"Graph Suite {graph_label} Graph Coloring colors{int(colors)}",
            )
            problems.append(_apply_graph_suite_metadata(problem, graph_label, shared_graph_id, "Graph Coloring", repeat, graph_metadata))
    if "Hamiltonian Path" in suite_problems:
        problem = hamiltonian_path_problem(graph, name=f"Graph Suite {graph_label} Hamiltonian Path")
        problems.append(_apply_graph_suite_metadata(problem, graph_label, shared_graph_id, "Hamiltonian Path", repeat, graph_metadata))
    if "Independent Set" in suite_problems:
        for target in target_sizes:
            problem = independent_set_problem(
                graph,
                int(target),
                name=f"Graph Suite {graph_label} Independent Set k{int(target)}",
            )
            problems.append(_apply_graph_suite_metadata(problem, graph_label, shared_graph_id, "Independent Set", repeat, graph_metadata))
    if "Clique" in suite_problems:
        for target in target_sizes:
            problem = clique_problem(
                graph,
                int(target),
                name=f"Graph Suite {graph_label} Clique k{int(target)}",
            )
            problems.append(_apply_graph_suite_metadata(problem, graph_label, shared_graph_id, "Clique", repeat, graph_metadata))
    return problems


def _run_graph_problem_sweep(
    label: str,
    problem_builder,
    node_counts: Iterable[int],
    probabilities: Iterable[float] | None,
    target_values: list[int] | None,
    solvers: Iterable[str],
    repeats: int,
    seed: int | None = None,
    edge_counts: Iterable[int] | None = None,
    generation_mode: str = "probability",
    event_callback=None,
    cancel_token: RunToken | None = None,
    average_degrees: Iterable[float] | None = None,
    logging_options: dict | None = None,
    timeout_seconds: float | None = None,
) -> list[BenchmarkRow]:
    node_counts = list(node_counts)
    if generation_mode == "exact_edges":
        graph_values = list(edge_counts or [])
    elif generation_mode == "average_degree":
        graph_values = list(average_degrees or [])
    else:
        graph_values = list(probabilities or [])

    targets = target_values if target_values is not None else [None]
    solvers = list(solvers)
    rows = []
    total_cases = len(node_counts) * len(graph_values) * len(targets) * repeats
    total_runs = total_cases * len(solvers)
    case_index = 0
    run_index = 0

    if cancel_requested(cancel_token):
        emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled before start.", current=0, total=total_runs)
        return rows

    for node_count in node_counts:
        for graph_value in graph_values:
            for target in targets:
                for repeat in range(1, repeats + 1):
                    if cancel_requested(cancel_token):
                        emit(event_callback, EVENT_CANCELLED, "Benchmark cancelled.", current=run_index, total=total_runs)
                        return rows

                    case_index += 1
                    seed_component = int(float(graph_value) * 100) if generation_mode in ("probability", "average_degree") else int(graph_value)
                    case_seed = None if seed is None else seed + repeat + node_count * 1000 + seed_component * 10 + int(target or 0)
                    problem = problem_builder(node_count, graph_value, target, generation_mode, case_seed)
                    emit(event_callback, EVENT_LOG, f"[{case_index}/{total_cases}] {problem.name} repeat {repeat}")
                    emit(event_callback, EVENT_LOG, "   -> Generating CNF...")
                    emit(event_callback, EVENT_LOG, _graph_generation_summary(problem))

                    run_index, should_continue = _run_case_solvers(
                        problem,
                        solvers,
                        repeat,
                        rows,
                        run_index,
                        total_runs,
                        event_callback,
                        cancel_token,
                        logging_options,
                        timeout_seconds,
                    )
                    if not should_continue:
                        return rows

    return rows


def _hamiltonian_problem_for_mode(node_count, graph_value, _target, generation_mode, seed):
    if generation_mode == "exact_edges":
        return exact_edges_hamiltonian_path_problem(node_count, int(graph_value), seed=seed)
    if generation_mode == "average_degree":
        return average_degree_hamiltonian_path_problem(node_count, float(graph_value), seed=seed)
    return random_hamiltonian_path_problem(node_count, float(graph_value), seed=seed)


def _independent_set_problem_for_mode(node_count, graph_value, target, generation_mode, seed):
    if generation_mode == "exact_edges":
        return exact_edges_independent_set_problem(node_count, int(graph_value), int(target), seed=seed)
    if generation_mode == "average_degree":
        return average_degree_independent_set_problem(node_count, float(graph_value), int(target), seed=seed)
    return random_independent_set_problem(node_count, float(graph_value), int(target), seed=seed)


def _clique_problem_for_mode(node_count, graph_value, target, generation_mode, seed):
    if generation_mode == "exact_edges":
        return exact_edges_clique_problem(node_count, int(graph_value), int(target), seed=seed)
    if generation_mode == "average_degree":
        return average_degree_clique_problem(node_count, float(graph_value), int(target), seed=seed)
    return random_clique_problem(node_count, float(graph_value), int(target), seed=seed)


def _graph_generation_summary(problem: ProblemInstance) -> str:
    edges = problem.metadata.get("edges")
    requested_edges = problem.metadata.get("requested_edges")
    average_degree = problem.metadata.get("average_degree")
    if average_degree is not None:
        if problem.metadata.get("edge_request_clamped"):
            return (
                f"      Requested average degree: {average_degree:g} "
                f"({requested_edges} edges), Generated edges: {edges} "
                f"(complete graph), Clauses: {problem.clause_count}, Variables: {problem.variable_count}"
            )

        return (
            f"      Average degree: {average_degree:g}, Edges: {edges}, "
            f"Clauses: {problem.clause_count}, Variables: {problem.variable_count}"
        )

    if problem.metadata.get("edge_request_clamped"):
        return (
            f"      Requested edges: {requested_edges}, Generated edges: {edges} "
            f"(complete graph), Clauses: {problem.clause_count}, Variables: {problem.variable_count}"
        )

    return f"      Edges: {edges}, Clauses: {problem.clause_count}, Variables: {problem.variable_count}"


def _sudoku_generation_summary(problem: ProblemInstance) -> str:
    size = problem.metadata.get("size")
    givens = problem.metadata.get("givens")
    return f"      Size: {size}x{size}, Givens: {givens}, Clauses: {problem.clause_count}, Variables: {problem.variable_count}"


def _generic_generation_summary(problem: ProblemInstance) -> str:
    return f"      Clauses: {problem.clause_count}, Variables: {problem.variable_count}"


def _random_3sat_generation_summary(problem: ProblemInstance) -> str:
    sat_mix = ""
    if problem.metadata.get("mode") == "Random" and problem.metadata.get("sat_percentage") is not None:
        sat_mix = (
            f", SAT target: {problem.metadata.get('sat_percentage'):g}%, "
            f"Selected: {problem.metadata.get('selected_mode')}"
        )
    return (
        f"      Variables: {problem.metadata.get('variables')}, "
        f"Clauses: {problem.metadata.get('clauses_requested')}, "
        f"Ratio: {problem.metadata.get('ratio', 0):.2f}, "
        f"Mode: {problem.metadata.get('mode')}{sat_mix}"
    )


def write_benchmark_csv(path: str | Path, rows: list[BenchmarkRow]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(BENCHMARK_HEADERS)
        for row in rows:
            writer.writerow(row.as_csv_row())


def _random_3sat_sat_fraction(row: BenchmarkRow):
    metadata = row.problem_metadata
    if "preset_sat_fraction" in metadata:
        return metadata["preset_sat_fraction"]
    if metadata.get("mode") == "Planted SAT":
        return 1.0
    if metadata.get("mode") == "Forced UNSAT":
        return 0.0
    sat_percentage = metadata.get("sat_percentage")
    if sat_percentage is None:
        return ""
    return float(sat_percentage) / 100


def random_3sat_csv_row(row: BenchmarkRow) -> list:
    metadata = row.problem_metadata
    return [
        metadata.get("mode", ""),
        metadata.get("variables", ""),
        metadata.get("ratio", ""),
        metadata.get("clauses_requested", row.clauses),
        _random_3sat_sat_fraction(row),
        metadata.get("seed", row.seed),
        row.solver,
        row.status,
        f"{row.elapsed:.8f}",
        row.decisions,
        row.conflicts,
        row.propagations,
        row.learned_clauses,
        row.flips,
        row.tries,
        row.best_unsatisfied,
        row.timeout,
    ]


def write_random_3sat_benchmark_csv(path: str | Path, rows: list[BenchmarkRow]) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)

    with target.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle)
        writer.writerow(RANDOM_3SAT_CSV_HEADERS)
        for row in rows:
            writer.writerow(random_3sat_csv_row(row))
