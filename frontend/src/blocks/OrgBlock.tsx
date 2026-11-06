import type { ReactElement } from "react";
import type { BlockPropsByType, NodeState, OrgNode } from "./types";

const LED: Record<NodeState, string> = { idle: "off", queued: "off", running: "busy", done: "on", failed: "error" };

// One connector segment per level of depth, drawn in CSS so lines join across rows.
type Seg = "pipe" | "blank" | "tee" | "elbow";

function Row({ node, segs, depth }: { node: OrgNode; segs: Seg[]; depth: number }) {
  return (
    <li className={`org-row org-${node.state} org-depth-${Math.min(depth, 2)}`}>
      {segs.map((seg, i) => (
        <span key={i} className={`org-seg org-seg-${seg}`} aria-hidden />
      ))}
      <span className={`led led-${LED[node.state]}`} />
      <span className="org-name">{node.name}</span>
      <span className={`state state-${node.state}`}>{node.state === "idle" ? "bench" : node.state}</span>
      {node.detail && <span className="org-detail muted small">{node.detail}</span>}
      {node.state === "running" && <span className="barber barber-sm" aria-hidden />}
    </li>
  );
}

/** The live team tree: orchestrator → leads → specialists, with tree connectors. */
export function OrgBlock({ props }: { props: BlockPropsByType["org"] }) {
  const ids = new Set(props.nodes.map((n) => n.id));
  const children = new Map<string | null, OrgNode[]>();
  for (const n of props.nodes) {
    const parent = n.parent && ids.has(n.parent) ? n.parent : null;
    children.set(parent, [...(children.get(parent) ?? []), n]);
  }

  const rows: ReactElement[] = [];
  function walk(parent: string | null, lead: Seg[], depth: number) {
    const kids = children.get(parent) ?? [];
    kids.forEach((n, i) => {
      const last = i === kids.length - 1;
      const segs: Seg[] = depth === 0 ? [] : [...lead, last ? "elbow" : "tee"];
      rows.push(<Row key={n.id} node={n} segs={segs} depth={depth} />);
      walk(n.id, depth === 0 ? [] : [...lead, last ? "blank" : "pipe"], depth + 1);
    });
  }
  walk(null, [], 0);

  const roots = new Set((children.get(null) ?? []).map((n) => n.id));
  const leads = props.nodes.filter((n) => n.parent && roots.has(n.parent));
  const engaged = leads.filter((n) => n.state !== "idle").length;
  const busy = props.nodes.filter((n) => n.state === "running").length;
  const done = props.nodes.filter((n) => n.state === "done").length;

  return (
    <div className="org">
      <div className="org-stats mono tiny">
        <span>
          <b>{engaged}</b>/{leads.length} leads engaged
        </span>
        <span>
          <b>{busy}</b> working
        </span>
        <span>
          <b>{done}</b> done
        </span>
      </div>
      <ul className="org-tree">{rows}</ul>
    </div>
  );
}
