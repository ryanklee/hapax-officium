import { useCallback, useMemo, useState, type ReactNode } from "react";
import { useSSE } from "../hooks/useSSE";
import { useTerrainActions } from "../hooks/useTerrain";
import type { AgentInfo } from "../api/types";
import { AgentRunCtx } from "./AgentRunContextDefs";

export function AgentRunProvider({ children }: { children: ReactNode }) {
  const sse = useSSE();
  const [agentName, setAgentName] = useState<string | null>(null);
  const [startedAt, setStartedAt] = useState<number | null>(null);
  const { setOverlay, setInvestigationTab } = useTerrainActions();

  const runAgent = useCallback(
    (agent: AgentInfo, flags: string[]) => {
      setAgentName(agent.name);
      setStartedAt(Date.now());
      sse.start(`/api/agents/${agent.name}/run`, { flags });
      setOverlay("investigation");
      setInvestigationTab("output");
    },
    [sse, setOverlay, setInvestigationTab],
  );

  const cancelAgent = useCallback(() => {
    sse.cancel();
    fetch("/api/agents/runs/current", { method: "DELETE" }).catch(() => {});
  }, [sse]);

  const clearOutput = useCallback(() => {
    sse.clear();
    setAgentName(null);
    setStartedAt(null);
  }, [sse]);

  const value = useMemo(
    () => ({
      lines: sse.lines,
      isRunning: sse.isRunning,
      error: sse.error,
      agentName,
      startedAt,
      runAgent,
      cancelAgent,
      clearOutput,
    }),
    [sse.lines, sse.isRunning, sse.error, agentName, startedAt, runAgent, cancelAgent, clearOutput],
  );

  return <AgentRunCtx.Provider value={value}>{children}</AgentRunCtx.Provider>;
}
