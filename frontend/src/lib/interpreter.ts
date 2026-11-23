import type { Interpreter, RunEnvironment } from "../api/types";

/** The interpreter a request runs on: PyPy only when it was chosen and the server has one (the catalog's `interpreters.pypy`). */
export function effectiveInterpreter(choice: Interpreter, pypyAvailable: boolean): Interpreter {
  return choice === "pypy" && pypyAvailable ? "pypy" : "python";
}

/**
 * The interpreter a past job chose. Jobs saved before the field existed have none in their request:
 * they ran on PyPy when their environment record says so, the same rule as the server's Rerun
 * (with_recorded_interpreter in sat_web/api.py).
 */
export function interpreterOf(request: { interpreter?: Interpreter }, environment?: RunEnvironment | null): Interpreter {
  if (request.interpreter) return request.interpreter === "pypy" ? "pypy" : "python";
  return environment?.python_implementation === "PyPy" ? "pypy" : "python";
}
