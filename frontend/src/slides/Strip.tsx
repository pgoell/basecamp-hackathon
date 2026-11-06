// The slide strip at the left: thumbnails to pick, drag to reorder, and the new slide menu.
import { useState } from "react";
import { type Doc, type Slide, SLIDE_W, newId } from "./doc";
import { LAYOUTS, type Layout, slideFor } from "./layouts";
import { SlideView } from "./view";

const THUMB = 150;

export function Strip({ doc, current, pick, change }: { doc: Doc; current: string; pick: (id: string) => void; change: (doc: Doc) => void }) {
  const [drag, setDrag] = useState<number | null>(null);
  const at = Math.max(0, doc.slides.findIndex((s) => s.id === current));
  const put = (slides: Slide[], focus: string) => {
    change({ ...doc, slides });
    pick(focus);
  };
  const add = (layout: Layout) => {
    const s = slideFor(layout);
    put([...doc.slides.slice(0, at + 1), s, ...doc.slides.slice(at + 1)], s.id);
  };
  const duplicate = () => {
    const src = doc.slides[at];
    const s: Slide = { ...structuredClone(src), id: newId(), elements: src.elements.map((el) => ({ ...structuredClone(el), id: newId() })) };
    put([...doc.slides.slice(0, at + 1), s, ...doc.slides.slice(at + 1)], s.id);
  };
  const remove = () => {
    if (doc.slides.length < 2) return;
    const rest = doc.slides.filter((_, i) => i !== at);
    put(rest, rest[Math.min(at, rest.length - 1)].id);
  };

  return (
    <aside className="strip">
      <div className="strip-tools">
        <select value="" title="New slide" onChange={(e) => e.target.value && add(e.target.value as Layout)}>
          <option value="">+ New slide</option>
          {Object.entries(LAYOUTS).map(([k, name]) => <option key={k} value={k}>{name}</option>)}
        </select>
        <button title="Duplicate slide" onClick={duplicate}>Copy</button>
        <button title="Delete slide" onClick={remove} disabled={doc.slides.length < 2}>Delete</button>
      </div>
      <ol>
        {doc.slides.map((s, i) => (
          <li
            key={s.id}
            className={s.id === current ? "on" : undefined}
            draggable
            onDragStart={() => setDrag(i)}
            onDragOver={(e) => e.preventDefault()}
            onDrop={() => {
              if (drag === null || drag === i) return;
              const slides = [...doc.slides];
              const [moved] = slides.splice(drag, 1);
              slides.splice(i, 0, moved);
              setDrag(null);
              put(slides, moved.id);
            }}
            onClick={() => pick(s.id)}
          >
            <span className="n">{i + 1}</span>
            <SlideView doc={doc} slide={s} k={THUMB / SLIDE_W} />
          </li>
        ))}
      </ol>
    </aside>
  );
}
