import { useState, useMemo, useEffect } from "react";
import { useBriefing } from "../../api/hooks";
import { SidebarSection } from "./SidebarSection";
import { DetailModal } from "../shared/DetailModal";
import { MarkdownContent } from "../shared/MarkdownContent";
import { formatAge } from "../../utils";

export function BriefingPanel() {
  const { data: briefing, dataUpdatedAt, isError } = useBriefing();
  const [detailOpen, setDetailOpen] = useState(false);
  const [now, setNow] = useState(() => Date.now());

  useEffect(() => {
    const interval = setInterval(() => setNow(Date.now()), 60_000);
    return () => clearInterval(interval);
  }, []);

  const ageH = useMemo(() => {
    if (!briefing?.generated_at) return "?";
    try {
      const gen = new Date(briefing.generated_at);
      return ((now - gen.getTime()) / 3600000).toFixed(0);
    } catch {
      return "?";
    }
  }, [briefing, now]);

  if (isError) {
    return (
      <SidebarSection title="Briefing">
        <p className="text-red-400">Failed to load briefing</p>
      </SidebarSection>
    );
  }

  if (!briefing) {
    return (
      <SidebarSection title="Briefing">
        <p className="text-zinc-500">No briefing yet</p>
      </SidebarSection>
    );
  }

  return (
    <>
      <SidebarSection title="Briefing" clickable onClick={() => setDetailOpen(true)} age={formatAge(dataUpdatedAt)}>
        <p className="text-sm text-zinc-300 line-clamp-2">{briefing.headline}</p>
        <p className="text-zinc-500">{ageH}h ago · {briefing.action_items.length} action items</p>
      </SidebarSection>

      <DetailModal title="Daily Briefing" open={detailOpen} onClose={() => setDetailOpen(false)}>
        <div className="space-y-3 text-xs">
          <p className="text-zinc-500">{briefing.generated_at}</p>
          <MarkdownContent content={briefing.body} className="text-sm" />
          {briefing.action_items.length > 0 && (
            <div>
              <h3 className="mb-1 font-medium text-zinc-300">Action Items</h3>
              <ul className="space-y-1">
                {briefing.action_items.map((a, i) => (
                  <li key={i} className="text-zinc-400">
                    <span className="font-medium text-zinc-300">[{a.priority}]</span> {a.action}
                    {a.command && <code className="ml-1 text-zinc-500">{a.command}</code>}
                  </li>
                ))}
              </ul>
            </div>
          )}
        </div>
      </DetailModal>
    </>
  );
}
