// Insert buttons, and the look of the picked elements: font, size, colours, alignment, order.
import { useRef } from "react";
import { upload } from "./api";
import { type Doc, type El, FONTS, type Run, type ShapeKind, fontOf, fresh } from "./doc";

const SHAPES: [ShapeKind, string][] = [["rect", "Rectangle"], ["roundRect", "Rounded"], ["ellipse", "Ellipse"], ["triangle", "Triangle"], ["line", "Line"], ["arrow", "Arrow"]];
const SIZES = [12, 14, 16, 18, 20, 24, 28, 32, 40, 48, 54, 64, 72, 96];

// A button that keeps the focus in the open text field, so execCommand works on its selection.
function Btn({ on, title, active, children }: { on: () => void; title: string; active?: boolean; children: React.ReactNode }) {
  return (
    <button title={title} className={active ? "on" : undefined} onMouseDown={(e) => e.preventDefault()} onClick={on}>
      {children}
    </button>
  );
}

export function Toolbar({ doc, els, editing, insert, update, arrange, remove, setNote }: {
  doc: Doc;
  els: El[];
  editing: boolean;
  insert: (el: El) => void;
  update: (f: (el: El) => El) => void;
  arrange: (to: "front" | "back") => void;
  remove: () => void;
  setNote: (s: string) => void;
}) {
  const file = useRef<HTMLInputElement>(null);
  const el = els[0];
  const texty = els.length > 0 && els.every((e) => e.type === "text" || e.type === "shape" || e.type === "table");
  const runs = els.flatMap((e) => (e.type === "text" || e.type === "shape" ? (e.paras ?? []).flatMap((p) => p.runs) : []));
  const all = (key: "bold" | "italic" | "underline") => runs.length > 0 && runs.every((r) => r[key]);

  // Bold, italic, underline: in the open field on the words picked, else on every run of the picked elements.
  const mark = (key: "bold" | "italic" | "underline") => {
    if (editing) return void document.execCommand(key);
    const to = !all(key);
    update((e) =>
      e.type === "text" || e.type === "shape"
        ? { ...e, paras: (e.paras ?? []).map((p) => ({ ...p, runs: p.runs.map((r): Run => ({ ...r, [key]: to || undefined })) })) }
        : e,
    );
  };
  const set = (props: Record<string, unknown>) => update((e) => ({ ...e, ...props }) as El);
  const color = (c: string) => {
    if (editing) return void document.execCommand("foreColor", false, c);
    update((e) =>
      e.type === "text" || e.type === "shape"
        ? { ...e, color: c, paras: (e.paras ?? []).map((p) => ({ ...p, runs: p.runs.map(({ color: _, ...r }) => r) })) }
        : e.type === "table" ? { ...e, color: c } : e,
    );
  };
  const list = (kind: "bullet" | "number") =>
    update((e) => {
      if (e.type !== "text" && e.type !== "shape") return e;
      const on = (e.paras ?? []).every((p) => p.list === kind);
      return { ...e, paras: (e.paras ?? []).map(({ list: _, ...p }) => (on ? p : { ...p, list: kind })) };
    });
  const table = (rows: number, cols: number) =>
    update((e) => {
      if (e.type !== "table") return e;
      let cells = e.cells.map((r) => [...r]);
      if (rows > 0) cells.push(cells[0].map(() => ""));
      if (rows < 0 && cells.length > 1) cells = cells.slice(0, -1);
      if (cols > 0) cells = cells.map((r) => [...r, ""]);
      if (cols < 0 && cells[0].length > 1) cells = cells.map((r) => r.slice(0, -1));
      return { ...e, cells };
    });

  return (
    <div className="toolbar">
      <div className="group">
        <Btn title="Text box" on={() => insert(fresh("text"))}>Text</Btn>
        <select value="" title="Shape" onChange={(e) => e.target.value && insert(fresh(e.target.value as ShapeKind))}>
          <option value="">Shape</option>
          {SHAPES.map(([k, name]) => <option key={k} value={k}>{name}</option>)}
        </select>
        <Btn title="Image" on={() => file.current!.click()}>Image</Btn>
        <Btn title="Table" on={() => insert(fresh("table"))}>Table</Btn>
        <input
          ref={file}
          type="file"
          accept="image/*"
          hidden
          onChange={async (e) => {
            const f = e.target.files?.[0];
            e.target.value = "";
            if (!f) return;
            try {
              insert(fresh("image", await upload(f)));
            } catch {
              setNote("The image did not upload.");
            }
          }}
        />
      </div>
      {texty && (
        <div className="group">
          <select value={fontOf(doc, el as { font?: string })} title="Font" onChange={(e) => set({ font: e.target.value })}>
            {FONTS.map((f) => <option key={f}>{f}</option>)}
          </select>
          <select value={(el as { size?: number }).size ?? 24} title="Size" onChange={(e) => set({ size: +e.target.value })}>
            {[...new Set([...SIZES, (el as { size?: number }).size ?? 24])].sort((a, b) => a - b).map((s) => <option key={s}>{s}</option>)}
          </select>
          <Btn title="Bold" active={all("bold")} on={() => mark("bold")}><b>B</b></Btn>
          <Btn title="Italic" active={all("italic")} on={() => mark("italic")}><i>I</i></Btn>
          <Btn title="Underline" active={all("underline")} on={() => mark("underline")}><u>U</u></Btn>
          <label title="Text colour" className="swatch">
            A
            <input type="color" value={(el as { color?: string }).color ?? "#1a1a1a"} onChange={(e) => color(e.target.value)} />
          </label>
          {el.type !== "table" && (
            <>
              <Btn title="Bullets" on={() => list("bullet")}>•</Btn>
              <Btn title="Numbers" on={() => list("number")}>1.</Btn>
              {(["left", "center", "right"] as const).map((a) => (
                <Btn key={a} title={`Align ${a}`} active={(el as { align?: string }).align === a || (!(el as { align?: string }).align && a === "left")} on={() => set({ align: a })}>
                  {a === "left" ? "⇤" : a === "center" ? "↔" : "⇥"}
                </Btn>
              ))}
              <select value={(el as { valign?: string }).valign ?? "top"} title="Vertical alignment" onChange={(e) => set({ valign: e.target.value })}>
                <option value="top">Top</option>
                <option value="middle">Middle</option>
                <option value="bottom">Bottom</option>
              </select>
            </>
          )}
        </div>
      )}
      {els.length > 0 && el.type !== "image" && (
        <div className="group">
          <label title="Fill" className="swatch fill">
            Fill
            <input type="color" value={(el as { fill?: string }).fill ?? "#ffffff"} onChange={(e) => set({ fill: e.target.value })} />
          </label>
          <Btn title="No fill" on={() => set({ fill: undefined })}>∅</Btn>
          {el.type === "shape" && (
            <>
              <label title="Outline" className="swatch">
                Line
                <input type="color" value={el.stroke ?? "#1a1a1a"} onChange={(e) => set({ stroke: e.target.value, strokeWidth: el.strokeWidth ?? 2 })} />
              </label>
              <select value={el.strokeWidth ?? 0} title="Line width" onChange={(e) => set({ strokeWidth: +e.target.value || undefined, stroke: +e.target.value ? (el.stroke ?? "#1a1a1a") : undefined })}>
                {[0, 1, 2, 3, 4, 6, 8].map((w) => <option key={w} value={w}>{w ? `${w} pt` : "No line"}</option>)}
              </select>
            </>
          )}
          {el.type === "table" && (
            <>
              <Btn title="Add row" on={() => table(1, 0)}>+Row</Btn>
              <Btn title="Remove row" on={() => table(-1, 0)}>−Row</Btn>
              <Btn title="Add column" on={() => table(0, 1)}>+Col</Btn>
              <Btn title="Remove column" on={() => table(0, -1)}>−Col</Btn>
              <Btn title="Header row" active={!!el.header} on={() => set({ header: !el.header || undefined })}>Header</Btn>
            </>
          )}
        </div>
      )}
      {els.length > 0 && (
        <div className="group">
          <Btn title="Bring to front" on={() => arrange("front")}>Front</Btn>
          <Btn title="Send to back" on={() => arrange("back")}>Back</Btn>
          <Btn title="Delete" on={remove}>Delete</Btn>
        </div>
      )}
    </div>
  );
}
