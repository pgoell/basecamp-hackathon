import type { BlockPropsByType } from "./types";

const LED = { queued: "off", running: "busy", done: "on", failed: "error" } as const;

export function StatusBlock({ props }: { props: BlockPropsByType["status"] }) {
  return (
    <div className="status-row">
      <span className={`led led-${LED[props.state]}`} />
      <span className={`state state-${props.state}`}>{props.state}</span>
      {props.detail && <span className="muted small truncate">{props.detail}</span>}
      {props.state === "running" && <span className="barber" aria-hidden />}
    </div>
  );
}
