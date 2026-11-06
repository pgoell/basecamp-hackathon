// All presentations: open one, make one, delete one.
import { useEffect, useState } from "react";
import { ask } from "./api";
import { type Presentation, SLIDE_W } from "./doc";
import { SlideView } from "./view";

export function List() {
  const [list, setList] = useState<Presentation[] | null>(null);
  const load = () => ask<Presentation[]>("/presentations").then(setList);
  useEffect(() => void load(), []);

  async function create() {
    const title = prompt("Title of the new presentation", "Untitled presentation")?.trim();
    if (!title) return;
    const p = await ask<Presentation>("/presentations", { method: "POST", json: { title } });
    location.href = `/slides/${p.id}`;
  }

  return (
    <div className="slides-app list">
      <header className="bar">
        <span className="brand">PowerPointless</span>
        <button onClick={create}>New presentation</button>
        <a href="/" className="aside">Deal Desk</a>
      </header>
      {!list && <p className="hint">Loading…</p>}
      {list?.length === 0 && <p className="hint">No presentations yet.</p>}
      <ul className="cards">
        {list?.map((p) => (
          <li key={p.id}>
            <a href={`/slides/${p.id}`}>
              {p.doc.slides[0] && <SlideView doc={p.doc} slide={p.doc.slides[0]} k={240 / SLIDE_W} />}
              <strong>{p.title}</strong>
              <small>{p.doc.slides.length} slides, {new Date(p.updated + (p.updated.endsWith("Z") ? "" : "Z")).toLocaleString()}</small>
            </a>
            <button
              className="del"
              title="Delete"
              onClick={async () => {
                if (!confirm(`Delete "${p.title}"?`)) return;
                await ask(`/presentations/${p.id}`, { method: "DELETE" });
                load();
              }}
            >
              ×
            </button>
          </li>
        ))}
      </ul>
    </div>
  );
}
