import type { BlockPropsByType } from "./types";

const ICON = { info: "i", success: "✓", warning: "!", danger: "✕" } as const;

export function CalloutBlock({ props }: { props: BlockPropsByType["callout"] }) {
  return (
    <div className={`dialog dialog-${props.tone}`}>
      <span className="dialog-icon" aria-hidden>
        {ICON[props.tone]}
      </span>
      <span>{props.text}</span>
    </div>
  );
}
