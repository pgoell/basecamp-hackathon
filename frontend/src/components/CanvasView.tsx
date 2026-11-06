import { useCanvas } from "../api/useCanvas";
import { BlockView } from "../blocks/BlockView";

export function CanvasView({ canvasId }: { canvasId: number | null }) {
  const { canvas, connected } = useCanvas(canvasId);

  if (!canvasId) {
    return <p className="muted empty">Pick a team and run it. Its agents write here.</p>;
  }
  if (!canvas) return <p className="muted empty">Connecting…</p>;

  return (
    <div className="canvas">
      <div className="canvas-head">
        <h2>{canvas.title}</h2>
        <span className={`dot ${connected ? "dot-on" : ""}`} title="live" />
        <span className="muted small">v{canvas.version}</span>
      </div>
      {canvas.blocks.map((b) => (
        <BlockView key={b.id} block={b} />
      ))}
    </div>
  );
}
