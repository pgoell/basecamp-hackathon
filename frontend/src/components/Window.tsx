import type { ReactNode } from "react";

export type Tone = "ink" | "tomato" | "teal" | "mustard" | "cobalt";
export type Led = "on" | "off" | "busy" | "error";

interface Props {
  title: ReactNode;
  tone?: Tone;
  led?: Led;
  /** A slim toolbar under the title bar. */
  tools?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** A retro desktop window: striped title bar, hard shadow, decorative controls. */
export function Window({ title, tone = "ink", led, tools, className = "", children }: Props) {
  return (
    <section className={`win win-${tone} ${className}`}>
      <header className="win-bar">
        <span className="win-box" aria-hidden />
        <span className="win-stripes" aria-hidden />
        <h2 className="win-title">{title}</h2>
        <span className="win-stripes" aria-hidden />
        {led && <span className={`led led-${led}`} title={led} />}
        <span className="win-ctrl" aria-hidden>
          <i>▁</i>
          <i>✕</i>
        </span>
      </header>
      {tools && <div className="win-tools">{tools}</div>}
      <div className="win-body">{children}</div>
    </section>
  );
}
