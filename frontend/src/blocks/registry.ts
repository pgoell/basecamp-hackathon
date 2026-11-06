// Block type -> component. To add a new kind of UI:
//   1. add the props model + block class in backend canvas/models.py
//   2. add its props to BlockPropsByType in ./types.ts
//   3. write the component and register it here
import type { ComponentType } from "react";
import { CalloutBlock } from "./CalloutBlock";
import { FileBlock } from "./FileBlock";
import { KeyValueBlock } from "./KeyValueBlock";
import { MarkdownBlock } from "./MarkdownBlock";
import { OrgBlock } from "./OrgBlock";
import { StatusBlock } from "./StatusBlock";
import { TableBlock } from "./TableBlock";
import type { BlockPropsByType, BlockType } from "./types";

type Registry = { [T in BlockType]: ComponentType<{ props: BlockPropsByType[T] }> };

export const blockRegistry: Registry = {
  markdown: MarkdownBlock,
  status: StatusBlock,
  table: TableBlock,
  kv: KeyValueBlock,
  callout: CalloutBlock,
  file: FileBlock,
  org: OrgBlock,
};

export function isKnownBlockType(type: string): type is BlockType {
  return type in blockRegistry;
}
