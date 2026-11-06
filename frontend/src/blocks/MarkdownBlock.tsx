import Markdown from "react-markdown";
import type { BlockPropsByType } from "./types";

export function MarkdownBlock({ props }: { props: BlockPropsByType["markdown"] }) {
  return (
    <div className="markdown">
      <Markdown>{props.text}</Markdown>
    </div>
  );
}
