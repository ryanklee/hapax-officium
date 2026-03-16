# officium-web

Management dashboard for the hapax-officium system. Provides agent execution, nudge management, demo viewing, incident monitoring, and management oversight.

## Quick Start

```bash
pnpm install      # install dependencies
pnpm dev          # dev server on :5173
pnpm build        # type-check + production build
pnpm lint         # ESLint
```

**Requires the cockpit API backend running at :8050.** Vite proxies `/api` requests to `http://127.0.0.1:8051` in dev mode.

## Tech Stack

- **React 19** + **TypeScript 5.9** (strict mode)
- **Vite 7** with `@vitejs/plugin-react`
- **Tailwind CSS 4** via `@tailwindcss/vite`
- **TanStack React Query** (5min refetch interval)
- **React Router 7** (BrowserRouter, 2 routes)
- **Lucide React** for icons
- **react-markdown** + remark-gfm for markdown rendering

No test runner is currently configured.

## Routes

| Path | Page | Purpose |
|------|------|---------||
| `/` | DashboardPage | Agents, nudges, incidents, sidebar panels |
| `/demos` | DemosPage | Browse and view generated demos |

## Project Structure

```
src/
  api/            API client (20 endpoints), React Query hooks, SSE helpers, TypeScript types
  components/
    dashboard/    Agent grid, nudge list, output pane, incident banner, agent config modal
    demos/        Demo list and detail views
    layout/       App layout shell, error boundary, command palette, toast provider
    shared/       Command palette, error boundary, modals, markdown, badges, loading skeletons
    sidebar/      5 sidebar panels (briefing, management, OKRs, review cycles, goals)
  pages/          DashboardPage, DemosPage
  utils.ts        Shared utilities
```

## Sidebar

5 panels with auto-priority sorting (stale 1:1s > overdue reviews > at-risk OKRs > stale briefing). Auto-expand on alerts, manual collapse/expand override. Collapses to icon strip with status dots.

## Conventions

- **pnpm only** — never npm or yarn
- TypeScript strict mode enforced
- Tailwind for all styling — no CSS modules or styled-components
- Functional components only
- API types must stay in sync with cockpit backend dataclasses
