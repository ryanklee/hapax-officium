import { useReviewCycles } from "../../api/hooks";
import { SidebarSection } from "./SidebarSection";
import { formatAge } from "../../utils";

export function ReviewCyclePanel() {
  const { data: cycles, dataUpdatedAt, isError } = useReviewCycles();

  if (isError) {
    return (
      <SidebarSection title="Reviews">
        <p className="text-red-400">Failed to load review data</p>
      </SidebarSection>
    );
  }

  if (!cycles || cycles.cycles.length === 0) return null;

  const active = cycles.cycles.filter((c) => !c.delivered);

  return (
    <SidebarSection title="Reviews" age={cycles ? formatAge(dataUpdatedAt) : undefined}>
      <p>
        {cycles.active_count} active
        {cycles.overdue_count > 0 && (
          <span className="text-red-400"> · {cycles.overdue_count} overdue</span>
        )}
        {cycles.peer_feedback_gap_total > 0 && (
          <span className="text-yellow-400"> · {cycles.peer_feedback_gap_total} feedback gap</span>
        )}
      </p>
      <ul className="mt-1 space-y-1 text-zinc-500">
        {active.map((c) => (
          <li key={`${c.cycle}-${c.person}`}>
            <span className="text-zinc-300">{c.person}</span> — {c.status}
            {c.overdue && (
              <span className="ml-1 rounded bg-red-500/20 px-1 text-red-400">overdue</span>
            )}
            {c.peer_feedback_gap > 0 && (
              <span className="ml-1 text-yellow-400">
                {c.peer_feedback_received}/{c.peer_feedback_requested} feedback
              </span>
            )}
          </li>
        ))}
      </ul>
    </SidebarSection>
  );
}
