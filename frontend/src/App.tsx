import { useEffect, useMemo, useState } from "react";
import { api, type RunInput, type TeamSummary } from "./api/client";
import { CanvasView } from "./components/CanvasView";
import { RolesContext, rolesOf } from "./components/roles";
import { TeamPanel, useTeam } from "./components/TeamPanel";

function Clock() {
  const [now, setNow] = useState(() => new Date());
  useEffect(() => {
    const id = setInterval(() => setNow(new Date()), 15_000);
    return () => clearInterval(id);
  }, []);
  return <span className="mono">{now.toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>;
}

export function App() {
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [teamKey, setTeamKey] = useState<string | null>(null);
  const [canvasId, setCanvasId] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [swarm, setSwarm] = useState<boolean | null>(null);
  const { team, error: teamError } = useTeam(teamKey);
  const roles = useMemo(() => rolesOf(team), [team]);

  useEffect(() => {
    api
      .teams()
      .then((t) => {
        setTeams(t);
        setTeamKey((k) => k ?? t[0]?.key ?? null);
      })
      .catch((e: Error) => setError(e.message));
    api
      .health()
      .then((h) => setSwarm(h.swarm))
      .catch(() => setSwarm(false));
  }, []);

  async function run(body: RunInput) {
    if (!teamKey) return;
    setRunning(true);
    setError(null);
    try {
      const { canvas_id } = await api.startRun(teamKey, body);
      setCanvasId(canvas_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="bc">
      <header className="menubar">
        <span className="logo">
          <span className="logo-mark" aria-hidden>
            ▲
          </span>
          Basecamp
        </span>
        <nav className="menu" aria-label="Teams">
          {teams.map((t) => (
            <button
              key={t.key}
              className={t.key === teamKey ? "menu-item is-active" : "menu-item"}
              onClick={() => setTeamKey(t.key)}
            >
              {t.name}
              {t.mode === "dynamic" && <span className="menu-new">new</span>}
            </button>
          ))}
        </nav>
        <span className="menubar-right">
          <a className="menu-item" href="/slides">
            PowerPointless ↗
          </a>
          <span className="sys" title={swarm ? "agents are set up" : "agents not set up (swarm.json)"}>
            <span className={`led ${swarm ? "led-on" : swarm === false ? "led-error" : "led-off"}`} />
            <span className="mono small">{swarm ? "swarm ready" : "no swarm"}</span>
          </span>
          <Clock />
        </span>
      </header>
      {error && <p className="dialog dialog-danger banner">{error}</p>}
      <RolesContext.Provider value={roles}>
        <main className="desktop">
          <aside className="sidebar">
            <TeamPanel team={team} error={teamError} onRun={run} running={running} />
          </aside>
          <CanvasView canvasId={canvasId} />
        </main>
      </RolesContext.Provider>
      <footer className="statusbar mono tiny">
        <span>Claude Managed Agents</span>
        <span>{team ? `${team.name} · ${team.member_agents.length} on the roster` : "—"}</span>
        <span>{canvasId ? `canvas #${canvasId}` : "no run yet"}</span>
      </footer>
    </div>
  );
}
