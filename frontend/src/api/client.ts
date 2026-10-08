import type {
  BenchmarkRequest,
  BenchmarkRow,
  Catalog,
  JobDetail,
  JobKind,
  JobSummary,
  LogLine,
  PlanSummary,
  PreviewResponse,
  RowCase,
} from "./types";

/** An API failure. `errors` maps field names (e.g. "nodes", "segments.0.ratio") to messages. */
export class ApiError extends Error {
  status: number;
  errors: Record<string, string>;

  constructor(status: number, message: string, errors: Record<string, string> = {}) {
    super(message);
    this.status = status;
    this.errors = errors;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response;
  try {
    response = await fetch(path, {
      ...init,
      headers: { "content-type": "application/json", ...(init?.headers ?? {}) },
    });
  } catch {
    throw new ApiError(0, "Cannot reach the WizSAT server. Is it still running?");
  }
  if (response.status === 204) {
    return undefined as T;
  }
  const text = await response.text();
  const data = text ? safeJson(text) : null;
  if (!response.ok) {
    const record = (data ?? {}) as { message?: string; errors?: Record<string, string>; detail?: unknown };
    const message =
      record.message ?? (typeof record.detail === "string" ? record.detail : `Request failed (${response.status})`);
    throw new ApiError(response.status, message, record.errors ?? {});
  }
  return data as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return { message: text };
  }
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });

export const api = {
  catalog: () => request<Catalog>("/api/catalog"),
  preview: (problem: string, params: Record<string, unknown>) =>
    post<PreviewResponse>(`/api/problems/${problem}/preview`, { params }),
  plan: (benchmark: BenchmarkRequest) => post<PlanSummary>("/api/benchmarks/plan", { request: benchmark }),
  jobs: () => request<{ jobs: JobSummary[] }>("/api/jobs").then((data) => data.jobs),
  job: (id: number) => request<JobDetail>(`/api/jobs/${id}`),
  rows: (id: number) => request<{ job_id: number; label: string; rows: BenchmarkRow[] }>(`/api/jobs/${id}/rows`),
  logs: (id: number) => request<{ logs: LogLine[] }>(`/api/jobs/${id}/logs`).then((data) => data.logs),
  createJob: (kind: JobKind, body: unknown, title?: string) =>
    post<JobSummary>("/api/jobs", { kind, request: body, title }),
  cancel: (id: number) => post<JobSummary>(`/api/jobs/${id}/cancel`),
  skip: (id: number) => post<JobSummary>(`/api/jobs/${id}/skip`),
  rerun: (id: number) => post<JobSummary>(`/api/jobs/${id}/rerun`),
  remove: (id: number) => request<void>(`/api/jobs/${id}`, { method: "DELETE" }),
  clear: (kinds?: JobKind[]) => post<{ deleted: number[] }>("/api/jobs/clear", { kinds: kinds ?? null }),
  resetNumbering: () => post<void>("/api/jobs/reset-numbering"),
  cnf: (id: number, offset: number, limit: number) =>
    request<{ offset: number; lines: string[]; total: number }>(`/api/jobs/${id}/cnf?offset=${offset}&limit=${limit}`),
  rowCase: (id: number, index: number) => request<RowCase>(`/api/jobs/${id}/rows/${index}/case`),
};

export const urls = {
  file: (id: number, name: string) => `/api/jobs/${id}/files/${name}`,
  exportCsv: (id: number) => `/api/jobs/${id}/export.csv`,
  exportMany: (ids: number[]) => `/api/export.csv?jobs=${ids.join(",")}`,
  rowCnf: (id: number, index: number) => `/api/jobs/${id}/rows/${index}/cnf`,
  media: (name: string) => `/media/${name}`,
};
