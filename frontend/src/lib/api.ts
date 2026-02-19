import type {
  ApprovalResponse,
  CreateSessionResponse,
  HealthResponse,
  SessionHistoryResponse,
} from "./types";

const BASE = "/api";

async function fetchJSON<T>(url: string, init?: RequestInit): Promise<T> {
  const res = await fetch(url, init);
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(
      `API ${res.status}: ${body || res.statusText}`
    );
  }
  return res.json() as Promise<T>;
}

export function createSession(): Promise<CreateSessionResponse> {
  return fetchJSON(`${BASE}/conversations`, { method: "POST" });
}

export function streamQueryURL(sessionId: string, question: string): string {
  const q = encodeURIComponent(question);
  return `${BASE}/conversations/${encodeURIComponent(sessionId)}/stream?question=${q}`;
}

export function approveQuery(
  queryId: string,
  approved: boolean,
  modifiedSql?: string
): Promise<ApprovalResponse> {
  return fetchJSON(`${BASE}/approve/${queryId}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      approved,
      modified_sql: modifiedSql || null,
    }),
  });
}

export function getSessionHistory(
  sessionId: string
): Promise<SessionHistoryResponse> {
  return fetchJSON(`${BASE}/conversations/${encodeURIComponent(sessionId)}/history`);
}

export function getHealth(): Promise<HealthResponse> {
  return fetchJSON(`${BASE}/health`);
}
