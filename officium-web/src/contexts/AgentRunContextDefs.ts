import { createContext } from "react";
import type { AgentInfo } from "../api/types";

export interface AgentRunState {
  lines: string[];
  isRunning: boolean;
  error: string | null;
  agentName: string | null;
  startedAt: number | null;
  runAgent: (agent: AgentInfo, flags: string[]) => void;
  cancelAgent: () => void;
  clearOutput: () => void;
}

export const AgentRunCtx = createContext<AgentRunState | null>(null);
