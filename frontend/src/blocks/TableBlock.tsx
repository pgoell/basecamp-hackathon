import type { BlockPropsByType } from "./types";

export function TableBlock({ props }: { props: BlockPropsByType["table"] }) {
  return (
    <table>
      <thead>
        <tr>
          {props.columns.map((c) => (
            <th key={c}>{c}</th>
          ))}
        </tr>
      </thead>
      <tbody>
        {props.rows.map((row, i) => (
          <tr key={i}>
            {row.map((cell, j) => (
              <td key={j}>{cell ?? ""}</td>
            ))}
          </tr>
        ))}
      </tbody>
    </table>
  );
}
