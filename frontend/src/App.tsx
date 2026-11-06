import { useEffect, useState } from "react";
import { api, type TeamSummary } from "./api/client";
import { CanvasView } from "./components/CanvasView";
import { TeamPanel } from "./components/TeamPanel";

export function App() {
  const [teams, setTeams] = useState<TeamSummary[]>([]);
  const [teamKey, setTeamKey] = useState<string | null>(null);
  const [canvasId, setCanvasId] = useState<number | null>(null);
  const [running, setRunning] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    api
      .teams()
      .then((t) => {
        setTeams(t);
        setTeamKey((k) => k ?? t[0]?.key ?? null);
      })
      .catch((e: Error) => setError(e.message));
  }, []);

  async function run(input: string | null) {
    if (!teamKey) return;
    setRunning(true);
    setError(null);
    try {
      const { canvas_id } = await api.startRun(teamKey, input);
      setCanvasId(canvas_id);
    } catch (e) {
      setError((e as Error).message);
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="layout">
      <header className="topbar">
        <strong>Basecamp</strong>
        <nav>
          {teams.map((t) => (
            <button
              key={t.key}
              className={t.key === teamKey ? "tab active" : "tab"}
              onClick={() => setTeamKey(t.key)}
            >
              {t.name}
            </button>
          ))}
        </nav>
      </header>
      {error && <p className="callout callout-danger">{error}</p>}
      <main>
        <aside>{teamKey && <TeamPanel teamKey={teamKey} onRun={run} running={running} />}</aside>
        <CanvasView canvasId={canvasId} />
      </main>
    </div>
  );
}
