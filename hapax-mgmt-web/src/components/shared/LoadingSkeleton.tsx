import { useMemo } from "react";

interface LoadingSkeletonProps {
  lines?: number;
  className?: string;
}

// Deterministic widths to avoid Math.random() during render
const WIDTHS = [85, 72, 93, 78, 88, 70, 95, 82, 76, 91];

export function LoadingSkeleton({ lines = 3, className = "" }: LoadingSkeletonProps) {
  const widths = useMemo(
    () => Array.from({ length: lines }, (_, i) => WIDTHS[i % WIDTHS.length]),
    [lines],
  );

  return (
    <div className={`animate-pulse space-y-2 ${className}`}>
      {widths.map((w, i) => (
        <div
          key={i}
          className="h-3 rounded bg-zinc-800"
          style={{ width: `${w}%` }}
        />
      ))}
    </div>
  );
}
