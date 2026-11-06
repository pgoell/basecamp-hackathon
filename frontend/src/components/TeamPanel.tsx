import { useEffect, useState } from "react";
import { api, type Agent, type Rfp, type RunInput, type TeamDetail } from "../api/client";
import { Dropzone } from "./Dropzone";
import { Window } from "./Window";

interface Props {
  team: TeamDetail | null;
  error: string | null;
  onRun: (body: RunInput) => void;
  running: boolean;
}

function AgentRow({ agent, role }: { agent: Agent; role: string }) {
  return (
    <div className="roster-row" title={agent.description}>
      <span className={`dot dot-${role}`} aria-hidden />
      <span className="roster-name">{agent.name}</span>
      <span className="mono tiny muted">{agent.model.replace("claude-", "")}</span>
    </div>
  );
}

export function TeamPanel({ team, error, onRun, running }: Props) {
  const [text, setText] = useState("");
  const [rfp, setRfp] = useState<Rfp | null>(null);
  const [tab, setTab] = useState<"pdf" | "text">("text");

  useEffect(() => {
    setText(team?.sample_input ?? "");
    setRfp(null);
    setTab(team?.input_pdf ? "pdf" : "text");
  }, [team?.key]);

  if (error) return <p className="dialog dialog-danger">{error}</p>;
  if (!team) return <Window title="Loading">Booting the team…</Window>;

  const dynamic = team.mode === "dynamic";
  const useRfp = tab === "pdf" && rfp;
  const ready = tab === "pdf" ? Boolean(rfp) : true;

  return (
    <div className="stack">
      <Window title={team.name} tone="tomato">
        <div className="team-head">
          <span className={`tag ${dynamic ? "tag-teal" : "tag-ink"}`}>
            {dynamic ? "Dynamic staffing" : "Fixed roster"}
          </span>
        </div>
        <p className="lede">{team.description}</p>

        <h4 className="eyebrow">{dynamic ? "Orchestrator and lead pool" : "Roster"}</h4>
        <ul className="roster">
          <li>
            <AgentRow agent={team.coordinator_agent} role="coordinator" />
            <ul>
              {team.member_agents.map((a) => (
                <li key={a.key}>
                  <AgentRow agent={a} role="lead" />
                  {a.members.length > 0 && (
                    <ul>
                      {a.members.map((m) =>
                        team.sub_agents[m] ? (
                          <li key={m}>
                            <AgentRow agent={team.sub_agents[m]} role="specialist" />
                          </li>
                        ) : null,
                      )}
                    </ul>
                  )}
                </li>
              ))}
            </ul>
          </li>
        </ul>
        {dynamic && (
          <p className="small muted">
            The orchestrator reads the RFP and engages only the leads it needs. Leads with a crew brief
            their own specialists in parallel.
          </p>
        )}
      </Window>

      <Window
        title={team.input_label}
        tone="cobalt"
        tools={
          team.input_pdf && (
            <div className="segmented" role="tablist">
              <button role="tab" aria-selected={tab === "pdf"} onClick={() => setTab("pdf")}>
                PDF
              </button>
              <button role="tab" aria-selected={tab === "text"} onClick={() => setTab("text")}>
                Text
              </button>
            </div>
          )
        }
      >
        {tab === "pdf" ? (
          <Dropzone rfp={rfp} onChange={setRfp} disabled={running} />
        ) : (
          <textarea
            className="field"
            value={text}
            onChange={(e) => setText(e.target.value)}
            rows={12}
            spellCheck={false}
            placeholder={`Paste the ${team.input_label.toLowerCase()} here…`}
          />
        )}
        <button
          className="btn btn-primary btn-block"
          disabled={running || !ready}
          onClick={() => onRun(useRfp ? { rfp_id: rfp.id } : { input: text.trim() || null })}
        >
          {running ? "Starting…" : "▶ Run team"}
        </button>
      </Window>
    </div>
  );
}

export function useTeam(teamKey: string | null) {
  const [team, setTeam] = useState<TeamDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  useEffect(() => {
    if (!teamKey) return;
    let cancelled = false;
    setTeam(null);
    api
      .team(teamKey)
      .then((t) => {
        if (cancelled) return;
        setTeam(t);
        setError(null);
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [teamKey]);
  return { team, error };
}
