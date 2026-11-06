// The page headless Chromium prints to PDF: one slide per page at 1 px per pt, which is 13.333 x 7.5 in. Sets
// window.__slidesReady once fonts and images are in, as blattwerk's print page tells pdf.py.
import { useEffect, useState } from "react";
import { getPresentation } from "./api";
import type { Presentation } from "./doc";
import { SlideView } from "./view";

declare global {
  interface Window { __slidesReady?: boolean }
}

export function Print({ id }: { id: number }) {
  const [p, setP] = useState<Presentation | null>(null);
  useEffect(() => void getPresentation(id).then(setP), [id]);
  useEffect(() => {
    if (!p) return;
    const images = [...document.images].map((img) => (img.complete ? null : new Promise((ok) => (img.onload = img.onerror = ok))));
    Promise.all([document.fonts.ready, ...images]).then(() => (window.__slidesReady = true));
  }, [p]);
  if (!p) return null;
  return (
    <div className="print">
      {p.doc.slides.map((s) => (
        <div className="page" key={s.id}>
          <SlideView doc={p.doc} slide={s} k={96 / 72} />
        </div>
      ))}
    </div>
  );
}
