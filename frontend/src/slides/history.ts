// Undo and redo, from blattwerk's history.ts without the sheet's own rules.
import type { Doc } from "./doc";

export type Hist = { past: Doc[]; doc: Doc; future: Doc[] };

// Whether two docs are the same once saved: a key that holds nothing is saved as no key.
export function alike(a: unknown, b: unknown): boolean {
  if (a === b) return true;
  if (!a || !b || typeof a !== "object" || typeof b !== "object" || Array.isArray(a) !== Array.isArray(b)) return false;
  const [x, y] = [a, b] as Record<string, unknown>[];
  return Object.keys({ ...x, ...y }).every((key) => alike(x[key], y[key]));
}

// A change: a step of its own, or with `merge` one more of the gesture that made the last step. Redo goes.
export const stepped = (h: Hist, doc: Doc, merge: boolean): Hist =>
  alike(doc, h.doc) ? h : { past: merge ? h.past : [...h.past, h.doc].slice(-100), doc, future: [] };
export const undone = (h: Hist): Hist =>
  h.past.length ? { past: h.past.slice(0, -1), doc: h.past.at(-1)!, future: [h.doc, ...h.future] } : h;
export const redone = (h: Hist): Hist =>
  h.future.length ? { past: [...h.past, h.doc], doc: h.future[0], future: h.future.slice(1) } : h;
