from problems.dimacs_problem import dimacs_problem_from_text
from problems.clique import (
    average_degree_clique_problem,
    exact_edges_clique_problem,
    manual_clique_problem,
    random_clique_problem,
)
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


PROBLEM_TYPES = {
    "Sudoku": sudoku_problem,
    "Graph Coloring Manual": manual_graph_coloring_problem,
    "Graph Coloring Random": random_graph_coloring_problem,
    "Graph Coloring Exact Edges": exact_edges_graph_coloring_problem,
    "Graph Coloring Average Degree": average_degree_graph_coloring_problem,
    "N-Queens": n_queens_problem,
    "Random 3-SAT": random_3sat_problem,
    "Hamiltonian Path Manual": manual_hamiltonian_path_problem,
    "Hamiltonian Path Random": random_hamiltonian_path_problem,
    "Hamiltonian Path Exact Edges": exact_edges_hamiltonian_path_problem,
    "Hamiltonian Path Average Degree": average_degree_hamiltonian_path_problem,
    "Independent Set Manual": manual_independent_set_problem,
    "Independent Set Random": random_independent_set_problem,
    "Independent Set Exact Edges": exact_edges_independent_set_problem,
    "Independent Set Average Degree": average_degree_independent_set_problem,
    "Clique Manual": manual_clique_problem,
    "Clique Random": random_clique_problem,
    "Clique Exact Edges": exact_edges_clique_problem,
    "Clique Average Degree": average_degree_clique_problem,
    "DIMACS": dimacs_problem_from_text,
}
