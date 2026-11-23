import { SegmentedControl, Stack, Text } from "@mantine/core";
import { useId } from "react";
import type { Catalog, Interpreter } from "../api/types";
import { effectiveInterpreter } from "../lib/interpreter";

type PypyFacts = Catalog["interpreters"]["pypy"];

/**
 * "Run with: Python | PyPy" for one job (INTERP-3). The choice covers every run of the job.
 * The server says whether it found PyPy; without it the option is off and the text says how to install it.
 * The form does not remember the choice between visits: CPython stays the interpreter of reported results.
 */
export function InterpreterSwitch({ value, onChange, pypy }: { value: Interpreter; onChange: (choice: Interpreter) => void; pypy: PypyFacts }) {
  const labelId = useId();
  return (
    <Stack gap={4}>
      <Text size="sm" fw={500} id={labelId}>
        Run with
      </Text>
      <SegmentedControl
        aria-labelledby={labelId}
        value={effectiveInterpreter(value, pypy.available)}
        // A disabled option can still fire a change event (keyboard, assistive tools): never pass PyPy up when there is none.
        onChange={(choice) => (choice === "pypy" && !pypy.available ? undefined : onChange(choice as Interpreter))}
        data={[
          { value: "python", label: "Python" },
          { value: "pypy", label: pypy.available ? `PyPy ${pypy.version}` : "PyPy", disabled: !pypy.available },
        ]}
      />
      <Text size="xs" c="dimmed">
        {pypy.available
          ? "PyPy is faster on runs of several seconds and slower under about a second."
          : "PyPy not found. Install it from pypy.org, then add its folder to PATH or set WIZSAT_SOLVER_PYTHON, and restart the server."}
      </Text>
    </Stack>
  );
}
