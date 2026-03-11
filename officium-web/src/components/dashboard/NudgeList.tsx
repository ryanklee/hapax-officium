import { useState } from "react";
import { useNudges, useNudgeAction } from "../../api/hooks";
import type { Nudge } from "../../api/types";
import { useToast } from "../shared/ToastProvider";
import { Check, X, Play, Loader2 } from "lucide-react";

const priorityColor: Record<string, string> = {
  critical: "border-red-500 bg-red-500/10",
  high: "border-orange-500 bg-orange-500/10",
  medium: "border-yellow-500 bg-yellow-500/10",
  low: "border-zinc-600 bg-zinc-800",
};

const categoryBadge: Record<string, string> = {
  people: "bg-blue-500/20 text-blue-400",
  goals: "bg-amber-500/20 text-amber-400",
  operational: "bg-red-500/20 text-red-400",
};

export function NudgeList() {
  const { data: nudges, isLoading, isError } = useNudges();
  const nudgeAction = useNudgeAction();
  const { addToast } = useToast();
  const [pendingId, setPendingId] = useState<string | null>(null);

  function handleAction(nudge: Nudge, action: "act" | "dismiss") {
    setPendingId(nudge.source_id);
    nudgeAction.mutate(
      { sourceId: nudge.source_id, action },
      {
        onError: () => addToast(`Failed to ${action} nudge`, "error"),
        onSettled: () => setPendingId(null),
      },
    );
  }

  const items = nudges ?? [];

  if (isLoading) {
    return (
      <section>
        <h2 className="mb-2 text-sm font-medium tracking-wide uppercase text-zinc-300">
          Action Items
        </h2>
        <p className="text-xs text-zinc-500">Loading...</p>
      </section>
    );
  }

  if (isError) {
    return (
      <section>
        <h2 className="mb-2 text-sm font-medium tracking-wide uppercase text-zinc-300">
          Action Items
        </h2>
        <p className="text-xs text-red-400">Failed to load nudges</p>
      </section>
    );
  }

  return (
    <section>
      <h2 className="mb-2 text-sm font-medium tracking-wide uppercase text-zinc-300">
        Action Items ({items.length})
      </h2>
      {items.length === 0 ? (
        <p className="text-xs text-zinc-500">No action items right now.</p>
      ) : (
        <ul className="space-y-2">
          {items.map((n) => (
            <li
              key={n.source_id}
              className={`rounded border-l-2 p-2 text-xs transition-shadow duration-150 hover:shadow-sm hover:shadow-black/20 ${priorityColor[n.priority_label] ?? priorityColor.low}`}
            >
              <div className="flex items-start justify-between gap-2">
                <div className="flex-1">
                  <div className="flex items-center gap-2">
                    <span className="font-medium text-zinc-200">{n.title}</span>
                    <span className={`shrink-0 rounded px-1 py-0.5 text-[10px] uppercase tracking-wider ${categoryBadge[n.category] ?? "bg-zinc-700 text-zinc-400"}`}>
                      {n.category}
                    </span>
                  </div>
                  {n.detail && <p className="mt-1 text-zinc-400">{n.detail}</p>}
                  {n.suggested_action && (
                    <p className="mt-1 text-zinc-300">
                      <span className="text-zinc-500">Action:</span> {n.suggested_action}
                    </p>
                  )}
                  {n.command_hint && (
                    <code className="mt-1 block text-zinc-500">{n.command_hint}</code>
                  )}
                </div>
                {n.source_id !== "meta:overflow" && (
                  <div className="flex shrink-0 gap-1">
                    {pendingId === n.source_id ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin text-zinc-400" />
                    ) : (
                      <>
                        <button
                          onClick={() => handleAction(n, "act")}
                          className="flex items-center gap-1 rounded px-1.5 py-1 text-green-400 hover:bg-green-500/20 active:scale-[0.97] focus-visible:ring-1 focus-visible:ring-zinc-500 focus-visible:outline-none"
                          title={n.command_hint ? "Run command" : "Mark done"}
                        >
                          {n.command_hint ? (
                            <Play className="h-3.5 w-3.5" />
                          ) : (
                            <Check className="h-3.5 w-3.5" />
                          )}
                        </button>
                        <button
                          onClick={() => handleAction(n, "dismiss")}
                          className="rounded p-1 text-zinc-500 hover:bg-zinc-700"
                          title="Dismiss"
                        >
                          <X className="h-3.5 w-3.5" />
                        </button>
                      </>
                    )}
                  </div>
                )}
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
