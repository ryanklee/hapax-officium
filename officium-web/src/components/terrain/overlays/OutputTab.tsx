import { useEffect, useRef, useState } from "react";
import { useAgentRun } from "../../../hooks/useAgentRun";

function lineColor(line: string): string {
  if (line.startsWith("---")) return "text-zinc-500 font-medium";
  if (/ERROR|FAILED|✗/.test(line)) return "text-red-400";
  if (/WARNING|WARN|⚠/.test(line)) return "text-yellow-400";
  if (/✓|PASS|\bOK\b/.test(line)) return "text-green-600";
  return "";
}

function ElapsedTimer({ startedAt }: { startedAt: number }) {
  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const id = setInterval(() => {
      setElapsed(Math.floor((Date.now() - startedAt) / 1000));
    }, 1000);
    return () => clearInterval(id);
  }, [startedAt]);
  return <span className="text-blue-400">running {elapsed}s</span>;
}

export function OutputTab() {
  const { lines, isRunning, error, agentName, startedAt, cancelAgent, clearOutput } =
    useAgentRun();
  const scrollRef = useRef<HTMLDivElement>(null);

  // Auto-scroll to bottom
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [lines.length]);

  if (lines.length === 0 && !isRunning && !error) {
    return (
      <div className="flex items-center justify-center h-full text-zinc-600 text-[12px]">
        Run an agent from the Foundation region to see output here.
      </div>
    );
  }

  return (
    <div className="flex flex-col h-full">
      {/* Header */}
      <div className="flex items-center gap-3 px-3 py-2 text-[11px] text-zinc-400 shrink-0 border-b border-zinc-800">
        {agentName && <span className="text-zinc-300 font-medium">{agentName}</span>}
        {isRunning && startedAt && (
          <>
            <ElapsedTimer startedAt={startedAt} />
            <button
              onClick={cancelAgent}
              className="text-red-400 hover:text-red-300 text-[10px] uppercase tracking-wider"
            >
              Cancel
            </button>
          </>
        )}
        {!isRunning && lines.length > 0 && (
          <button
            onClick={clearOutput}
            className="text-zinc-600 hover:text-zinc-400 text-[10px] uppercase tracking-wider ml-auto"
          >
            Clear
          </button>
        )}
      </div>

      {/* Output */}
      <div ref={scrollRef} className="flex-1 overflow-y-auto px-3 py-2 font-mono text-[11px]">
        {error && (
          <div className="text-red-400 mb-2 p-2 rounded bg-red-400/5">{error}</div>
        )}
        {lines.map((line, i) => (
          <div key={i} className={`whitespace-pre-wrap ${lineColor(line)}`}>
            {line}
          </div>
        ))}
      </div>
    </div>
  );
}
