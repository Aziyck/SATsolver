import type { Fact, RunEnvironment } from "../api/types";

const UNKNOWN = "unknown";

function cores(environment: RunEnvironment): string {
  const { cpu_physical_cores: physical, cpu_logical_cores: logical } = environment;
  if (logical === null) return physical === null ? UNKNOWN : `${physical} physical`;
  return physical === null ? `${logical} logical` : `${physical} physical, ${logical} logical`;
}

function version(environment: RunEnvironment): string {
  if (!environment.git_commit) return environment.wizsat_version;
  const dirty = environment.git_dirty ? " with uncommitted changes" : "";
  return `${environment.wizsat_version}, commit ${environment.git_commit}${dirty}`;
}

/** The machine and software a job ran on, as labelled lines for the Machine block. */
export function machineFacts(environment: RunEnvironment): Fact[] {
  return [
    { label: "Python", value: `${environment.python_implementation} ${environment.python_version}` },
    { label: "Operating system", value: environment.os ?? UNKNOWN },
    { label: "Processor", value: environment.cpu_model ?? UNKNOWN },
    { label: "Cores", value: cores(environment) },
    { label: "Memory", value: environment.ram_total_gb === null ? UNKNOWN : `${environment.ram_total_gb} GB` },
    { label: "WizSAT", value: version(environment) },
  ];
}
