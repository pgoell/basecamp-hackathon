import type { BlockPropsByType } from "./types";

export function FileBlock({ props }: { props: BlockPropsByType["file"] }) {
  return props.url ? (
    <a className="file" href={props.url} download>
      ⬇ {props.filename}
    </a>
  ) : (
    <span className="file muted">{props.filename} (not ready yet)</span>
  );
}
