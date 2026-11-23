import type { Interpreter } from "../api/types";

/** The interpreter a request runs on: PyPy only when it was chosen and the server has one (the catalog's `interpreters.pypy`). */
export function effectiveInterpreter(choice: Interpreter, pypyAvailable: boolean): Interpreter {
  return choice === "pypy" && pypyAvailable ? "pypy" : "python";
}

/**
 * The interpreter to preselect for a past job: its summary's `interpreter`, which the server derives
 * (recorded_interpreter in sat_core/jobs.py, the rule Rerun uses too). Null (no solver) means Python.
 */
export function interpreterOf(job: { interpreter: Interpreter | null | undefined }): Interpreter {
  return job.interpreter === "pypy" ? "pypy" : "python";
}
