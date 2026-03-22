import { useEffect, useMemo, useState } from "react";
import type { RegionName, StimmungStance } from "../components/terrain/types";
import {
  useBriefing,
  useGoals,
  useIncidents,
  useManagement,
  useNudges,
  useOKRs,
  usePostmortemActions,
  useReviewCycles,
  useStatusReports,
} from "../api/hooks";

function clamp01(v: number): number {
  return Math.max(0, Math.min(1, v));
}

function stanceFromPressure(pressure: number): StimmungStance {
  if (pressure >= 0.6) return "critical";
  if (pressure >= 0.4) return "degraded";
  if (pressure >= 0.2) return "cautious";
  return "nominal";
}

export function useStimmung(): Record<RegionName, StimmungStance> {
  const { data: mgmt } = useManagement();
  const { data: nudges } = useNudges();
  const { data: okrs } = useOKRs();
  const { data: goals } = useGoals();
  const { data: briefing } = useBriefing();
  const { data: incidents } = useIncidents();
  const { data: postmortems } = usePostmortemActions();
  const { data: reviews } = useReviewCycles();
  const { data: statusReports } = useStatusReports();

  // Briefing age recomputed every 60s (avoid impure Date.now in render)
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const id = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(id);
  }, []);
  const briefingAgeHours = briefing?.generated_at
    ? (now - new Date(briefing.generated_at).getTime()) / 3_600_000
    : 48;

  return useMemo(() => {
    // Assembly: team health pressure
    const stale1on1s = mgmt?.people?.filter((p) => p.stale_1on1).length ?? 0;
    const highLoad = mgmt?.people?.filter((p) => (p.cognitive_load ?? 0) >= 4).length ?? 0;
    const overdueCoaching = mgmt?.coaching?.filter((c) => c.overdue).length ?? 0;
    const assemblyPressure = clamp01(stale1on1s * 0.15 + highLoad * 0.2 + overdueCoaching * 0.15);

    // Outlook: goal/strategic pressure
    const atRiskOKRs = okrs?.at_risk_count ?? 0;
    const staleGoals = goals?.stale_count ?? 0;
    const criticalNudges = nudges?.filter(
      (n) => n.priority_label === "critical" || n.priority_label === "high",
    ).length ?? 0;
    const outlookPressure = clamp01(
      atRiskOKRs * 0.2 + staleGoals * 0.1 + criticalNudges * 0.15 + (briefingAgeHours > 24 ? 0.3 : 0),
    );

    // Cadence: process pressure
    const overdueReviews = reviews?.overdue_count ?? 0;
    const feedbackGap = reviews?.peer_feedback_gap_total ?? 0;
    const staleReports = statusReports?.stale ? 1 : 0;
    const cadencePressure = clamp01(overdueReviews * 0.3 + feedbackGap * 0.05 + staleReports * 0.2);

    // Chronicle: operational pressure
    const openIncidents = incidents?.open_count ?? 0;
    const missingPostmortems = incidents?.missing_postmortem_count ?? 0;
    const overdueActions = postmortems?.overdue_count ?? 0;
    const chroniclePressure = clamp01(
      openIncidents * 0.3 + missingPostmortems * 0.2 + overdueActions * 0.15,
    );

    return {
      outlook: stanceFromPressure(outlookPressure),
      assembly: stanceFromPressure(assemblyPressure),
      cadence: stanceFromPressure(cadencePressure),
      chronicle: stanceFromPressure(chroniclePressure),
      foundation: "nominal" as StimmungStance,
    };
  }, [mgmt, nudges, okrs, goals, briefingAgeHours, incidents, postmortems, reviews, statusReports]);
}
