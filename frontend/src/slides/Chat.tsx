// The chat beside the slide: several chats per presentation, each with an agent that edits the deck through tools.
import { useEffect, useRef, useState } from "react";
import { BASE, ask } from "./api";

type Chat = { id: number; title: string };
type Block = { type: string; text?: string; name?: string; content?: unknown; is_error?: boolean };
type Stored = { role: "user" | "assistant"; content: string | Block[] };
type Line = { kind: "user" | "agent" | "tool" | "error"; text: string };

const NOTE = /^\[current slide:[^\]]*\]\s*/;

// What the stored messages show: the words, and one line per tool call.
function lines(messages: Stored[]): Line[] {
  return messages.flatMap((m): Line[] => {
    const blocks: Block[] = typeof m.content === "string" ? [{ type: "text", text: m.content }] : m.content;
    return blocks.flatMap((b): Line[] => {
      if (b.type === "text" && b.text) return [{ kind: m.role === "user" ? "user" : "agent", text: m.role === "user" ? b.text.replace(NOTE, "") : b.text }];
      if (b.type === "tool_use") return [{ kind: "tool", text: `⚙ ${b.name}` }];
      if (b.type === "tool_result" && b.is_error) return [{ kind: "error", text: typeof b.content === "string" ? b.content : "tool failed" }];
      return [];
    });
  });
}

export function ChatPanel({ presentation, slide, onDoc }: { presentation: number; slide: string; onDoc: () => void }) {
  const [chats, setChats] = useState<Chat[]>([]);
  const [chat, setChat] = useState<number | null>(null);
  const [shown, setShown] = useState<Line[]>([]);
  const [text, setText] = useState("");
  const [running, setRunning] = useState(false);
  const end = useRef<HTMLDivElement>(null);

  useEffect(() => {
    ask<Chat[]>(`/presentations/${presentation}/chats`).then((list) => {
      setChats(list);
      setChat(list[0]?.id ?? null);
    });
  }, [presentation]);
  useEffect(() => {
    if (chat === null) setShown([]);
    else ask<{ messages: Stored[] }>(`/chats/${chat}`).then((c) => setShown(lines(c.messages)));
  }, [chat]);
  useEffect(() => {
    end.current?.scrollIntoView({ block: "end" });
  }, [shown]);

  async function newChat() {
    const c = await ask<Chat>(`/presentations/${presentation}/chats`, { method: "POST", json: {} });
    setChats((list) => [c, ...list]);
    setChat(c.id);
    return c.id;
  }

  async function send() {
    const words = text.trim();
    if (!words || running) return;
    setText("");
    setRunning(true);
    const id = chat ?? (await newChat());
    setShown((s) => [...s, { kind: "user", text: words }]);
    try {
      const res = await fetch(`${BASE}/chats/${id}/messages`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ text: words, slide }),
      });
      if (!res.ok || !res.body) throw new Error(await res.text());
      const reader = res.body.pipeThrough(new TextDecoderStream()).getReader();
      let buf = "";
      let open = false; // whether the last line is agent text still being written
      for (;;) {
        const { value, done } = await reader.read();
        if (done) break;
        buf += value;
        const parts = buf.split("\n\n");
        buf = parts.pop()!;
        for (const part of parts) {
          const data = part.split("\n").find((l) => l.startsWith("data: "));
          if (!data) continue;
          const e = JSON.parse(data.slice(6));
          if (e.type === "text") {
            const was = open;
            setShown((s) => (was ? [...s.slice(0, -1), { kind: "agent", text: s.at(-1)!.text + e.text }] : [...s, { kind: "agent", text: e.text }]));
            open = true;
            continue;
          }
          open = false;
          if (e.type === "tool") setShown((s) => [...s, { kind: "tool", text: `⚙ ${e.name}` }]);
          else if (e.type === "tool_result" && !e.ok) setShown((s) => [...s, { kind: "error", text: e.text }]);
          else if (e.type === "doc") onDoc();
          else if (e.type === "error") setShown((s) => [...s, { kind: "error", text: e.message }]);
        }
      }
    } catch (err) {
      setShown((s) => [...s, { kind: "error", text: String(err) }]);
    } finally {
      setRunning(false);
      onDoc();
      ask<Chat[]>(`/presentations/${presentation}/chats`).then(setChats);
    }
  }

  return (
    <aside className="chat">
      <div className="chat-head">
        <select value={chat ?? ""} onChange={(e) => setChat(e.target.value ? +e.target.value : null)}>
          {chats.length === 0 && <option value="">New chat</option>}
          {chats.map((c) => <option key={c.id} value={c.id}>{c.title || "New chat"}</option>)}
        </select>
        <button onClick={newChat} disabled={running}>New chat</button>
      </div>
      <div className="chat-log">
        {shown.length === 0 && <p className="hint">Ask for slides, e.g. "Make a 5 slide deck about our Q3 results" or "make the title on this slide blue".</p>}
        {shown.map((l, i) => <div key={i} className={`msg ${l.kind}`}>{l.text}</div>)}
        {running && <div className="msg tool">…</div>}
        <div ref={end} />
      </div>
      <form
        className="chat-input"
        onSubmit={(e) => {
          e.preventDefault();
          send();
        }}
      >
        <textarea
          value={text}
          rows={3}
          placeholder="Message the slide agent"
          onChange={(e) => setText(e.target.value)}
          onKeyDown={(e) => {
            e.stopPropagation();
            if (e.key === "Enter" && !e.shiftKey) {
              e.preventDefault();
              send();
            }
          }}
        />
        <button type="submit" disabled={running || !text.trim()}>Send</button>
      </form>
    </aside>
  );
}
