const BASE = "/api";

async function get<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

async function post<T>(path: string, body?: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: body ? { "Content-Type": "application/json" } : {},
    body: body ? JSON.stringify(body) : undefined,
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

async function put<T>(path: string, body: unknown): Promise<T> {
  const res = await fetch(`${BASE}${path}`, {
    method: "PUT",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

async function del<T>(path: string): Promise<T> {
  const res = await fetch(`${BASE}${path}`, { method: "DELETE" });
  if (!res.ok) throw new Error(`API ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  nudges: () => get<import("./types").Nudge[]>("/nudges"),
  briefing: () => get<import("./types").BriefingData | null>("/briefing"),
  goals: () => get<import("./types").GoalSnapshot>("/goals"),
  agents: () => get<import("./types").AgentInfo[]>("/agents"),
  management: () => get<import("./types").ManagementSnapshot>("/management"),
  demos: () => get<import("./types").Demo[]>("/demos"),
  demo: (id: string) => get<import("./types").Demo>(`/demos/${id}`),
  deleteDemo: (id: string) => del<{ deleted: string }>(`/demos/${id}`),
  cycleMode: () => get<import("./types").CycleModeResponse>("/cycle-mode"),
  setCycleMode: (mode: "dev" | "prod") => put<import("./types").CycleModeResponse>("/cycle-mode", { mode }),
  scoutDecisions: () => get<import("./types").ScoutDecisionsResponse>("/scout/decisions"),
  scoutDecide: (component: string, decision: string, notes?: string) =>
    post<import("./types").ScoutDecision>(`/scout/${component}/decide`, { decision, notes: notes ?? "" }),
  okrs: () => get<import("./types").OKRSnapshot>("/okrs"),
  smartGoals: () => get<import("./types").SmartGoalSnapshot>("/smart-goals"),
  incidents: () => get<import("./types").IncidentSnapshot>("/incidents"),
  postmortemActions: () => get<import("./types").PostmortemActionSnapshot>("/postmortem-actions"),
  reviewCycles: () => get<import("./types").ReviewCycleSnapshot>("/review-cycles"),
  statusReports: () => get<import("./types").StatusReportSnapshot>("/status-reports"),
  // POST/DELETE/PUT helpers exposed for mutations
  post,
  del,
  put,
};
