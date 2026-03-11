import { useIncidents } from "../../api/hooks";
import { AlertTriangle } from "lucide-react";

const severityColor: Record<string, string> = {
  sev1: "bg-red-500/20 border-red-500 text-red-300",
  sev2: "bg-orange-500/20 border-orange-500 text-orange-300",
  sev3: "bg-yellow-500/20 border-yellow-500 text-yellow-300",
};

export function IncidentBanner() {
  const { data: snap } = useIncidents();

  if (!snap || snap.open_count === 0) return null;

  const openIncidents = snap.incidents.filter((i) => i.open);

  return (
    <div className="space-y-2">
      {openIncidents.map((inc) => (
        <div
          key={inc.title}
          className={`flex items-center gap-2 rounded border-l-2 p-2 text-xs ${severityColor[inc.severity] ?? severityColor.sev3}`}
        >
          <AlertTriangle className="h-3.5 w-3.5 shrink-0" />
          <div className="flex-1">
            <span className="font-medium">{inc.severity.toUpperCase()}</span>
            <span className="mx-1">—</span>
            <span>{inc.title}</span>
            {!inc.has_postmortem && (
              <span className="ml-2 rounded bg-red-500/30 px-1 text-red-300">needs postmortem</span>
            )}
          </div>
        </div>
      ))}
    </div>
  );
}
