import { useState, useMemo, useCallback, useEffect, type ComponentType } from "react";
import { ChevronLeft, ChevronRight } from "lucide-react";
import { useBriefing, useManagement, useNudges, useOKRs, useReviewCycles, useIncidents } from "../api/hooks";
import { BriefingPanel } from "./sidebar/BriefingPanel";
import { GoalsPanel } from "./sidebar/GoalsPanel";
import { ManagementPanel } from "./sidebar/ManagementPanel";
import { OKRPanel } from "./sidebar/OKRPanel";
import { ReviewCyclePanel } from "./sidebar/ReviewCyclePanel";
import { SidebarStrip } from "./sidebar/SidebarStrip";

interface PanelEntry {
  id: string;
  component: ComponentType;
  defaultOrder: number;
}

const panels: PanelEntry[] = [
  { id: "team", component: ManagementPanel, defaultOrder: 0 },
  { id: "okrs", component: OKRPanel, defaultOrder: 1 },
  { id: "reviews", component: ReviewCyclePanel, defaultOrder: 2 },
  { id: "briefing", component: BriefingPanel, defaultOrder: 3 },
  { id: "goals", component: GoalsPanel, defaultOrder: 4 },
];

export function Sidebar() {
  const [manualOverride, setManualOverride] = useState<"expanded" | "collapsed" | null>(null);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(interval);
  }, []);

  const { data: briefing } = useBriefing();
  const { data: mgmt } = useManagement();
  const { data: nudges } = useNudges();
  const { data: okrs } = useOKRs();
  const { data: reviews } = useReviewCycles();
  const { data: incidents } = useIncidents();

  // Alert triggers — management signals only
  const needsAttention = useMemo(() => {
    if (mgmt?.people.some((p) => p.stale_1on1)) return true;
    if (nudges?.some((n) => n.priority_label === "critical" || n.priority_label === "high")) return true;
    if (okrs && okrs.at_risk_count > 0) return true;
    if (reviews && reviews.overdue_count > 0) return true;
    if (incidents && incidents.open_count > 0) return true;
    if (briefing?.generated_at) {
      const hours = (now - new Date(briefing.generated_at).getTime()) / 3_600_000;
      if (hours > 24) return true;
    }
    return false;
  }, [briefing, mgmt, nudges, okrs, reviews, incidents, now]);

  const isExpanded = manualOverride === "expanded" || (manualOverride === null && needsAttention);

  // Status dots for strip mode
  const statusDots = useMemo(() => {
    const dots: Record<string, "green" | "yellow" | "red" | "zinc"> = {};
    dots.team = mgmt?.people.some((p) => p.stale_1on1) ? "yellow" : mgmt ? "green" : "zinc";
    dots.okrs = okrs?.at_risk_count ? "yellow" : okrs ? "green" : "zinc";
    dots.reviews = reviews?.overdue_count ? "red" : reviews ? "green" : "zinc";
    dots.briefing = (() => {
      if (!briefing?.generated_at) return "zinc" as const;
      const h = (now - new Date(briefing.generated_at).getTime()) / 3_600_000;
      return h > 24 ? "yellow" as const : "green" as const;
    })();
    return dots;
  }, [briefing, mgmt, now, okrs, reviews]);

  const summaries = useMemo(() => {
    const s: Record<string, string> = {};
    if (mgmt) {
      const stale = mgmt.people.filter((p) => p.stale_1on1).length;
      s.team = stale > 0 ? `${stale} stale 1:1s` : `${mgmt.people.length} reports`;
    }
    return s;
  }, [mgmt]);

  // Priority sorting
  const sorted = useMemo(() => {
    function priority(id: string): number {
      switch (id) {
        case "team": {
          const stale = mgmt?.people.filter((p) => p.stale_1on1).length ?? 0;
          return stale > 0 ? 25 : 0;
        }
        case "okrs":
          return (okrs?.at_risk_count ?? 0) > 0 ? 20 : 0;
        case "reviews":
          return (reviews?.overdue_count ?? 0) > 0 ? 22 : 0;
        case "briefing": {
          if (!briefing?.generated_at) return 0;
          const hours = (now - new Date(briefing.generated_at).getTime()) / 3_600_000;
          return hours > 24 ? 30 : 0;
        }
        default:
          return 0;
      }
    }

    return [...panels].sort((a, b) => {
      const pa = priority(a.id);
      const pb = priority(b.id);
      if (pa !== pb) return pb - pa;
      return a.defaultOrder - b.defaultOrder;
    });
  }, [briefing, mgmt, now, okrs, reviews]);

  const handleStripClick = useCallback(() => {
    setManualOverride("expanded");
  }, []);

  const toggleSidebar = useCallback(() => {
    if (isExpanded) {
      setManualOverride("collapsed");
    } else {
      setManualOverride("expanded");
    }
  }, [isExpanded]);

  return (
    <aside className={`relative shrink-0 border-l border-zinc-700 bg-zinc-900/50 text-xs transition-[width] duration-200 ease-in-out ${isExpanded ? "w-72" : "w-12"}`}>
      {isExpanded ? (
        <div className="h-full divide-y divide-zinc-800 overflow-y-auto">
          <div className="flex justify-end p-2">
            <button
              onClick={toggleSidebar}
              className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
              title="Collapse sidebar"
            >
              <ChevronRight className="h-3.5 w-3.5" />
            </button>
          </div>
          {sorted.map((panel) => (
            <div key={panel.id} className="p-4" id={`sidebar-${panel.id}`}>
              <panel.component />
            </div>
          ))}
        </div>
      ) : (
        <div className="h-full overflow-y-auto">
          <div className="flex justify-center py-2">
            <button
              onClick={toggleSidebar}
              className="rounded p-1 text-zinc-500 hover:bg-zinc-800 hover:text-zinc-300"
              title="Expand sidebar"
            >
              <ChevronLeft className="h-3.5 w-3.5" />
            </button>
          </div>
          <SidebarStrip
            statusDots={statusDots}
            summaries={summaries}
            onPanelClick={handleStripClick}
          />
        </div>
      )}
    </aside>
  );
}
