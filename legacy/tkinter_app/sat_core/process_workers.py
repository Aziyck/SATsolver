from __future__ import annotations

from problems.clique import (
    average_degree_clique_problem,
    exact_edges_clique_problem,
    manual_clique_problem,
    random_clique_problem,
)
from problems.dimacs_problem import dimacs_problem_from_text
from problems.graph_coloring import (
    average_degree_graph_coloring_problem,
    exact_edges_graph_coloring_problem,
    manual_graph_coloring_problem,
    random_graph_coloring_problem,
)
from problems.hamiltonian_path import (
    average_degree_hamiltonian_path_problem,
    exact_edges_hamiltonian_path_problem,
    manual_hamiltonian_path_problem,
    random_hamiltonian_path_problem,
)
from problems.independent_set import (
    average_degree_independent_set_problem,
    exact_edges_independent_set_problem,
    manual_independent_set_problem,
    random_independent_set_problem,
)
from problems.n_queens import n_queens_problem
from problems.random_3sat import random_3sat_problem
from problems.sudoku import sudoku_problem
from sat_core.benchmark import (
    run_clique_sweep,
    run_graph_coloring_sweep,
    run_graph_suite_sweep,
    run_hamiltonian_path_sweep,
    run_independent_set_sweep,
    run_n_queens_sweep,
    run_random_3sat_preset,
    run_random_3sat_sweep,
    run_sudoku_sweep,
)
from sat_core.dimacs import clauses_to_dimacs
from sat_core.models import ProblemInstance
from sat_core.benchmark_presets.random_3sat_presets import RANDOM_3SAT_PRESET_CUSTOM
from sat_core.runtime import EVENT_CNF, EVENT_LOG, EVENT_PROGRESS, EVENT_RESULT, RunEvent, RunToken
from sat_core.solver_runner import solve_problem


def _problem_payload(problem: ProblemInstance) -> dict:
    return {
        "name": problem.name,
        "problem_type": problem.problem_type,
        "clauses": problem.clauses,
        "metadata": problem.metadata,
    }


def problem_from_snapshot(snapshot: dict) -> ProblemInstance:
    kind = snapshot["kind"]

    if kind == "Sudoku":
        return sudoku_problem(snapshot["grid"])

    if kind == "N-Queens":
        return n_queens_problem(snapshot["size"])

    if kind == "Random 3-SAT":
        return random_3sat_problem(
            snapshot["variables"],
            snapshot["clauses"],
            seed=snapshot["seed"],
            planted=snapshot.get("planted", True),
            formula_mode=snapshot.get("formula_mode"),
            sat_percentage=snapshot.get("sat_percentage"),
        )

    if kind == "Graph Coloring":
        if snapshot["mode"] == "Probability":
            return random_graph_coloring_problem(
                snapshot["nodes"],
                snapshot["probability"],
                snapshot["colors"],
                seed=snapshot["seed"],
            )

        if snapshot["mode"] == "Exact edges":
            return exact_edges_graph_coloring_problem(
                snapshot["nodes"],
                snapshot["edge_count"],
                snapshot["colors"],
                seed=snapshot["seed"],
            )

        if snapshot["mode"] == "Average degree":
            return average_degree_graph_coloring_problem(
                snapshot["nodes"],
                snapshot["average_degree"],
                snapshot["colors"],
                seed=snapshot["seed"],
            )

        return manual_graph_coloring_problem(snapshot["nodes"], snapshot["colors"], snapshot["edge_text"])

    if kind == "Hamiltonian Path":
        if snapshot["mode"] == "Probability":
            return random_hamiltonian_path_problem(snapshot["nodes"], snapshot["probability"], seed=snapshot["seed"])
        if snapshot["mode"] == "Exact edges":
            return exact_edges_hamiltonian_path_problem(snapshot["nodes"], snapshot["edge_count"], seed=snapshot["seed"])
        if snapshot["mode"] == "Average degree":
            return average_degree_hamiltonian_path_problem(snapshot["nodes"], snapshot["average_degree"], seed=snapshot["seed"])
        return manual_hamiltonian_path_problem(snapshot["nodes"], snapshot["edge_text"])

    if kind == "Independent Set":
        if snapshot["mode"] == "Probability":
            return random_independent_set_problem(snapshot["nodes"], snapshot["probability"], snapshot["target"], seed=snapshot["seed"])
        if snapshot["mode"] == "Exact edges":
            return exact_edges_independent_set_problem(snapshot["nodes"], snapshot["edge_count"], snapshot["target"], seed=snapshot["seed"])
        if snapshot["mode"] == "Average degree":
            return average_degree_independent_set_problem(snapshot["nodes"], snapshot["average_degree"], snapshot["target"], seed=snapshot["seed"])
        return manual_independent_set_problem(snapshot["nodes"], snapshot["target"], snapshot["edge_text"])

    if kind == "Clique":
        if snapshot["mode"] == "Probability":
            return random_clique_problem(snapshot["nodes"], snapshot["probability"], snapshot["target"], seed=snapshot["seed"])
        if snapshot["mode"] == "Exact edges":
            return exact_edges_clique_problem(snapshot["nodes"], snapshot["edge_count"], snapshot["target"], seed=snapshot["seed"])
        if snapshot["mode"] == "Average degree":
            return average_degree_clique_problem(snapshot["nodes"], snapshot["average_degree"], snapshot["target"], seed=snapshot["seed"])
        return manual_clique_problem(snapshot["nodes"], snapshot["target"], snapshot["edge_text"])

    return dimacs_problem_from_text(
        snapshot["text"],
        problem_type=snapshot.get("loaded_problem_type", "DIMACS"),
    )


def _emit(queue, event: RunEvent) -> None:
    queue.put(event)


def _problem_summary(problem: ProblemInstance) -> str:
    base = f"Generated {problem.name}: {problem.clause_count} clauses, {problem.variable_count} variables"
    if problem.problem_type == "Sudoku":
        return f"{base}, size {problem.metadata.get('size')}x{problem.metadata.get('size')}, givens {problem.metadata.get('givens')}"
    if problem.problem_type == "N-Queens":
        return f"{base}, size {problem.metadata.get('size')}"
    if problem.problem_type == "Random 3-SAT":
        return (
            f"{base}, variables {problem.metadata.get('variables')}, "
            f"clauses {problem.metadata.get('clauses_requested')}, "
            f"ratio {problem.metadata.get('ratio'):.2f}, "
            f"mode {problem.metadata.get('mode')}, "
            f"selected {problem.metadata.get('selected_mode')}"
        )
    if problem.problem_type in ("Independent Set", "Clique"):
        return f"{base}, target k {problem.metadata.get('target')}, edges {problem.metadata.get('edges')}"
    if problem.problem_type not in ("Graph Coloring", "Hamiltonian Path"):
        return base

    requested_edges = problem.metadata.get("requested_edges")
    actual_edges = problem.metadata.get("edges")
    average_degree = problem.metadata.get("average_degree")
    if average_degree is not None:
        if problem.metadata.get("edge_request_clamped"):
            return f"{base}, average degree {average_degree:g}, requested edges {requested_edges}, actual edges {actual_edges}"
        return f"{base}, average degree {average_degree:g}, edges {actual_edges}"
    if problem.metadata.get("edge_request_clamped"):
        return f"{base}, requested edges {requested_edges}, actual edges {actual_edges}"
    if actual_edges is not None:
        return f"{base}, edges {actual_edges}"
    return base


def generate_cnf_process(snapshot: dict, event_queue, cancel_event) -> None:
    token = RunToken(cancel_event)
    token.raise_if_cancelled()

    _emit(event_queue, RunEvent(EVENT_LOG, "Generating CNF..."))
    problem = problem_from_snapshot(snapshot)
    dimacs = clauses_to_dimacs(
        problem.clauses,
        [
            problem.name,
            f"type={problem.problem_type}",
            f"variables={problem.variable_count}",
        ],
    )

    _emit(event_queue, RunEvent(EVENT_LOG, _problem_summary(problem)))
    _emit(
        event_queue,
        RunEvent(
            EVENT_CNF,
            payload={
                "problem": _problem_payload(problem),
                "dimacs": dimacs,
            },
        ),
    )
    _emit(event_queue, RunEvent(EVENT_PROGRESS, "CNF generated", current=1, total=1))


def solve_process(
    snapshot: dict,
    solver_name: str,
    logging_options: dict | None,
    timeout_seconds: float | None,
    event_queue,
    cancel_event,
) -> None:
    token = RunToken(cancel_event)
    token.raise_if_cancelled()

    _emit(event_queue, RunEvent(EVENT_LOG, "Generating CNF..."))
    problem = problem_from_snapshot(snapshot)
    dimacs = clauses_to_dimacs(
        problem.clauses,
        [
            problem.name,
            f"type={problem.problem_type}",
            f"variables={problem.variable_count}",
        ],
    )

    _emit(event_queue, RunEvent(EVENT_LOG, _problem_summary(problem)))
    _emit(event_queue, RunEvent(EVENT_CNF, payload={"problem": _problem_payload(problem), "dimacs": dimacs}))

    result = solve_problem(
        problem,
        solver_name,
        event_callback=lambda event: _emit(event_queue, event),
        cancel_token=token,
        logging_options=logging_options,
        timeout_seconds=timeout_seconds,
    )

    if result.status == "CANCELLED":
        token.cancel()
        return

    _emit(event_queue, RunEvent(EVENT_RESULT, payload={"result": result}))
    _emit(event_queue, RunEvent(EVENT_PROGRESS, "Solve complete", current=1, total=1))


def benchmark_process(params: dict, skip_event, event_queue, cancel_event) -> None:
    token = RunToken(cancel_event, skip_event=skip_event)
    token.raise_if_cancelled()

    if params.get("problem_type") == "Sudoku":
        run_sudoku_sweep(
            params["sizes"],
            params["solvers"],
            params["repeats"],
            event_callback=lambda event: _emit(event_queue, event),
            cancel_token=token,
            logging_options=params.get("logging_options"),
            timeout_seconds=params.get("timeout_seconds"),
        )
    elif params.get("problem_type") == "N-Queens":
        run_n_queens_sweep(
            params["sizes"],
            params["solvers"],
            params["repeats"],
            event_callback=lambda event: _emit(event_queue, event),
            cancel_token=token,
            logging_options=params.get("logging_options"),
            timeout_seconds=params.get("timeout_seconds"),
        )
    elif params.get("problem_type") == "Random 3-SAT":
        preset_name = params.get("preset_name", RANDOM_3SAT_PRESET_CUSTOM)
        if preset_name != RANDOM_3SAT_PRESET_CUSTOM:
            run_random_3sat_preset(
                preset_name,
                params["solvers"],
                event_callback=lambda event: _emit(event_queue, event),
                cancel_token=token,
                logging_options=params.get("logging_options"),
                timeout_seconds=params.get("timeout_seconds"),
            )
        else:
            run_random_3sat_sweep(
                params["variable_counts"],
                params["clause_ratios"],
                params["solvers"],
                params["repeats"],
                seed=params.get("seed"),
                planted=params.get("planted", True),
                formula_mode=params.get("formula_mode"),
                sat_percentage=params.get("sat_percentage"),
                event_callback=lambda event: _emit(event_queue, event),
                cancel_token=token,
                logging_options=params.get("logging_options"),
                timeout_seconds=params.get("timeout_seconds"),
            )
    elif params.get("problem_type") == "Hamiltonian Path":
        run_hamiltonian_path_sweep(
            params["node_counts"],
            params["probabilities"],
            params["solvers"],
            params["repeats"],
            seed=params["seed"],
            edge_counts=params.get("edge_counts"),
            generation_mode=params.get("generation_mode", "probability"),
            event_callback=lambda event: _emit(event_queue, event),
            cancel_token=token,
            average_degrees=params.get("average_degrees"),
            logging_options=params.get("logging_options"),
            timeout_seconds=params.get("timeout_seconds"),
        )
    elif params.get("problem_type") == "Independent Set":
        run_independent_set_sweep(
            params["node_counts"],
            params["probabilities"],
            params["target_sizes"],
            params["solvers"],
            params["repeats"],
            seed=params["seed"],
            edge_counts=params.get("edge_counts"),
            generation_mode=params.get("generation_mode", "probability"),
            event_callback=lambda event: _emit(event_queue, event),
            cancel_token=token,
            average_degrees=params.get("average_degrees"),
            logging_options=params.get("logging_options"),
            timeout_seconds=params.get("timeout_seconds"),
        )
    elif params.get("problem_type") == "Clique":
        run_clique_sweep(
            params["node_counts"],
            params["probabilities"],
            params["target_sizes"],
            params["solvers"],
            params["repeats"],
            seed=params["seed"],
            edge_counts=params.get("edge_counts"),
            generation_mode=params.get("generation_mode", "probability"),
            event_callback=lambda event: _emit(event_queue, event),
            cancel_token=token,
            average_degrees=params.get("average_degrees"),
            logging_options=params.get("logging_options"),
            timeout_seconds=params.get("timeout_seconds"),
        )
    elif params.get("problem_type") == "Graph Suite":
        run_graph_suite_sweep(
            params["node_counts"],
            params["probabilities"],
            params["suite_problems"],
            params["solvers"],
            params["repeats"],
            seed=params["seed"],
            target_sizes=params.get("target_sizes"),
            color_counts=params.get("color_counts"),
            edge_counts=params.get("edge_counts"),
            generation_mode=params.get("generation_mode", "probability"),
            event_callback=lambda event: _emit(event_queue, event),
            cancel_token=token,
            average_degrees=params.get("average_degrees"),
            logging_options=params.get("logging_options"),
            timeout_seconds=params.get("timeout_seconds"),
        )
    else:
        run_graph_coloring_sweep(
            params["node_counts"],
            params["probabilities"],
            params["color_counts"],
            params["solvers"],
            params["repeats"],
            seed=params["seed"],
            edge_counts=params.get("edge_counts"),
            generation_mode=params.get("generation_mode", "probability"),
            event_callback=lambda event: _emit(event_queue, event),
            cancel_token=token,
            average_degrees=params.get("average_degrees"),
            logging_options=params.get("logging_options"),
            timeout_seconds=params.get("timeout_seconds"),
        )
