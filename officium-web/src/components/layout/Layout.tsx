import { useState, useEffect } from "react";
import { Outlet } from "react-router-dom";
import { Header } from "../Header";
import { CommandPalette } from "../shared/CommandPalette";
import { ErrorBoundary } from "../shared/ErrorBoundary";
import { ToastProvider } from "../shared/ToastProvider";
import { useKeyboardShortcuts } from "../../hooks/useKeyboardShortcuts";

export function Layout() {
  const [paletteOpen, setPaletteOpen] = useState(false);

  useKeyboardShortcuts();

  // Ctrl+P for command palette
  useEffect(() => {
    function handleKeyDown(e: KeyboardEvent) {
      if ((e.ctrlKey || e.metaKey) && e.key === "p") {
        e.preventDefault();
        setPaletteOpen((prev) => !prev);
      }
    }
    document.addEventListener("keydown", handleKeyDown);
    return () => document.removeEventListener("keydown", handleKeyDown);
  }, []);

  return (
    <ToastProvider>
      <div className="flex h-screen flex-col bg-zinc-950 text-zinc-100">
        <Header />
        <ErrorBoundary>
          <div className="flex flex-1 overflow-hidden">
            <Outlet />
          </div>
        </ErrorBoundary>
        <CommandPalette
          open={paletteOpen}
          onClose={() => setPaletteOpen(false)}
        />
      </div>
    </ToastProvider>
  );
}
