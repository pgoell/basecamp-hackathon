import { useEffect, useState } from "react";
import { api, type TeamDetail } from "../api/client";

interface Props {
  teamKey: string;
  onRun: (input: string | null) => void;
  running: boolean;
}

export function TeamPanel({ teamKey, onRun, running }: Props) {
  const [team, setTeam] = useState<TeamDetail | null>(null);
  const [input, setInput] = useState("");
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .team(teamKey)
      .then((t) => {
        if (cancelled) return;
        setTeam(t);
        setInput(t.sample_input ?? "");
        setError(null);
      })
      .catch((e: Error) => !cancelled && setError(e.message));
    return () => {
      cancelled = true;
    };
  }, [teamKey]);

  if (error) return <p className="callout callout-danger">{error}</p>;
  if (!team) return <p className="muted">Loading…</p>;

  return (
    <div className="team-panel">
      <h2>{team.name}</h2>
      <p className="muted">{team.description}</p>
      <h4>Roster</h4>
      <ul className="roster">
        <li>
          <strong>{team.coordinator_agent.name}</strong> <span className="agent">coordinator</span>
          <div className="muted small">{team.coordinator_agent.model}</div>
        </li>
        {team.member_agents.map((a) => (
          <li key={a.key} title={a.description}>
            {a.name}
            <div className="muted small">
              {a.model}
              {a.skills.length > 0 && ` · ${a.skills.join(", ")}`}
            </div>
          </li>
        ))}
      </ul>
      <label>
        <h4>{team.input_label}</h4>
        <textarea value={input} onChange={(e) => setInput(e.target.value)} rows={10} />
      </label>
      <button disabled={running} onClick={() => onRun(input.trim() || null)}>
        {running ? "Running…" : "Run team"}
      </button>
    </div>
  );
}
