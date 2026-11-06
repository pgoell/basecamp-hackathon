import type { ComponentType } from "react";
import { blockRegistry, isKnownBlockType } from "./registry";
import type { Block } from "./types";
import { UnknownBlock } from "./UnknownBlock";

export function BlockView({ block }: { block: Block }) {
  let body;
  if (isKnownBlockType(block.type)) {
    // The registry is keyed by type, so the props shape matches at runtime.
    const Component = blockRegistry[block.type] as ComponentType<{ props: unknown }>;
    body = <Component props={block.props} />;
  } else {
    body = <UnknownBlock block={block} />;
  }
  return (
    <section className={`block block-${block.type}`} data-block-id={block.id}>
      {(block.title || block.agent) && (
        <header>
          {block.title && <h3>{block.title}</h3>}
          {block.agent && <span className="agent">{block.agent}</span>}
        </header>
      )}
      {body}
    </section>
  );
}
