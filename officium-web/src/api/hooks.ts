import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { api } from "./client";
import type { NudgeActionResponse } from "./types";

const SLOW = 300_000; // 5min

export const useNudges = () =>
  useQuery({ queryKey: ["nudges"], queryFn: api.nudges, refetchInterval: SLOW });

export const useBriefing = () =>
  useQuery({ queryKey: ["briefing"], queryFn: api.briefing, refetchInterval: SLOW });

export const useGoals = () =>
  useQuery({ queryKey: ["goals"], queryFn: api.goals, refetchInterval: SLOW });

export const useAgents = () =>
  useQuery({ queryKey: ["agents"], queryFn: api.agents, staleTime: Infinity });

export const useManagement = () =>
  useQuery({ queryKey: ["management"], queryFn: api.management, refetchInterval: SLOW });

// --- Mutations ---

export function useNudgeAction() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ sourceId, action }: { sourceId: string; action: "act" | "dismiss" }) =>
      api.post<NudgeActionResponse>(`/nudges/${sourceId}/${action}`),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["nudges"] });
    },
  });
}

export function useCancelAgent() {
  return useMutation({
    mutationFn: () => api.del<{ status: string }>("/agents/runs/current"),
  });
}

// --- Working Mode ---

export const useWorkingMode = () =>
  useQuery({ queryKey: ["workingMode"], queryFn: api.workingMode, refetchInterval: SLOW });

export function useSetWorkingMode() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (mode: "research" | "rnd") => api.setWorkingMode(mode),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["workingMode"] });
    },
  });
}

/** @deprecated Use useWorkingMode. */
export const useCycleMode = useWorkingMode;

/** @deprecated Use useSetWorkingMode. Accepts research/rnd, not dev/prod. */
export const useSetCycleMode = useSetWorkingMode;

// --- Scout Decisions ---

export const useScoutDecisions = () =>
  useQuery({ queryKey: ["scoutDecisions"], queryFn: api.scoutDecisions, refetchInterval: SLOW });

export function useScoutDecide() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: ({ component, decision, notes }: { component: string; decision: string; notes?: string }) =>
      api.scoutDecide(component, decision, notes),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["scoutDecisions"] });
    },
  });
}

// --- Demos ---

export const useDemos = () =>
  useQuery({ queryKey: ["demos"], queryFn: api.demos, refetchInterval: SLOW });

export function useDeleteDemo() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (id: string) => api.deleteDemo(id),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["demos"] });
    },
  });
}

// --- Tier 1 Expansion ---

export const useOKRs = () =>
  useQuery({ queryKey: ["okrs"], queryFn: api.okrs, refetchInterval: SLOW });

export const useSmartGoals = () =>
  useQuery({ queryKey: ["smartGoals"], queryFn: api.smartGoals, refetchInterval: SLOW });

export const useIncidents = () =>
  useQuery({ queryKey: ["incidents"], queryFn: api.incidents, refetchInterval: SLOW });

export const usePostmortemActions = () =>
  useQuery({ queryKey: ["postmortemActions"], queryFn: api.postmortemActions, refetchInterval: SLOW });

export const useReviewCycles = () =>
  useQuery({ queryKey: ["reviewCycles"], queryFn: api.reviewCycles, refetchInterval: SLOW });

export const useStatusReports = () =>
  useQuery({ queryKey: ["statusReports"], queryFn: api.statusReports, refetchInterval: SLOW });
