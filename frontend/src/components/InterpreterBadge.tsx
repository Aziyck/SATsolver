import { Badge } from "@mantine/core";
import type { Interpreter } from "../api/types";

/**
 * A "PyPy" mark for a job set to run its solvers on PyPy (INTERP-4): the job's choice. What really ran
 * is in the job's Machine block (its environment record). Python, the default, needs no mark.
 */
export function InterpreterBadge({ interpreter }: { interpreter: Interpreter | null }) {
  if (interpreter !== "pypy") return null;
  return (
    <Badge variant="outline" color="gray" radius="sm" title="This job was set to run its solvers on PyPy">
      PyPy
    </Badge>
  );
}
