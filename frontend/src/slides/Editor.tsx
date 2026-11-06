// The editor: slide strip, canvas with its toolbar and notes, and the chat.
import { useEffect, useState } from "react";
import { BASE, ask } from "./api";
import { Canvas } from "./Canvas";
import { ChatPanel } from "./Chat";
import { type El, type Slide, newId } from "./doc";
import { Strip } from "./Strip";
import { Toolbar } from "./Toolbar";
import { useDoc } from "./useDoc";

export function Editor({ id }: { id: number }) {
  const { doc, title, setTitle, change, undo, redo, note, setNote, dirty, pull, busy } = useDoc(id);
  const [current, setCurrent] = useState("");
  const [picked, setPicked] = useState<string[]>([]);
  const [editing, setEditing] = useState<string | null>(null);
  busy.current = editing !== null;

  // The slide in use stays put when slides come and go, or moves to its neighbour.
  const slide: Slide | undefined = doc?.slides.find((s) => s.id === current) ?? doc?.slides[0];
  useEffect(() => {
    if (slide && slide.id !== current) setCurrent(slide.id);
  }, [slide, current]);
  useEffect(() => {
    setPicked((p) => p.filter((pid) => slide?.elements.some((el) => el.id === pid)));
  }, [slide]);

  const setElements = (els: El[], merge = false) => doc && slide && change({ ...doc, slides: doc.slides.map((s) => (s.id === slide.id ? { ...s, elements: els } : s)) }, merge);
  const update = (f: (el: El) => El) => slide && setElements(slide.elements.map((el) => (picked.includes(el.id) ? f(el) : el)));
  const insert = (el: El) => {
    if (!slide) return;
    setElements([...slide.elements, el]);
    setPicked([el.id]);
  };
  const remove = () => slide && setElements(slide.elements.filter((el) => !picked.includes(el.id)));
  const arrange = (to: "front" | "back") => {
    if (!slide) return;
    const mine = slide.elements.filter((el) => picked.includes(el.id));
    const rest = slide.elements.filter((el) => !picked.includes(el.id));
    setElements(to === "front" ? [...rest, ...mine] : [...mine, ...rest]);
  };

  useEffect(() => {
    const keys = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement;
      if (editing || t.closest("input, textarea, select, [contenteditable=true]")) return;
      const mod = e.ctrlKey || e.metaKey;
      if (mod && e.key.toLowerCase() === "z") return e.preventDefault(), e.shiftKey ? redo() : undo();
      if (mod && e.key.toLowerCase() === "y") return e.preventDefault(), redo();
      if (!slide || !picked.length) return;
      if (e.key === "Delete" || e.key === "Backspace") return e.preventDefault(), remove();
      if (mod && e.key.toLowerCase() === "d") {
        e.preventDefault();
        const copies = slide.elements.filter((el) => picked.includes(el.id)).map((el) => ({ ...structuredClone(el), id: newId(), x: el.x + 20, y: el.y + 20 }));
        setElements([...slide.elements, ...copies]);
        return setPicked(copies.map((c) => c.id));
      }
      const step = e.shiftKey ? 10 : 1;
      const move = { ArrowLeft: [-step, 0], ArrowRight: [step, 0], ArrowUp: [0, -step], ArrowDown: [0, step] }[e.key];
      if (move) {
        e.preventDefault();
        setElements(slide.elements.map((el) => (picked.includes(el.id) ? { ...el, x: el.x + move[0], y: el.y + move[1] } : el)), e.repeat);
      }
    };
    addEventListener("keydown", keys);
    return () => removeEventListener("keydown", keys);
  });

  if (!doc || !slide) return <div className="slides-app loading">{note || "Loading…"}</div>;

  return (
    <div className="slides-app editor">
      <header className="bar">
        <a href="/slides" className="brand">PowerPointless</a>
        <input
          className="title"
          value={title}
          onChange={(e) => setTitle(e.target.value)}
          onBlur={() => title.trim() && ask(`/presentations/${id}`, { method: "PATCH", json: { title: title.trim() } })}
        />
        <span className="status">{note || (dirty ? "Saving…" : "Saved")}</span>
        <button onClick={undo} title="Undo (Ctrl+Z)">↶</button>
        <button onClick={redo} title="Redo (Ctrl+Y)">↷</button>
        <a className="button" href={`${BASE}/presentations/${id}/pdf`}>Download PDF</a>
      </header>
      <Strip doc={doc} current={slide.id} pick={(s) => (setCurrent(s), setPicked([]), setEditing(null))} change={change} />
      <section className="stage">
        <Toolbar
          doc={doc}
          els={slide.elements.filter((el) => picked.includes(el.id))}
          editing={editing !== null}
          insert={insert}
          update={update}
          arrange={arrange}
          remove={remove}
          setNote={setNote}
        />
        <Canvas
          doc={doc}
          slide={slide}
          picked={picked}
          setPicked={setPicked}
          editing={editing}
          setEditing={setEditing}
          onElements={setElements}
          onText={(eid, paras) => {
            setEditing(null);
            setElements(slide.elements.map((el) => (el.id === eid && (el.type === "text" || el.type === "shape") ? { ...el, paras } : el)));
          }}
          onCell={(eid, r, c, text) =>
            setElements(
              slide.elements.map((el) =>
                el.id === eid && el.type === "table" ? { ...el, cells: el.cells.map((row, i) => (i === r ? row.map((v, j) => (j === c ? text : v)) : row)) } : el,
              ),
            )
          }
        />
        <div className="slide-props">
          <label>
            Background <input type="color" value={slide.background ?? "#ffffff"} onChange={(e) => change({ ...doc, slides: doc.slides.map((s) => (s.id === slide.id ? { ...s, background: e.target.value } : s)) }, true)} />
          </label>
          <textarea
            placeholder="Speaker notes"
            value={slide.notes ?? ""}
            rows={2}
            onChange={(e) => change({ ...doc, slides: doc.slides.map((s) => (s.id === slide.id ? { ...s, notes: e.target.value || undefined } : s)) }, true)}
          />
        </div>
      </section>
      <ChatPanel presentation={id} slide={slide.id} onDoc={() => pull().catch(() => {})} />
    </div>
  );
}
