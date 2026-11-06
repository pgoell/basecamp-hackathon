import "@fontsource-variable/geist";
import "@fontsource-variable/geist-mono";
import "@fontsource/silkscreen";
import { createRoot } from "react-dom/client";
import { App } from "./App";
import { Editor } from "./slides/Editor";
import { List } from "./slides/List";
import { Print } from "./slides/Print";

// One page for every path: Bun serves index.html for all of them.
function Route() {
  const path = location.pathname;
  const editor = path.match(/^\/slides\/(\d+)/);
  const print = path.match(/^\/print\/(\d+)/);
  if (path !== "/") document.title = "PowerPointless";
  if (print) return <Print id={+print[1]} />;
  if (editor) return <Editor id={+editor[1]} />;
  if (path.startsWith("/slides")) return <List />;
  return <App />;
}

createRoot(document.getElementById("root")!).render(<Route />);
