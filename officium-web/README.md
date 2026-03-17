# officium-web — Management Dashboard

React single-page application providing operational visibility into the hapax-officium management decision support system. Agent execution, nudge management, briefings, goals, and demo browsing — backed by the cockpit API via Server-Sent Events and React Query.

This is a Tier 1 interface: interactive, human-facing, read-heavy. It consumes the cockpit API (:8050) but never writes to the filesystem-as-bus directly. All mutations go through API endpoints that the reactive engine processes.

## Quick Start

```bash
pnpm install      # install dependencies
pnpm dev          # dev server on :5173
pnpm build        # type-check + production build
pnpm lint         # ESLint
```

Requires the cockpit API at :8050:
```bash
cd ~/projects/hapax-officium
uv run python -m cockpit.api --host 127.0.0.1 --port 8050
```

## Architecture

**Server state** is managed exclusively through TanStack React Query. Every backend call goes through `src/api/client.ts`, which hits `/api/*` (Vite proxies to :8050 in dev, nginx proxies in production). Types in `src/api/types.ts` mirror the Python dataclasses in `cockpit/data/`.

**Agent execution** uses Server-Sent Events (`src/api/sse.ts` + `src/hooks/useSSE.ts`). Agent runs stream output, done, and error events in real time. AbortController-based cancellation with DELETE to `/api/agents/runs/current`.

**Sidebar panels** show management-relevant context: briefing, goals, OKRs, management snapshots (people, coaching, feedback), review cycles, and status reports.

## Routes

| Path | Page | Purpose |
|------|------|---------|
| `/` | DashboardPage | Agent grid, nudge list, incidents, streaming output, sidebar panels |
| `/demos` | DemosPage | Browse and view generated capability demos |

## Stack

React 19, TypeScript 5.9 (strict), Vite 7, Tailwind CSS 4 (Gruvbox Dark theme), TanStack React Query, React Router 7, Recharts, Lucide React, react-markdown + remark-gfm, JetBrains Mono.

## Project Structure

```
src/
  api/              Client, React Query hooks, SSE streaming, TypeScript types
  components/
    dashboard/      Agent grid, nudge list, output pane, incident banner
    demos/          Demo list and detail views
    layout/         App shell, header, error boundary, toast provider, command palette
    sidebar/        Briefing, goals, OKRs, management, review cycle panels
  hooks/            useSSE (agent output streaming)
  pages/            DashboardPage, DemosPage
```

## Deployment

Production builds are served via nginx with SPA routing fallback. API requests proxy to `management-cockpit:8050`. Static assets cached with 1-year expiry.

## Related

- [hapax-officium](https://github.com/ryanklee/hapax-officium) — Backend cockpit API + agents
- [hapax-constitution](https://github.com/ryanklee/hapax-constitution) — Governance architecture
- [council-web](../council-web/) (in hapax-council) — Equivalent dashboard for the personal operating environment
