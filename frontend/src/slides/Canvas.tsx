// The slide being edited: picks, drags, resizes and turns elements with react-moveable, as blattwerk's Stage does.
import Moveable from "react-moveable";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { type Doc, type El, type Para, type Slide, SLIDE_H, SLIDE_W } from "./doc";
import { SlideView } from "./view";

const r1 = (n: number) => Math.round(n * 10) / 10;

export function Canvas({ doc, slide, picked, setPicked, editing, setEditing, onElements, onText, onCell }: {
  doc: Doc;
  slide: Slide;
  picked: string[];
  setPicked: (ids: string[]) => void;
  editing: string | null;
  setEditing: (id: string | null) => void;
  onElements: (els: El[]) => void;
  onText: (id: string, paras: Para[]) => void;
  onCell: (id: string, row: number, col: number, text: string) => void;
}) {
  const host = useRef<HTMLDivElement>(null);
  const [k, setK] = useState(0);
  const [targets, setTargets] = useState<HTMLElement[]>([]);

  useLayoutEffect(() => {
    const el = host.current!;
    const fit = () => setK(Math.max(0.2, Math.min((el.clientWidth - 48) / SLIDE_W, (el.clientHeight - 48) / SLIDE_H)));
    fit();
    const watch = new ResizeObserver(fit);
    watch.observe(el);
    return () => watch.disconnect();
  }, []);

  // Moveable takes the DOM nodes of the picked elements, found after each draw.
  useEffect(() => {
    const nodes = picked.map((id) => host.current!.querySelector<HTMLElement>(`.slide .el[data-id="${id}"]`)).filter((n): n is HTMLElement => !!n);
    setTargets(editing ? [] : nodes);
  }, [picked, slide, k, editing]);

  // Reads each moved node's box back into its element.
  function commit(nodes: (HTMLElement | SVGElement)[]) {
    const moved = new Map(
      nodes.map((n) => {
        const s = (n as HTMLElement).style;
        const turn = s.transform.match(/rotate\((-?[\d.]+)deg\)/);
        return [
          (n as HTMLElement).dataset.id!,
          { x: r1(parseFloat(s.left) / k), y: r1(parseFloat(s.top) / k), w: r1(parseFloat(s.width) / k), h: r1(parseFloat(s.height) / k), rotation: turn ? r1(((+turn[1] % 360) + 360) % 360) : 0 },
        ];
      }),
    );
    onElements(slide.elements.map((el) => (moved.has(el.id) ? { ...el, ...moved.get(el.id)!, ...(moved.get(el.id)!.rotation ? {} : { rotation: undefined }) } : el)));
  }

  const others = slide.elements.filter((el) => !picked.includes(el.id)).map((el) => `.slide .el[data-id="${el.id}"]`);
  const single = targets.length === 1;

  return (
    <div
      className="canvas"
      ref={host}
      onMouseDown={(e) => {
        const t = e.target as Element;
        if (t.closest(".moveable-control-box") || t.closest(".field") || t.closest("td[contenteditable=true]")) return;
        const id = t.closest<HTMLElement>(".slide .el")?.dataset.id;
        if (editing && id !== editing) setEditing(null);
        if (!id) return setPicked([]);
        if (e.shiftKey) setPicked(picked.includes(id) ? picked.filter((p) => p !== id) : [...picked, id]);
        else if (!picked.includes(id)) setPicked([id]);
      }}
      onDoubleClick={(e) => {
        const id = (e.target as Element).closest<HTMLElement>(".slide .el")?.dataset.id;
        const el = slide.elements.find((x) => x.id === id);
        if (el && (el.type === "text" || el.type === "shape" || el.type === "table")) {
          setPicked([el.id]);
          setEditing(el.id);
        }
      }}
    >
      {k > 0 && <SlideView doc={doc} slide={slide} k={k} editing={editing ?? undefined} onText={onText} onCell={onCell} />}
      {k > 0 && targets.length > 0 && (
        <Moveable
          target={single ? targets[0] : targets}
          draggable
          resizable={single}
          rotatable={single}
          keepRatio={single && slide.elements.find((el) => el.id === picked[0])?.type === "image"}
          snappable
          snapThreshold={6}
          isDisplaySnapDigit={false}
          elementGuidelines={others}
          verticalGuidelines={[0, (SLIDE_W * k) / 2, SLIDE_W * k]}
          horizontalGuidelines={[0, (SLIDE_H * k) / 2, SLIDE_H * k]}
          snapContainer={host.current?.querySelector<HTMLElement>(".slide") ?? undefined}
          origin={false}
          onDrag={({ target, left, top }) => {
            target.style.left = `${left}px`;
            target.style.top = `${top}px`;
          }}
          onDragEnd={({ target, isDrag }) => isDrag && commit([target])}
          onDragGroup={({ events }) =>
            events.forEach(({ target, left, top }) => {
              target.style.left = `${left}px`;
              target.style.top = `${top}px`;
            })
          }
          onDragGroupEnd={({ targets: moved, isDrag }) => isDrag && commit(moved)}
          onResize={({ target, width, height, drag }) => {
            target.style.width = `${width}px`;
            target.style.height = `${height}px`;
            target.style.left = `${drag.left}px`;
            target.style.top = `${drag.top}px`;
          }}
          onResizeEnd={({ target, isDrag }) => isDrag && commit([target])}
          onRotate={({ target, rotation }) => {
            target.style.transform = `rotate(${rotation}deg)`;
          }}
          onRotateEnd={({ target, isDrag }) => isDrag && commit([target])}
        />
      )}
    </div>
  );
}
