import type { BlockPropsByType } from "./types";

export function FileBlock({ props }: { props: BlockPropsByType["file"] }) {
  const ext = props.filename.split(".").pop()?.toUpperCase().slice(0, 4) ?? "FILE";
  return (
    <div className="file-row">
      <span className="doc-icon" aria-hidden>
        <span>{ext}</span>
      </span>
      <div className="file-meta">
        <strong className="truncate" title={props.filename}>
          {props.filename}
        </strong>
        {props.url ? (
          <a className="btn btn-primary btn-sm" href={props.url} download>
            ⬇ Download
          </a>
        ) : (
          <span className="mono tiny muted">
            not ready yet<span className="cursor">_</span>
          </span>
        )}
      </div>
    </div>
  );
}
