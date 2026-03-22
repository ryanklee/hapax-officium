import { useContext } from "react";
import { AgentRunCtx } from "../contexts/AgentRunContextDefs";
import type { AgentRunState } from "../contexts/AgentRunContextDefs";

export type { AgentRunState };

export function useAgentRun(): AgentRunState {
  const ctx = useContext(AgentRunCtx);
  if (!ctx) throw new Error("useAgentRun must be used within AgentRunProvider");
  return ctx;
}
