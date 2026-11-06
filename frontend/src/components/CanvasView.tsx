import { useCanvas } from "../api/useCanvas";
import { BlockView } from "../blocks/BlockView";
import { Window } from "./Window";

export function CanvasView({ canvasId }: { canvasId: number | null }) {
  const { canvas, connected } = useCanvas(canvasId);

  if (!canvasId) {
    return (
      <Window title="Canvas" className="canvas-win">
        <div className="welcome">
          <pre className="welcome-art" aria-hidden>{`   ┌──────────┐
   │ ▓▓▓▓▓▓▓▓ │
   │ ▓ RFP  ▓ │
   │ ▓▓▓▓▓▓▓▓ │
   └──┬────┬──┘
      ▼    ▼
   [ agents ]`}</pre>
          <p className="welcome-line mono">
            &gt; pick a team, drop an RFP, press RUN<span className="cursor">_</span>
          </p>
          <p className="muted small">Each agent writes to this canvas live while the team works.</p>
        </div>
      </Window>
    );
  }

  return (
    <Window
      title={canvas?.title ?? "Connecting…"}
      className="canvas-win"
      led={connected ? "on" : "off"}
      tools={
        canvas && (
          <div className="toolbar mono tiny">
            <span>v{canvas.version}</span>
            <span>{canvas.blocks.length} blocks</span>
            <span>{connected ? "● live" : "○ reconnecting"}</span>
          </div>
        )
      }
    >
      {!canvas ? (
        <p className="muted mono">Dialling in…</p>
      ) : (
        <div className="canvas-grid">
          {canvas.blocks.map((b) => (
            <BlockView key={b.id} block={b} />
          ))}
        </div>
      )}
    </Window>
  );
}
