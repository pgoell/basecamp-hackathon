import type { Block } from "./types";

/** Rendered for block types the backend knows but this frontend doesn't yet. */
export function UnknownBlock({ block }: { block: Block }) {
  return (
    <details className="unknown">
      <summary>Unsupported block type “{block.type}”</summary>
      <pre>{JSON.stringify(block.props, null, 2)}</pre>
    </details>
  );
}
