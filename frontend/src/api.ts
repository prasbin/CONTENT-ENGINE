import type { Job, JobList, JobStatus } from "./types";

const BASE_URL = (import.meta.env.VITE_API_BASE_URL ?? "").replace(/\/$/, "");
const TOKEN = import.meta.env.VITE_API_TOKEN ?? "";

function authHeaders(): Record<string, string> {
  return TOKEN ? { Authorization: `Bearer ${TOKEN}` } : {};
}

async function parseError(res: Response): Promise<string> {
  try {
    const body = (await res.json()) as { error?: { message?: string } };
    return body?.error?.message ?? `Request failed (${res.status})`;
  } catch {
    return `Request failed (${res.status})`;
  }
}

export async function createJob(sourceUrl: string, payload: Record<string, unknown> = {}): Promise<Job> {
  const res = await fetch(`${BASE_URL}/api/v1/jobs`, {
    method: "POST",
    headers: { "Content-Type": "application/json", ...authHeaders() },
    body: JSON.stringify({ source_url: sourceUrl, payload }),
  });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as Job;
}

export async function getJob(id: string): Promise<Job> {
  const res = await fetch(`${BASE_URL}/api/v1/jobs/${id}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as Job;
}

export async function listJobs(status?: JobStatus): Promise<JobList> {
  const qs = status ? `?status=${status}` : "";
  const res = await fetch(`${BASE_URL}/api/v1/jobs${qs}`, { headers: authHeaders() });
  if (!res.ok) throw new Error(await parseError(res));
  return (await res.json()) as JobList;
}

export async function getHealth(): Promise<boolean> {
  try {
    const res = await fetch(`${BASE_URL}/health`);
    if (!res.ok) return false;
    const body = (await res.json()) as { status?: string };
    return body?.status === "ok";
  } catch {
    return false;
  }
}
