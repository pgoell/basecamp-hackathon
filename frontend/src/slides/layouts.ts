// The slide layouts the "New slide" menu offers. backend/app/slides/ops.py places the same ones for the agent.
import { type El, type Slide, newId, plain } from "./doc";

export const LAYOUTS = { title: "Title", title_content: "Title and content", two_columns: "Two columns", section: "Section header", blank: "Blank" } as const;
export type Layout = keyof typeof LAYOUTS;

const text = (x: number, y: number, w: number, h: number, words: string, rest: Partial<El & { type: "text" }> = {}): El => ({
  id: newId(), type: "text", x, y, w, h, paras: plain(words), size: 24, ...rest,
});
const title = (words = "Click to add title") => text(60, 40, 840, 80, words, { size: 40, role: "title", valign: "middle" });
const bullets = (x: number, w: number): El =>
  text(x, 140, w, 360, "", { role: "body", paras: [{ runs: [{ text: "Click to add text" }], list: "bullet" }] });

export function slideFor(layout: Layout): Slide {
  const els: Record<Layout, () => El[]> = {
    title: () => [
      text(60, 170, 840, 110, "Click to add title", { size: 54, role: "title", align: "center", valign: "bottom" }),
      text(60, 290, 840, 60, "Click to add subtitle", { size: 28, align: "center", color: "#555555", role: "body" }),
    ],
    title_content: () => [title(), bullets(60, 840)],
    two_columns: () => [title(), bullets(60, 405), bullets(495, 405)],
    section: () => [text(60, 200, 840, 100, "Section title", { size: 48, role: "title", valign: "middle" })],
    blank: () => [],
  };
  return { id: newId(), elements: els[layout]() };
}
