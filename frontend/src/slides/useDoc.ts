// Loads a presentation, keeps undo, saves each change with the version it was based on, and picks up changes made
// elsewhere (the chat agent, a teammate) by polling. Saves follow blattwerk's rule: a stale version answers 409, and
// then the server's doc wins.
import { useCallback, useEffect, useRef, useState } from "react";
import { Refusal, getPresentation, saveDoc } from "./api";
import type { Doc } from "./doc";
import { type Hist, alike, redone, stepped, undone } from "./history";

const POLL_MS = 3000;
const SAVE_MS = 500;

export function useDoc(id: number) {
  const [hist, setHist] = useState<Hist | null>(null);
  const [title, setTitle] = useState("");
  const [note, setNote] = useState("");
  const server = useRef<{ version: number; doc: Doc } | null>(null);
  const saving = useRef(false);
  const histRef = useRef(hist);
  histRef.current = hist;
  // Set while a text field is open: a reload then would throw away what is being typed.
  const busy = useRef(false);

  const pull = useCallback(async () => {
    const p = await getPresentation(id);
    setTitle(p.title);
    if (server.current && p.version <= server.current.version) return;
    server.current = { version: p.version, doc: p.doc };
    setHist((h) => (h ? stepped(h, p.doc, false) : { past: [], doc: p.doc, future: [] }));
  }, [id]);

  useEffect(() => {
    server.current = null;
    setHist(null);
    pull().catch(() => setNote("Could not load the presentation."));
  }, [pull]);

  const dirty = !!hist && !!server.current && !alike(hist.doc, server.current.doc);

  // Save the doc a moment after the last change.
  useEffect(() => {
    if (!dirty || saving.current) return;
    const timer = setTimeout(async () => {
      const doc = histRef.current!.doc;
      saving.current = true;
      try {
        const p = await saveDoc(id, doc, server.current!.version);
        server.current = { version: p.version, doc };
        setNote("");
      } catch (e) {
        if (e instanceof Refusal && e.status === 409) {
          setNote("Someone else changed this presentation. Their version is loaded.");
          await pull();
          setHist((h) => h && { ...h, doc: server.current!.doc });
        } else if (e instanceof Refusal && e.status === 422) {
          setNote(`Not saved: ${e.problems.join("; ")}`);
          server.current = { ...server.current!, doc };
        } else setNote("Not saved, retrying.");
      } finally {
        saving.current = false;
        // A change made while saving needs a save of its own.
        setHist((h) => h && { ...h });
      }
    }, SAVE_MS);
    return () => clearTimeout(timer);
  }, [hist, dirty, id, pull]);

  // Pick up changes from elsewhere while nothing waits to be saved here.
  useEffect(() => {
    const timer = setInterval(() => {
      if (!saving.current && !busy.current && !document.hidden && histRef.current && server.current && alike(histRef.current.doc, server.current.doc))
        pull().catch(() => {});
    }, POLL_MS);
    return () => clearInterval(timer);
  }, [pull]);

  const change = useCallback((doc: Doc, merge = false) => setHist((h) => h && stepped(h, doc, merge)), []);
  const undo = useCallback(() => setHist((h) => h && undone(h)), []);
  const redo = useCallback(() => setHist((h) => h && redone(h)), []);

  return { doc: hist?.doc ?? null, title, setTitle, change, undo, redo, note, setNote, dirty, pull, busy };
}
