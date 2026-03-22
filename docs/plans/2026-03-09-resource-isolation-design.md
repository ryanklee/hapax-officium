# Resource Isolation Design

## Goal

Eliminate all shared resources between the management cockpit (`hapax-containerization`) and the wider hapax system (`hapaxromana` + `ai-agents`). Each system runs its own infrastructure stack with no shared services, databases, collections, or traces.

## Current State

Both systems share: Qdrant (6333), LiteLLM (4000), Langfuse (3000), PostgreSQL (5432), and Obsidian vault (`data/`). The management cockpit's `llm-stack/docker-compose.yml` defines all services but uses identical ports, container names, and Docker network as the wider system. Both stacks cannot coexist on the same host.

## Architecture

### Infrastructure Isolation

Offset all host-exposed ports by +100. Rename containers with `mgmt-` prefix. Use a separate Docker network (`mgmt-cockpit`). Prefix Docker volumes with `mgmt_`. Internal Docker ports stay the same — services communicate via service names.

| Service | Wider System | Management Cockpit | Notes |
|---------|-------------|-------------------|-------|
| Qdrant | 6333/6334 | 6433/6434 | Own instance, same collection names |
| LiteLLM | 4000 | 4100 | Own proxy, own model routing DB |
| Langfuse | 3000 | 3100 | Own traces, own project |
| PostgreSQL | 5432 | 5532 | Own databases (litellm, langfuse) |
| Ollama | 11434 | 11434 (shared) | Single GPU constraint, auto-manages models |
| ClickHouse | 8123/9000 | 8223/9100 | Own OLAP for Langfuse |
| Redis | internal | internal | No host port needed |
| MinIO | 9090/9091 | 9190/9191 | Own object storage |
| Langfuse Worker | 3030 | 3130 | Own worker |
| ntfy | 8090 | 8190 | Own notification server |
| Logos API | 8051 | 8051 | Unchanged |

**Ollama stays shared.** Only one GPU (RTX 3090, 24GB VRAM). Ollama auto-unloads idle models. Both stacks point at the same Ollama instance. This is acceptable — Ollama is stateless inference, not a data store.

### Vault Excision

All Obsidian vault dependencies removed. The vault replacement (VS Code + Qdrant) is a separate future project.

**Files affected:**

- `shared/management_bridge.py` — `get_management_state()` returns empty/stub results. Functions that read vault paths return empty lists/dicts. Clear "data source TBD" markers.
- `shared/vault_writer.py` — Write calls become no-ops with logged warnings.
- `shared/vault_utils.py` — Kept (generic frontmatter parser, useful for future data sources).
- `shared/config.py` — Remove `WORK_VAULT_PATH` and `PERSONAL_VAULT_PATH` constants.
- `logos/data/management.py` — Calls management_bridge, gets empty results naturally. No changes needed.
- `agents/system_check.py` — Remove vault accessibility check (currently 1 of 4 checks, becomes 3).
- `agents/management_prep.py` — Vault context tools return empty results naturally via management_bridge stub.
- `agents/management_briefing.py` — Same as above.
- `docker-compose.yml` — Remove `${VAULT_PATH}:/vault` mount and `VAULT_PATH` env var from management-cockpit service.

### Services Removed from docker-compose

- **Open WebUI** — Not management-scoped. Chat UI belongs to the wider system.
- **n8n** — Not management-scoped. Workflow automation belongs to the wider system.

### Code Changes

- `shared/config.py` — Update default ports: Qdrant 6433, LiteLLM 4100, Langfuse 3100.
- `docker-compose.yml` — Port offsets, container name prefixes, volume prefixes, network rename, remove Open WebUI + n8n, remove vault mount.
- `.envrc` template — Update default ports to match new offsets.
- `generate-env.sh` — Already generates independent secrets, no changes needed.

### Qdrant Collections

Same names (`profile-facts`, `axiom-precedents`) on the separate Qdrant instance. No code changes — different server, same schema.

### Boundary Document Update

After implementation, update `docs/cross-project-boundary.md` in both repos:
- Shared Infrastructure section updated to reflect isolation
- Ollama documented as the one shared service (stateless inference)
- Isolation Trajectory section updated to reflect completion

## What This Design Does NOT Cover

- **Vault replacement** — VS Code + Qdrant data source for people/meeting data. Separate project.
- **Ollama isolation** — Would require a second GPU or CPU-only inference. Not practical.
- **Network-level isolation** — Both stacks run on the same host via localhost. No firewall rules between them.
