import type { Canvas } from "../blocks/types";

export interface Agent {
  key: string;
  name: string;
  description: string;
  model: string;
  skills: string[];
  web: boolean;
  tags: string[];
  system: string;
  members: string[];
}

export interface TeamSummary {
  key: string;
  name: string;
  description: string;
  coordinator: string;
  members: string[];
  mode: "static" | "dynamic";
}

export interface TeamDetail extends TeamSummary {
  coordinator_agent: Agent;
  member_agents: Agent[];
  sub_agents: Record<string, Agent>;
  input_label: string;
  input_pdf: boolean;
  sample_input: string | null;
}

export interface Rfp {
  id: string;
  filename: string;
  pages: number;
  chars: number;
  preview: string;
}

export interface RunInput {
  input?: string | null;
  rfp_id?: string | null;
}

async function check<T>(res: Response): Promise<T> {
  if (!res.ok) {
    const body = await res.text();
    let detail = body;
    try {
      detail = JSON.parse(body).detail ?? body;
    } catch {
      // not JSON: keep the text
    }
    throw new Error(`${res.status} ${res.statusText}: ${typeof detail === "string" ? detail : body}`);
  }
  return res.json() as Promise<T>;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  return check<T>(await fetch(path, { headers: { "Content-Type": "application/json" }, ...init }));
}

export const api = {
  health: () => request<{ ok: boolean; swarm: boolean }>("/api/health"),
  teams: () => request<TeamSummary[]>("/api/teams"),
  team: (key: string) => request<TeamDetail>(`/api/teams/${encodeURIComponent(key)}`),
  canvas: (id: number) => request<Canvas>(`/api/canvases/${id}`),
  // No Content-Type header: the browser sets the multipart boundary itself.
  uploadRfp: async (file: File) => {
    const form = new FormData();
    form.append("file", file);
    return check<Rfp>(await fetch("/api/rfps", { method: "POST", body: form }));
  },
  startRun: (team: string, body: RunInput) =>
    request<{ canvas_id: number }>(`/api/teams/${encodeURIComponent(team)}/runs`, {
      method: "POST",
      body: JSON.stringify(body),
    }),
  canvasStreamUrl: (id: number) => `/api/canvases/${id}/stream`,
};
