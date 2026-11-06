// The presentation document. Lengths in pt on a 960 x 540 slide (PowerPoint 16:9). See docs/slides.md.

export const SLIDE_W = 960;
export const SLIDE_H = 540;

export type Run = { text: string; bold?: boolean; italic?: boolean; underline?: boolean; color?: string };
export type Para = { runs: Run[]; list?: "bullet" | "number" };
export type Align = "left" | "center" | "right";
export type Valign = "top" | "middle" | "bottom";

// Every element's box, as blattwerk's Box: pt from the slide's top left, turned about its centre.
type Box = { id: string; x: number; y: number; w: number; h: number; rotation?: number };
export type TextProps = {
  paras?: Para[];
  size?: number;
  color?: string;
  font?: string;
  align?: Align;
  valign?: Valign;
};
export type TextEl = Box & TextProps & { type: "text"; fill?: string; role?: "title" | "body" };
export type ShapeKind = "rect" | "roundRect" | "ellipse" | "triangle" | "line" | "arrow";
export type ShapeEl = Box & TextProps & { type: "shape"; shape: ShapeKind; fill?: string; stroke?: string; strokeWidth?: number };
export type ImageEl = Box & { type: "image"; src: string; fit?: "cover" | "contain"; opacity?: number };
export type TableEl = Box & {
  type: "table";
  cells: string[][];
  header?: boolean;
  size?: number;
  color?: string;
  fill?: string;
  headerFill?: string;
  border?: string;
};
export type El = TextEl | ShapeEl | ImageEl | TableEl;
export type Slide = { id: string; elements: El[]; background?: string; notes?: string };
export type Doc = { slides: Slide[]; font?: string };
export type Presentation = { id: number; title: string; doc: Doc; version: number; updated: string };

export const FONTS = ["Geist", "Georgia", "Arial", "Times New Roman", "Courier New"];
export const fontOf = (doc: Doc, el?: { font?: string }) => el?.font ?? doc.font ?? "Geist";
// The CSS family of a font name: Geist comes from @fontsource-variable/geist under its own name.
export const familyOf = (font: string) => (font === "Geist" ? '"Geist Variable", sans-serif' : `"${font}", sans-serif`);

export const newId = () => Math.random().toString(36).slice(2, 10);
export const plain = (text: string): Para[] => text.split("\n").map((line) => ({ runs: [{ text: line }] }));
export const textOf = (paras: Para[] = []) => paras.map((p) => p.runs.map((r) => r.text).join("")).join("\n");

// What the insert buttons add: centred, a size that reads on a slide.
export function fresh(type: El["type"] | ShapeKind, src = ""): El {
  const box = { id: newId(), x: 280, y: 170, w: 400, h: 200 };
  if (type === "text") return { ...box, type: "text", h: 60, paras: plain("Text"), size: 24 };
  if (type === "image") return { ...box, type: "image", src, fit: "contain" };
  if (type === "table")
    return { ...box, type: "table", w: 480, h: 160, header: true, size: 16, cells: [["Header", "Header", "Header"], ["", "", ""], ["", "", ""]] };
  const line = type === "line" || type === "arrow";
  return { ...box, type: "shape", shape: type as ShapeKind, h: line ? 4 : 200, fill: line ? undefined : "#4f7cff", stroke: line ? "#1a1a1a" : undefined, strokeWidth: line ? 3 : undefined };
}
