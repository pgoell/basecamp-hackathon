import type { BlockPropsByType } from "./types";

export function StatusBlock({ props }: { props: BlockPropsByType["status"] }) {
  return (
    <div className="status">
      <span className={`pill pill-${props.state}`}>{props.state}</span>
      {props.detail && <span className="muted">{props.detail}</span>}
    </div>
  );
}
