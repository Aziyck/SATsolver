import { Badge, Loader, type MantineColor } from "@mantine/core";
import {
  IconAlertTriangle,
  IconBan,
  IconCircleCheck,
  IconCircleX,
  IconClock,
  IconHelpCircle,
  IconPlayerSkipForward,
  IconPlayerStop,
} from "@tabler/icons-react";
import type { JobStatus, RunStatus } from "../api/types";

/** Solver answers. SAT/UNSAT are both correct outcomes, so neither is "green". */
export const RUN_STATUS: Record<RunStatus, { color: MantineColor; label: string; description: string }> = {
  SAT: { color: "blue", label: "SAT", description: "A satisfying assignment was found (and checked)." },
  UNSAT: { color: "orange", label: "UNSAT", description: "Proved that no assignment satisfies the formula." },
  UNKNOWN: { color: "teal", label: "UNKNOWN", description: "Stopped without an answer (local search cannot prove UNSAT)." },
  TIMEOUT: { color: "yellow", label: "TIMEOUT", description: "The time limit was reached." },
  CANCELLED: { color: "gray", label: "CANCELLED", description: "Stopped by you." },
  SKIPPED: { color: "gray", label: "SKIPPED", description: "Not run (skipped by you or by a limit rule)." },
  ERROR: { color: "red", label: "ERROR", description: "The solver or the encoder failed." },
};

export function RunStatusBadge({ status, size = "sm" }: { status: RunStatus | null | undefined; size?: "xs" | "sm" | "md" | "lg" | "xl" }) {
  if (!status) return null;
  const info = RUN_STATUS[status];
  return (
    <Badge color={info.color} variant="light" size={size} title={info.description} radius="sm">
      {info.label}
    </Badge>
  );
}

const JOB_STATUS: Record<JobStatus, { color: MantineColor; label: string; icon: React.ReactNode }> = {
  queued: { color: "gray", label: "Queued", icon: <IconClock size={12} /> },
  running: { color: "violet", label: "Running", icon: <Loader size={10} color="violet" /> },
  cancelling: { color: "violet", label: "Stopping", icon: <Loader size={10} color="violet" /> },
  done: { color: "green", label: "Done", icon: <IconCircleCheck size={12} /> },
  failed: { color: "red", label: "Failed", icon: <IconCircleX size={12} /> },
  cancelled: { color: "gray", label: "Cancelled", icon: <IconPlayerStop size={12} /> },
  interrupted: { color: "yellow", label: "Interrupted", icon: <IconAlertTriangle size={12} /> },
};

export function JobStatusBadge({ status }: { status: JobStatus }) {
  const info = JOB_STATUS[status];
  return (
    <Badge color={info.color} variant="light" leftSection={info.icon} radius="sm">
      {info.label}
    </Badge>
  );
}

export function isActive(status: JobStatus): boolean {
  return status === "queued" || status === "running" || status === "cancelling";
}

export const STATUS_ICONS: Record<string, React.ReactNode> = {
  SKIPPED: <IconPlayerSkipForward size={14} />,
  CANCELLED: <IconBan size={14} />,
  UNKNOWN: <IconHelpCircle size={14} />,
};
