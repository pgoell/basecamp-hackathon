import type { BlockPropsByType } from "./types";

export function KeyValueBlock({ props }: { props: BlockPropsByType["kv"] }) {
  return (
    <dl className="kv">
      {props.items.map((item) => (
        <div key={item.label}>
          <dt>{item.label}</dt>
          <dd>{item.value}</dd>
        </div>
      ))}
    </dl>
  );
}
