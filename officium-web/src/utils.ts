/** Format React Query's dataUpdatedAt timestamp as a relative age string. */
export function formatAge(dataUpdatedAt: number): string {
  if (!dataUpdatedAt) return "";
  const seconds = Math.floor((Date.now() - dataUpdatedAt) / 1000);
  if (seconds < 10) return "now";
  if (seconds < 60) return `${seconds}s ago`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  return `${hours}h ago`;
}
