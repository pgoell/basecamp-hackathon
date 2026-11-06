// Mirrors backend/app/canvas/models.py. The live JSON Schema is
// served at GET /api/schema if you want to generate these instead.

export type StatusState = "queued" | "running" | "done" | "failed";
export type Tone = "info" | "success" | "warning" | "danger";

export interface BlockPropsByType {
  markdown: { text: string };
  status: { state: StatusState; detail?: string | null };
  table: { columns: string[]; rows: (string | number | null)[][] };
  kv: { items: { label: string; value: string }[] };
  callout: { tone: Tone; text: string };
  file: { filename: string; url?: string | null };
}

export type BlockType = keyof BlockPropsByType;

export interface Block<T extends string = string> {
  id: string;
  type: T;
  title: string | null;
  agent: string | null;
  props: T extends BlockType ? BlockPropsByType[T] : Record<string, unknown>;
}

export interface Canvas {
  id: number;
  title: string;
  team: string | null;
  version: number;
  blocks: Block[];
  updated: string;
}
