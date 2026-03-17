import type { ApiErrorPayload } from "../../types/api";

const DEFAULT_API_BASE = "/api";

export class ApiError extends Error {
  readonly status: number;
  readonly detail: string;

  constructor(status: number, detail: string) {
    super(detail);
    this.name = "ApiError";
    this.status = status;
    this.detail = detail;
  }
}

function getApiBase() {
  return (import.meta.env.VITE_API_BASE ?? DEFAULT_API_BASE).replace(/\/$/, "");
}

function getRequestUrl(path: string) {
  const normalizedPath = path.startsWith("/") ? path : `/${path}`;
  return `${getApiBase()}${normalizedPath}`;
}

export async function fetchJson<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(getRequestUrl(path), {
    headers: {
      Accept: "application/json",
      ...(init?.headers ?? {}),
    },
    ...init,
  });

  if (!response.ok) {
    let errorPayload: ApiErrorPayload | null = null;
    try {
      errorPayload = (await response.json()) as ApiErrorPayload;
    } catch {
      errorPayload = null;
    }
    throw new ApiError(
      response.status,
      errorPayload?.detail ?? `API request failed: ${response.status}`,
    );
  }

  return (await response.json()) as T;
}
