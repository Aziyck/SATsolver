import { describe, expect, it } from "vitest";
import type { RunEnvironment } from "../api/types";
import { machineFacts } from "./environment";

const FULL: RunEnvironment = {
  python_implementation: "CPython",
  python_version: "3.12.0",
  os: "Linux 6.8.0 (x86_64)",
  cpu_model: "AMD Ryzen 7 4800H",
  cpu_logical_cores: 16,
  cpu_physical_cores: 8,
  ram_total_gb: 15.4,
  wizsat_version: "2.0.0",
  git_commit: "75c0c05",
  git_dirty: false,
};

const byLabel = (environment: RunEnvironment) => Object.fromEntries(machineFacts(environment).map((fact) => [fact.label, fact.value]));

describe("machineFacts", () => {
  it("names the interpreter, the CPU, the cores, the memory and the commit", () => {
    expect(byLabel(FULL)).toEqual({
      Python: "CPython 3.12.0",
      "Operating system": "Linux 6.8.0 (x86_64)",
      Processor: "AMD Ryzen 7 4800H",
      Cores: "8 physical, 16 logical",
      Memory: "15.4 GB",
      WizSAT: "2.0.0, commit 75c0c05",
    });
  });

  it("says when the commit had uncommitted changes", () => {
    expect(byLabel({ ...FULL, git_dirty: true }).WizSAT).toBe("2.0.0, commit 75c0c05 with uncommitted changes");
  });

  it("gives only the version when the code is not a git checkout", () => {
    expect(byLabel({ ...FULL, git_commit: null, git_dirty: null }).WizSAT).toBe("2.0.0");
  });

  it("writes a fact that could not be read as unknown", () => {
    const facts = byLabel({ ...FULL, os: null, cpu_model: null, cpu_logical_cores: null, cpu_physical_cores: null, ram_total_gb: null });
    expect(facts["Operating system"]).toBe("unknown");
    expect(facts.Processor).toBe("unknown");
    expect(facts.Cores).toBe("unknown");
    expect(facts.Memory).toBe("unknown");
  });

  it("gives the logical cores alone when the physical ones are not known", () => {
    expect(byLabel({ ...FULL, cpu_physical_cores: null }).Cores).toBe("16 logical");
  });
});
