import type { Doc, Presentation } from "./doc";

export const BASE = "/api/slides";

export class Refusal extends Error {
  constructor(public status: number, public problems: string[] = []) {
    super(problems.join("\n") || String(status));
  }
}

export async function ask<T>(path: string, init?: RequestInit & { json?: unknown }): Promise<T> {
  const { json, ...rest } = init ?? {};
  const res = await fetch(BASE + path, {
    ...rest,
    headers: json !== undefined ? { "Content-Type": "application/json" } : undefined,
    body: json !== undefined ? JSON.stringify(json) : rest.body,
  });
  if (!res.ok) {
    const body = await res.json().catch(() => ({}));
    const d = body?.detail;
    throw new Refusal(res.status, Array.isArray(d?.problems) ? d.problems : typeof d === "string" ? [d] : []);
  }
  return res.status === 204 ? (undefined as T) : res.json();
}

export const getPresentation = (id: number) => ask<Presentation>(`/presentations/${id}`);
export const saveDoc = (id: number, doc: Doc, version: number) =>
  ask<Presentation>(`/presentations/${id}`, { method: "PATCH", json: { doc, version } });

export async function upload(file: File): Promise<string> {
  const form = new FormData();
  form.append("file", file);
  const { src } = await ask<{ src: string }>("/uploads", { method: "POST", body: form });
  return src;
}
