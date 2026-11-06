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
}

export interface TeamSummary {
  key: string;
  name: string;
  description: string;
  coordinator: string;
  members: string[];
}

export interface TeamDetail extends TeamSummary {
  coordinator_agent: Agent;
  member_agents: Agent[];
  input_label: string;
  sample_input: string | null;
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text();
    throw new Error(`${res.status} ${res.statusText}: ${body}`);
  }
  return res.json() as Promise<T>;
}

export const api = {
  health: () => request<{ status: string; version: string }>("/api/health"),
  teams: () => request<TeamSummary[]>("/api/teams"),
  team: (key: string) => request<TeamDetail>(`/api/teams/${encodeURIComponent(key)}`),
  canvas: (id: string) => request<Canvas>(`/api/canvases/${encodeURIComponent(id)}`),
  startRun: (team: string, input: string | null) =>
    request<{ canvas_id: string }>(`/api/teams/${encodeURIComponent(team)}/runs`, {
      method: "POST",
      body: JSON.stringify({ input }),
    }),
  canvasStreamUrl: (id: string) => `/api/canvases/${encodeURIComponent(id)}/stream`,
};
