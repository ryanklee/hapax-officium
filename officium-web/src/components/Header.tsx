import { Activity } from "lucide-react";
import { NavLink } from "react-router-dom";

export function Header() {
  const navLinkClass = ({ isActive }: { isActive: boolean }) =>
    `px-3 py-1 rounded text-xs font-medium transition-colors ${
      isActive
        ? "bg-zinc-700 text-zinc-100"
        : "text-zinc-400 hover:text-zinc-200 hover:bg-zinc-800"
    }`;

  return (
    <header className="flex items-center justify-between border-b border-zinc-700 bg-zinc-900 px-4 py-2">
      <div className="flex items-center gap-4">
        <div className="flex items-center gap-2">
          <Activity className="h-5 w-5 text-zinc-400" />
          <span className="text-sm font-medium text-zinc-200">cockpit</span>
        </div>
        <nav className="flex items-center gap-1" aria-label="Main navigation">
          <NavLink to="/" end className={navLinkClass}>
            Dashboard
          </NavLink>
        </nav>
      </div>
      <div className="flex items-center gap-3 text-xs">
        <div className="hidden items-center gap-2 text-[10px] text-zinc-600 sm:flex">
          <span><kbd className="rounded border border-zinc-700 px-1 py-0.5">⌘P</kbd> commands</span>
        </div>
      </div>
    </header>
  );
}
