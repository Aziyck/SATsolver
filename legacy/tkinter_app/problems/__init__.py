from problems.dimacs_problem import dimacs_problem_from_text
from problems.clique import (
    average_degree_clique_problem,
    clique_problem,
    clique_var,
    exact_edges_clique_problem,
    manual_clique_problem,
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
    manual_hamiltonian_path_problem,
    random_hamiltonian_path_problem,
)
from problems.independent_set import (
    average_degree_independent_set_problem,
    exact_edges_independent_set_problem,
    independent_set_problem,
    manual_independent_set_problem,
    random_independent_set_problem,
)
from problems.n_queens import n_queens_problem
from problems.random_3sat import random_3sat_problem
from problems.sudoku import sudoku_problem

__all__ = [
    "average_degree_hamiltonian_path_problem",
    "average_degree_independent_set_problem",
    "average_degree_clique_problem",
    "average_degree_graph_coloring_problem",
    "clique_problem",
    "clique_var",
    "dimacs_problem_from_text",
    "edge_count_from_average_degree",
    "exact_edges_hamiltonian_path_problem",
    "exact_edges_independent_set_problem",
    "exact_edges_clique_problem",
    "exact_edges_graph_coloring_problem",
    "graph_coloring_problem",
    "hamiltonian_path_problem",
    "independent_set_problem",
    "manual_clique_problem",
    "manual_hamiltonian_path_problem",
    "manual_independent_set_problem",
    "n_queens_problem",
    "random_hamiltonian_path_problem",
    "random_independent_set_problem",
    "random_clique_problem",
    "random_graph_coloring_problem",
    "random_3sat_problem",
    "sudoku_problem",
]
