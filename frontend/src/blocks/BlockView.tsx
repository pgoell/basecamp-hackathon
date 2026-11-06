import type { ComponentType } from "react";
import { TONE, useRole } from "../components/roles";
import { blockRegistry, isKnownBlockType } from "./registry";
import type { Block } from "./types";
import { UnknownBlock } from "./UnknownBlock";

// Block types that take a single grid column; the rest span the canvas.
const NARROW = new Set(["status", "kv", "file"]);

export function BlockView({ block }: { block: Block }) {
  const role = useRole(block.agent);
  let body;
  if (isKnownBlockType(block.type)) {
    // The registry is keyed by type, so the props shape matches at runtime.
    const Component = blockRegistry[block.type] as ComponentType<{ props: unknown }>;
    body = <Component props={block.props} />;
  } else {
    body = <UnknownBlock block={block} />;
  }
  const wide = NARROW.has(block.type) ? "" : "card-wide";
  return (
    <section className={`card card-${block.type} ${wide}`} data-block-id={block.id}>
      {(block.title || block.agent) && (
        <header className="card-bar">
          <h3>{block.title ?? block.type}</h3>
          {block.agent && <span className={`badge badge-${role ? TONE[role] : "ink"}`}>{block.agent}</span>}
        </header>
      )}
      <div className="card-body">{body}</div>
    </section>
  );
}
