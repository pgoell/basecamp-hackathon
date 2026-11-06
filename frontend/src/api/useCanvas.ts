import { useEffect, useState } from "react";
import type { Canvas } from "../blocks/types";
import { api } from "./client";

/** Live canvas: subscribes to the backend's SSE stream and keeps the latest snapshot. */
export function useCanvas(canvasId: number | null) {
  const [canvas, setCanvas] = useState<Canvas | null>(null);
  const [connected, setConnected] = useState(false);

  useEffect(() => {
    if (!canvasId) return;
    const source = new EventSource(api.canvasStreamUrl(canvasId));
    source.onopen = () => setConnected(true);
    source.onerror = () => setConnected(false); // EventSource reconnects by itself
    source.onmessage = (e) => {
      const next = JSON.parse(e.data) as Canvas;
      // Ignore out-of-order snapshots after a reconnect.
      setCanvas((prev) =>
        prev && prev.id === next.id && prev.version > next.version ? prev : next,
      );
    };
    return () => {
      source.close();
      setConnected(false);
      setCanvas(null);
    };
  }, [canvasId]);

  return { canvas, connected };
}
