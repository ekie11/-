export const NETWORK_ERROR = "Сервер недоступен, попробуйте позже";

export class ApiError extends Error {
  status: number;
  detail: string;
  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

export interface Me {
  id: number;
  email: string;
}

export interface ProfileSummary {
  id: string;
  name: string;
  base: string | null;
  readonly: boolean;
}

/** Правила профиля: структура задаётся движком, поэтому значения произвольные. */
export type RuleConfig = Record<string, unknown>;

export interface Profile extends ProfileSummary {
  rules: RuleConfig;
  diff?: unknown;
}

export type JobStatus = "queued" | "running" | "done" | "error" | "expired";
export type JobMode = "check" | "format";

export interface JobSummary {
  id: number;
  status: JobStatus;
  mode: JobMode;
  profile_name: string;
  created_at: string;
  expires_at: string | null;
}

export interface Issue {
  rule?: string;
  source?: string;
  severity?: string;
  message: string;
  expected?: string | null;
  actual?: string | null;
  paragraph_index?: number | null;
  fixable?: boolean;
  location?: string | null;
  [key: string]: unknown;
}

export interface Report {
  issues?: Issue[];
  warnings?: string[];
  summary?: { errors?: number; recommendations?: number };
  [key: string]: unknown;
}

export interface Job {
  id: number;
  status: JobStatus;
  mode: JobMode;
  error: string | null;
  report: Report | null;
  has_pdf: boolean;
  created_at: string;
  expires_at: string | null;
}

async function request<T>(path: string, init: RequestInit): Promise<T> {
  let res: Response;
  try {
    res = await fetch(`/api${path}`, { ...init, credentials: "include" });
  } catch {
    throw new ApiError(0, NETWORK_ERROR);
  }
  if (!res.ok) {
    let detail = NETWORK_ERROR;
    try {
      const body = await res.json();
      if (body && typeof body.detail === "string") detail = body.detail;
    } catch {
      /* не JSON — оставляем общее сообщение */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  try {
    return (await res.json()) as T;
  } catch {
    throw new ApiError(res.status, NETWORK_ERROR);
  }
}

export function apiFetch<T>(path: string, init: RequestInit = {}): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined && init.body !== null && !headers.has("Content-Type")) {
    headers.set("Content-Type", "application/json");
  }
  return request<T>(path, { ...init, headers });
}

export function apiUpload<T>(path: string, form: FormData): Promise<T> {
  return request<T>(path, { method: "POST", body: form });
}

export type ExtractionStatus = "queued" | "running" | "done" | "failed";

export interface Extraction {
  id: string;
  status: ExtractionStatus;
  base_profile_id: string;
  source_name: string | null;
  result: import("@/components/extraction/ResultTable").ExtractionResult | null;
  error: string | null;
}

export const api = {
  createExtraction: (form: FormData) => apiUpload<{ id: string }>("/extractions", form),
  getExtraction: (id: string) => apiFetch<Extraction>(`/extractions/${id}`),
  getQuota: () => apiFetch<{ used: number; limit: number }>("/extractions/quota"),
  createProfileFromExtraction: (id: string, body: { accepted: number[]; name: string }) =>
    apiFetch<{ profile_id: string }>(`/extractions/${id}/profile`, { method: "POST", body: JSON.stringify(body) }),
};
