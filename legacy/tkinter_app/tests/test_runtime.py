import unittest

from sat_core.benchmark import (
    run_clique_sweep,
    run_graph_coloring_sweep,
    run_graph_suite_sweep,
    run_hamiltonian_path_sweep,
    run_independent_set_sweep,
    run_n_queens_sweep,
    run_sudoku_sweep,
)
from sat_core.runtime import EVENT_CANCELLED, EVENT_LOG, EVENT_PROGRESS, EVENT_ROW, RunEvent, RunToken
from sat_core.solver_runner import solve_clauses


class RuntimeTests(unittest.TestCase):
    def test_run_event_serializes(self):
        event = RunEvent(EVENT_PROGRESS, "halfway", current=1, total=2)
        data = event.as_dict()

        self.assertEqual(data["type"], EVENT_PROGRESS)
        self.assertEqual(data["message"], "halfway")
        self.assertEqual(data["current"], 1)
        self.assertEqual(data["total"], 2)
        self.assertIn("created_at", data)

    def test_benchmark_emits_row_and_progress_events(self):
        events = []

        rows = run_graph_coloring_sweep(
            [3],
            [0.2],
            [2],
            ["CDCL"],
            repeats=1,
            seed=1,
            event_callback=events.append,
        )

        self.assertEqual(len(rows), 1)
        self.assertTrue(any(event.type == EVENT_ROW for event in events))
        self.assertTrue(any(event.type == EVENT_PROGRESS for event in events))

    def test_exact_edge_benchmark_emits_rows(self):
        rows = run_graph_coloring_sweep(
            [4],
            None,
            [2],
            ["CDCL"],
            repeats=1,
            edge_counts=[3],
            generation_mode="exact_edges",
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].generation_mode, "exact_edges")
        self.assertEqual(rows[0].edge_count, 3)

    def test_average_degree_benchmark_emits_rows(self):
        rows = run_graph_coloring_sweep(
            [4],
            None,
            [2],
            ["CDCL"],
            repeats=1,
            generation_mode="average_degree",
            average_degrees=[2],
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].generation_mode, "average_degree")
        self.assertEqual(rows[0].edge_count, 4)

    def test_sudoku_benchmark_emits_row_and_progress_events(self):
        events = []

        rows = run_sudoku_sweep([4], ["CDCL"], repeats=1, event_callback=events.append)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].problem_type, "Sudoku")
        self.assertEqual(rows[0].detail, "size=4, givens=8")
        self.assertTrue(any(event.type == EVENT_ROW for event in events))
        self.assertTrue(any(event.type == EVENT_PROGRESS for event in events))

    def test_sudoku_benchmark_rejects_unsupported_size(self):
        with self.assertRaises(ValueError):
            run_sudoku_sweep([5], ["CDCL"], repeats=1)

    def test_cancelled_sudoku_benchmark_before_start_returns_no_rows(self):
        events = []
        token = RunToken()
        token.cancel()

        rows = run_sudoku_sweep([4], ["CDCL"], repeats=1, event_callback=events.append, cancel_token=token)

        self.assertEqual(rows, [])
        self.assertTrue(any(event.type == EVENT_CANCELLED for event in events))

    def test_n_queens_benchmark_emits_row_and_progress_events(self):
        events = []

        rows = run_n_queens_sweep([4], ["CDCL"], repeats=1, event_callback=events.append)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].problem_type, "N-Queens")
        self.assertEqual(rows[0].detail, "n=4")
        self.assertTrue(any(event.type == EVENT_ROW for event in events))
        self.assertTrue(any(event.type == EVENT_PROGRESS for event in events))

    def test_hamiltonian_path_benchmark_emits_row_and_progress_events(self):
        events = []

        rows = run_hamiltonian_path_sweep([3], [1.0], ["CDCL"], repeats=1, event_callback=events.append)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].problem_type, "Hamiltonian Path")
        self.assertTrue(any(event.type == EVENT_ROW for event in events))
        self.assertTrue(any(event.type == EVENT_PROGRESS for event in events))

    def test_independent_set_benchmark_emits_row_and_progress_events(self):
        events = []

        rows = run_independent_set_sweep([3], [0.0], [2], ["CDCL"], repeats=1, event_callback=events.append)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].problem_type, "Independent Set")
        self.assertIn("k=2", rows[0].detail)
        self.assertTrue(any(event.type == EVENT_ROW for event in events))
        self.assertTrue(any(event.type == EVENT_PROGRESS for event in events))

    def test_clique_benchmark_emits_row_and_progress_events(self):
        events = []

        rows = run_clique_sweep([3], [1.0], [3], ["CDCL"], repeats=1, event_callback=events.append)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].problem_type, "Clique")
        self.assertIn("k=3", rows[0].detail)
        self.assertTrue(any(event.type == EVENT_ROW for event in events))
        self.assertTrue(any(event.type == EVENT_PROGRESS for event in events))

    def test_graph_suite_benchmark_emits_row_and_progress_events(self):
        events = []

        rows = run_graph_suite_sweep(
            [3],
            [1.0],
            ["Clique", "Independent Set"],
            ["CDCL"],
            repeats=1,
            target_sizes=[2],
            event_callback=events.append,
        )

        self.assertEqual(len(rows), 2)
        self.assertEqual({row.problem_type for row in rows}, {"Clique", "Independent Set"})
        self.assertEqual(len({row.problem_metadata["shared_graph_id"] for row in rows}), 1)
        self.assertTrue(any(event.type == EVENT_ROW for event in events))
        self.assertTrue(any(event.type == EVENT_PROGRESS for event in events))

    def test_new_benchmarks_validate_inputs(self):
        with self.assertRaises(ValueError):
            run_n_queens_sweep([0], ["CDCL"], repeats=1)
        with self.assertRaises(ValueError):
            run_independent_set_sweep([2], [0.0], [3], ["CDCL"], repeats=1)
        with self.assertRaises(ValueError):
            run_clique_sweep([2], [1.0], [3], ["CDCL"], repeats=1)

    def test_cancelled_n_queens_benchmark_before_start_returns_no_rows(self):
        events = []
        token = RunToken()
        token.cancel()

        rows = run_n_queens_sweep([4], ["CDCL"], repeats=1, event_callback=events.append, cancel_token=token)

        self.assertEqual(rows, [])
        self.assertTrue(any(event.type == EVENT_CANCELLED for event in events))

    def test_benchmark_solver_logging_options_are_forwarded(self):
        events = []

        run_n_queens_sweep(
            [4],
            ["CDCL"],
            repeats=1,
            event_callback=events.append,
            logging_options={"mode": "periodic", "progress_interval": 1},
        )
        messages = [event.message for event in events if event.type == EVENT_LOG]

        self.assertTrue(any("CDCL progress" in message for message in messages))

    def test_cancelled_benchmark_before_start_returns_no_rows(self):
        events = []
        token = RunToken()
        token.cancel()

        rows = run_graph_coloring_sweep(
            [3],
            [0.2],
            [2],
            ["CDCL"],
            repeats=1,
            event_callback=events.append,
            cancel_token=token,
        )

        self.assertEqual(rows, [])
        self.assertTrue(any(event.type == EVENT_CANCELLED for event in events))

    def test_cdcl_cancelled_before_start(self):
        token = RunToken()
        token.cancel()

        result = solve_clauses([[1]], "CDCL", cancel_token=token)

        self.assertEqual(result.status, "CANCELLED")

    def test_dpll_cancelled_before_start(self):
        token = RunToken()
        token.cancel()

        result = solve_clauses([[1]], "DPLL", cancel_token=token)

        self.assertEqual(result.status, "CANCELLED")

    def test_walksat_cancelled_before_start(self):
        token = RunToken()
        token.cancel()

        result = solve_clauses([[1]], "WalkSAT", cancel_token=token)

        self.assertEqual(result.status, "CANCELLED")

    def test_solver_timeout_before_start_returns_timeout(self):
        events = []

        result = solve_clauses([[1]], "CDCL", event_callback=events.append, timeout_seconds=0)
        messages = [event.message for event in events if event.type == EVENT_LOG]

        self.assertEqual(result.status, "TIMEOUT")
        self.assertTrue(any("timed out" in message for message in messages))

    def test_benchmark_timeout_records_row_and_continues(self):
        events = []

        rows = run_n_queens_sweep([4], ["CDCL"], repeats=1, event_callback=events.append, timeout_seconds=0)

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0].status, "TIMEOUT")
        self.assertTrue(any(event.type == EVENT_ROW for event in events))

    def test_solver_skip_before_start_returns_skipped(self):
        token = RunToken()
        token.skip()

        result = solve_clauses([[1]], "CDCL", cancel_token=token)

        self.assertEqual(result.status, "SKIPPED")

    def test_benchmark_skip_marks_current_case_and_continues(self):
        token = RunToken()
        token.skip()

        rows = run_n_queens_sweep([4, 4], ["CDCL"], repeats=1, cancel_token=token)

        self.assertEqual(len(rows), 2)
        self.assertEqual(rows[0].status, "SKIPPED")
        self.assertEqual(rows[1].status, "SAT")

    def test_cdcl_normal_logging_emits_start_finish_and_stats(self):
        events = []

        result = solve_clauses([[1]], "CDCL", event_callback=events.append)
        messages = [event.message for event in events if event.type == EVENT_LOG]

        self.assertEqual(result.status, "SAT")
        self.assertTrue(any("Solving with CDCL" in message for message in messages))
        self.assertTrue(any("CDCL finished" in message for message in messages))
        self.assertTrue(any("CDCL stats" in message for message in messages))

    def test_cdcl_periodic_logging_emits_progress(self):
        events = []

        solve_clauses(
            [[1, 2], [-1, 2]],
            "CDCL",
            event_callback=events.append,
            logging_options={"mode": "periodic", "progress_interval": 1},
        )
        messages = [event.message for event in events if event.type == EVENT_LOG]

        self.assertTrue(any("CDCL progress" in message for message in messages))

    def test_dpll_debug_logging_emits_debug_messages(self):
        events = []

        result = solve_clauses(
            [[1, 2], [-1, 2]],
            "DPLL",
            event_callback=events.append,
            logging_options={"mode": "debug", "progress_interval": 1, "verbose_limit": 5},
        )
        messages = [event.message for event in events if event.type == EVENT_LOG]

        self.assertEqual(result.status, "SAT")
        self.assertTrue(any("DPLL debug" in message for message in messages))
        self.assertTrue(any("DPLL stats" in message for message in messages))


if __name__ == "__main__":
    unittest.main()
