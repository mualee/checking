import { auth } from "./firebase";

const API_BASE = import.meta.env.VITE_API_BASE || "/api";

export class ApiError extends Error {
  status: number;
  detail: unknown;
  constructor(status: number, detail: unknown, message: string) {
    super(message);
    this.status = status;
    this.detail = detail;
  }
}

async function authHeader(): Promise<Record<string, string>> {
  const user = auth.currentUser;
  if (!user) return {};
  const token = await user.getIdToken();
  return { Authorization: `Bearer ${token}` };
}

type RequestOptions = {
  method?: string;
  body?: unknown;
  /** When body is FormData, skip JSON serialization/content-type. */
  formData?: FormData;
  signal?: AbortSignal;
};

async function request<T>(path: string, opts: RequestOptions = {}): Promise<T> {
  const headers: Record<string, string> = { ...(await authHeader()) };
  let body: BodyInit | undefined;

  if (opts.formData) {
    body = opts.formData;
  } else if (opts.body !== undefined) {
    headers["Content-Type"] = "application/json";
    body = JSON.stringify(opts.body);
  }

  const res = await fetch(`${API_BASE}${path}`, {
    method: opts.method ?? "GET",
    headers,
    body,
    signal: opts.signal,
  });

  const text = await res.text();
  const parsed = text ? safeJson(text) : null;

  if (!res.ok) {
    const detail = (parsed as { detail?: unknown } | null)?.detail ?? parsed ?? text;
    throw new ApiError(res.status, detail, typeof detail === "string" ? detail : res.statusText);
  }
  return parsed as T;
}

function safeJson(text: string): unknown {
  try {
    return JSON.parse(text);
  } catch {
    return text;
  }
}

async function getBlob(path: string): Promise<Blob> {
  const headers = await authHeader();
  const res = await fetch(`${API_BASE}${path}`, { headers });
  if (!res.ok) {
    const text = await res.text();
    throw new ApiError(res.status, text, res.statusText);
  }
  return res.blob();
}

export const api = {
  get: <T>(path: string, signal?: AbortSignal) => request<T>(path, { signal }),
  post: <T>(path: string, body?: unknown) => request<T>(path, { method: "POST", body }),
  put: <T>(path: string, body?: unknown) => request<T>(path, { method: "PUT", body }),
  patch: <T>(path: string, body?: unknown) => request<T>(path, { method: "PATCH", body }),
  upload: <T>(path: string, formData: FormData) =>
    request<T>(path, { method: "POST", formData }),
  getBlob,
};
