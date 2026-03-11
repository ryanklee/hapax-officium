import { useOKRs } from "../../api/hooks";
import { SidebarSection } from "./SidebarSection";
import { formatAge } from "../../utils";

export function OKRPanel() {
  const { data: okrs, dataUpdatedAt, isError } = useOKRs();

  if (isError) {
    return (
      <SidebarSection title="OKRs">
        <p className="text-red-400">Failed to load OKR data</p>
      </SidebarSection>
    );
  }

  if (!okrs || okrs.okrs.length === 0) return null;

  const active = okrs.okrs.filter((o) => o.status === "active");

  return (
    <SidebarSection title="OKRs" age={okrs ? formatAge(dataUpdatedAt) : undefined}>
      <p>
        {okrs.active_count} active
        {okrs.at_risk_count > 0 && (
          <span className="text-orange-400"> · {okrs.at_risk_count} at-risk KR{okrs.at_risk_count !== 1 ? "s" : ""}</span>
        )}
        {okrs.stale_kr_count > 0 && (
          <span className="text-yellow-400"> · {okrs.stale_kr_count} stale</span>
        )}
      </p>
      <ul className="mt-1 space-y-1 text-zinc-500">
        {active.map((o) => (
          <li key={o.objective}>
            <span className="text-zinc-300">{o.quarter}</span> {o.objective}
            {o.at_risk_count > 0 && (
              <span className="ml-1 rounded bg-orange-500/20 px-1 text-orange-400">
                {o.at_risk_count} at risk
              </span>
            )}
          </li>
        ))}
      </ul>
    </SidebarSection>
  );
}
