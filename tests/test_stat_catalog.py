"""The catalog of solver statistics (ARCH-2): every key a solver reports is declared once."""

import unittest

from sat_core import export
from sat_core.solver_registry import STAT_SPECS, all_solvers, run_solver, stats_summary

SAT = [[1, 2], [-1, 2]]
UNSAT = [[1], [-1]]
# Pigeons: three need a hole each in two holes, a small formula where CDCL really learns and DPLL backtracks.
PIGEONS = [[1, 2], [3, 4], [5, 6], [-1, -3], [-1, -5], [-3, -5], [-2, -4], [-2, -6], [-4, -6]]


def option_variants(spec):
    """The defaults, and every boolean option flipped (adaptive noise adds statistics of its own)."""

    defaults = spec.default_options()
    variants = [{}]
    for field in spec.fields:
        if field.kind == "bool":
            variants.append({field.name: not defaults[field.name]})
    return variants


class CatalogTests(unittest.TestCase):
    def test_every_statistic_a_solver_reports_is_in_the_catalog(self):
        declared = {spec.key for spec in STAT_SPECS}
        for solver in all_solvers():
            for options in option_variants(solver):
                for name, clauses in (("sat", SAT), ("unsat", UNSAT), ("pigeons", PIGEONS)):
                    with self.subTest(solver=solver.key, options=options, formula=name):
                        result = run_solver(clauses, solver.key, options, timeout=5)
                        self.assertEqual(set(result.stats) - declared, set())

    def test_keys_are_unique_and_every_entry_is_described(self):
        keys = [spec.key for spec in STAT_SPECS]
        self.assertEqual(len(keys), len(set(keys)))
        for spec in STAT_SPECS:
            with self.subTest(key=spec.key):
                self.assertTrue(spec.label)
                self.assertTrue(spec.help)

    def test_the_job_memory_statistics_are_declared_and_say_what_they_measure(self):
        # Reported by solve_job (MEM-2), not by a solver; the CSV and chart flags come with MEM-6.
        specs = {spec.key: spec for spec in STAT_SPECS}
        for key, words in (("peak_memory_mb", "job"), ("baseline_memory_mb", "encoding")):
            with self.subTest(key=key):
                self.assertIn(key, specs)
                self.assertEqual(specs[key].unit, "MiB")
                self.assertIn(words, (specs[key].label + " " + specs[key].help).lower())
                self.assertFalse(specs[key].csv or specs[key].chart)

    def test_csv_columns_are_the_csv_entries_in_catalog_order(self):
        self.assertEqual(
            export.STAT_COLUMNS,
            (
                "decisions",
                "conflicts",
                "propagations",
                "learned_clauses",
                "restarts",
                "tries",
                "flips",
                "best_unsatisfied",
            ),
        )
        self.assertEqual(export.STAT_COLUMNS, tuple(spec.key for spec in STAT_SPECS if spec.csv))

    def test_summary_lists_the_entries_with_a_short_name_in_catalog_order(self):
        stats = {
            "decisions": 1,
            "conflicts": 2,
            "propagations": 3,
            "learned_clauses": 4,
            "active_learned_clauses": 99,
            "deleted_learned_clauses": 5,
            "avg_lbd": 2.5,
            "restarts": 6,
            "reductions": 7,
            "max_depth": 8,
            "tries": 9,
            "flips": 10,
            "best_unsatisfied": 0,
            "termination_reason": "found",
            "final_noise": 0.5,
            "free_flips": 11,
            "noise_flips": 12,
            "greedy_flips": 13,
            "elapsed": 1.5,
            "last_break": None,
        }
        self.assertEqual(
            stats_summary(stats),
            "decisions=1, conflicts=2, propagations=3, learned=4, deleted learned=5, avg LBD=2.5, restarts=6, "
            "cleanups=7, max depth=8, tries=9, flips=10, best unsatisfied=0, reason=found, final noise=0.5, "
            "free=11, noise=12, greedy=13",
        )

    def test_a_statistic_nobody_declared_is_left_out_of_the_summary(self):
        self.assertEqual(stats_summary({"conflicts": 2, "made_up": 5}), "conflicts=2")


if __name__ == "__main__":
    unittest.main()
