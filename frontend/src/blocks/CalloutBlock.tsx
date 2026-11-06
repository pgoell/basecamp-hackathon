import type { BlockPropsByType } from "./types";

export function CalloutBlock({ props }: { props: BlockPropsByType["callout"] }) {
  return <div className={`callout callout-${props.tone}`}>{props.text}</div>;
}
