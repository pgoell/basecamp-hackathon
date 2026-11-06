// Draws a slide at `k` px per pt. The editor, the slide strip and the print page all draw with this.
import { useLayoutEffect, useRef, type CSSProperties, type ReactNode } from "react";
import { type Doc, type El, type Para, type Run, type ShapeEl, type Slide, type TextProps, SLIDE_H, SLIDE_W, familyOf, fontOf } from "./doc";

const runStyle = (r: Run): CSSProperties => ({
  fontWeight: r.bold ? 700 : undefined,
  fontStyle: r.italic ? "italic" : undefined,
  textDecoration: r.underline ? "underline" : undefined,
  color: r.color,
});

function Paras({ paras }: { paras: Para[] }) {
  return (
    <>
      {paras.map((p, i) => {
        const runs = p.runs.some((r) => r.text) ? p.runs.map((r, j) => <span key={j} style={runStyle(r)}>{r.text}</span>) : <br />;
        if (!p.list) return <div key={i}>{runs}</div>;
        const n = paras.slice(0, i + 1).reverse().findIndex((q) => q.list !== "number");
        const mark = p.list === "bullet" ? "•" : `${n === -1 ? i + 1 : n}.`;
        return <div key={i} className="li" data-mark={mark}>{runs}</div>;
      })}
    </>
  );
}

const JUSTIFY = { top: "flex-start", middle: "center", bottom: "flex-end" } as const;
export const textCss = (doc: Doc, t: TextProps, k: number): CSSProperties => ({
  fontFamily: familyOf(fontOf(doc, t)),
  fontSize: (t.size ?? 24) * k,
  color: t.color ?? "#1a1a1a",
  textAlign: t.align ?? "left",
  justifyContent: JUSTIFY[t.valign ?? "top"],
});

// Moves the HTML of `paras` into the open field and back out, as runs.
export function toHtml(paras: Para[]): string {
  const esc = (s: string) => s.replace(/&/g, "&amp;").replace(/</g, "&lt;");
  return paras
    .map((p) => {
      const inner = p.runs
        .map((r) => {
          let s = esc(r.text);
          if (r.bold) s = `<b>${s}</b>`;
          if (r.italic) s = `<i>${s}</i>`;
          if (r.underline) s = `<u>${s}</u>`;
          if (r.color) s = `<font color="${r.color}">${s}</font>`;
          return s;
        })
        .join("");
      return `<div>${inner || "<br>"}</div>`;
    })
    .join("");
}

export function fromHtml(root: HTMLElement, was: Para[]): Para[] {
  const out: Para[] = [];
  let runs: Run[] = [];
  const flush = () => {
    const list = was[out.length]?.list ?? was.at(-1)?.list;
    out.push({ runs: runs.length ? runs : [{ text: "" }], ...(list && { list }) });
    runs = [];
  };
  const isBlock = (n: Node) => n instanceof HTMLElement && (n.tagName === "DIV" || n.tagName === "P");
  const walk = (node: Node, look: Omit<Run, "text">) => {
    if (node.nodeType === Node.TEXT_NODE) {
      const text = node.textContent ?? "";
      if (!text) return;
      const last = runs.at(-1);
      if (last && (["bold", "italic", "underline", "color"] as const).every((key) => last[key] === look[key])) last.text += text;
      else runs.push({ text, ...look });
      return;
    }
    if (!(node instanceof HTMLElement) || node.tagName === "BR") return;
    const tag = node.tagName;
    const next = { ...look };
    if (tag === "B" || tag === "STRONG" || node.style.fontWeight === "bold" || +node.style.fontWeight >= 600) next.bold = true;
    if (tag === "I" || tag === "EM" || node.style.fontStyle === "italic") next.italic = true;
    if (tag === "U" || node.style.textDecoration.includes("underline")) next.underline = true;
    const color = node.getAttribute("color") ?? (node.style.color ? hex(node.style.color) : undefined);
    if (color) next.color = color;
    node.childNodes.forEach((child) => {
      if (isBlock(child) && runs.length) flush();
      walk(child, next);
      if (isBlock(child) && (runs.length || ![...child.childNodes].some(isBlock))) flush();
    });
  };
  root.childNodes.forEach((child) => {
    if (isBlock(child) && runs.length) flush();
    walk(child, {});
    if (isBlock(child) && (runs.length || ![...child.childNodes].some(isBlock))) flush();
  });
  if (runs.length || !out.length) flush();
  // Drop the undefined keys, so a saved run names only what it sets.
  return out.map((p) => ({ ...p, runs: p.runs.map((r) => Object.fromEntries(Object.entries(r).filter(([, v]) => v !== undefined)) as Run) }));
}

function hex(css: string): string | undefined {
  const m = css.match(/rgb\((\d+),\s*(\d+),\s*(\d+)/);
  return m ? "#" + m.slice(1, 4).map((n) => (+n).toString(16).padStart(2, "0")).join("") : css.startsWith("#") ? css : undefined;
}

// The open text field of an element: plain contentEditable, read back into runs when it closes.
function Field({ paras, onDone }: { paras: Para[]; onDone: (paras: Para[]) => void }) {
  const ref = useRef<HTMLDivElement>(null);
  useLayoutEffect(() => {
    const el = ref.current!;
    el.innerHTML = toHtml(paras);
    el.focus();
    const range = document.createRange();
    range.selectNodeContents(el);
    getSelection()?.removeAllRanges();
    getSelection()?.addRange(range);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);
  return (
    <div
      ref={ref}
      className="field"
      contentEditable
      suppressContentEditableWarning
      onBlur={() => onDone(fromHtml(ref.current!, paras))}
      onKeyDown={(e) => {
        e.stopPropagation();
        if (e.key === "Escape") ref.current!.blur();
      }}
    />
  );
}

function ShapeSvg({ el, k }: { el: ShapeEl; k: number }) {
  const w = el.w * k;
  const h = el.h * k;
  const sw = (el.strokeWidth ?? (el.stroke ? 2 : 0)) * k;
  const paint = { fill: el.fill ?? "none", stroke: el.stroke ?? "none", strokeWidth: sw };
  const s = el.shape;
  let body: ReactNode;
  if (s === "rect") body = <rect x={sw / 2} y={sw / 2} width={Math.max(w - sw, 0)} height={Math.max(h - sw, 0)} {...paint} />;
  else if (s === "roundRect") body = <rect x={sw / 2} y={sw / 2} width={Math.max(w - sw, 0)} height={Math.max(h - sw, 0)} rx={Math.min(w, h) * 0.15} {...paint} />;
  else if (s === "ellipse") body = <ellipse cx={w / 2} cy={h / 2} rx={Math.max(w / 2 - sw / 2, 0)} ry={Math.max(h / 2 - sw / 2, 0)} {...paint} />;
  else if (s === "triangle") body = <polygon points={`${w / 2},${sw} ${w - sw},${h - sw / 2} ${sw},${h - sw / 2}`} {...paint} />;
  else {
    const line = { stroke: el.stroke ?? "#1a1a1a", strokeWidth: Math.max(sw, k) };
    const head = Math.max(sw, k) * 4;
    body = (
      <>
        <line x1={0} y1={h / 2} x2={s === "arrow" ? w - head : w} y2={h / 2} {...line} />
        {s === "arrow" && <polygon points={`${w},${h / 2} ${w - head},${h / 2 - head / 1.6} ${w - head},${h / 2 + head / 1.6}`} fill={line.stroke} />}
      </>
    );
  }
  return <svg width={w} height={h} style={{ position: "absolute", inset: 0, overflow: "visible" }}>{body}</svg>;
}

export function ElementView({ doc, el, k, editing, onText, onCell }: {
  doc: Doc;
  el: El;
  k: number;
  editing?: boolean;
  onText?: (paras: Para[]) => void;
  onCell?: (row: number, col: number, text: string) => void;
}) {
  const box: CSSProperties = {
    left: el.x * k,
    top: el.y * k,
    width: el.w * k,
    height: el.h * k,
    transform: el.rotation ? `rotate(${el.rotation}deg)` : undefined,
  };
  let inner: ReactNode = null;
  if (el.type === "text" || el.type === "shape") {
    const paras = el.paras ?? [];
    const text = (
      <div className="text" style={{ ...textCss(doc, el, k), padding: 4 * k }}>
        {editing && onText ? <Field paras={paras} onDone={onText} /> : <Paras paras={paras} />}
      </div>
    );
    inner = (
      <>
        {el.type === "shape" && <ShapeSvg el={el} k={k} />}
        {el.type === "text" && el.fill && <div style={{ position: "absolute", inset: 0, background: el.fill }} />}
        {(paras.length > 0 || editing) && text}
      </>
    );
  } else if (el.type === "image") {
    inner = el.src ? (
      <img src={el.src} alt="" draggable={false} style={{ width: "100%", height: "100%", objectFit: el.fit ?? "contain", opacity: el.opacity ?? 1 }} />
    ) : (
      <div className="empty-image">Image</div>
    );
  } else if (el.type === "table") {
    const border = `${Math.max(k, 0.5)}px solid ${el.border ?? "#999999"}`;
    inner = (
      <table style={{ fontFamily: familyOf(fontOf(doc)), fontSize: (el.size ?? 16) * k, color: el.color ?? "#1a1a1a", background: el.fill }}>
        <tbody>
          {el.cells.map((row, r) => (
            <tr key={r} style={r === 0 && el.header ? { background: el.headerFill ?? "#e8ecf4", fontWeight: 700 } : undefined}>
              {row.map((cell, c) => (
                <td
                  key={c}
                  style={{ border, padding: `${3 * k}px ${6 * k}px` }}
                  contentEditable={editing && !!onCell}
                  suppressContentEditableWarning
                  onKeyDown={(e) => e.stopPropagation()}
                  onBlur={(e) => onCell?.(r, c, e.currentTarget.innerText.trim())}
                >
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    );
  }
  return (
    <div className="el" data-id={el.id} style={box}>
      {inner}
    </div>
  );
}

export function SlideView({ doc, slide, k, children, editing, onText, onCell }: {
  doc: Doc;
  slide: Slide;
  k: number;
  children?: ReactNode;
  editing?: string;
  onText?: (id: string, paras: Para[]) => void;
  onCell?: (id: string, row: number, col: number, text: string) => void;
}) {
  return (
    <div className="slide" style={{ width: SLIDE_W * k, height: SLIDE_H * k, background: slide.background ?? "#ffffff" }}>
      {slide.elements.map((el) => (
        <ElementView key={el.id} doc={doc} el={el} k={k} editing={editing === el.id} onText={onText && ((p) => onText(el.id, p))} onCell={onCell && ((r, c, t) => onCell(el.id, r, c, t))} />
      ))}
      {children}
    </div>
  );
}
