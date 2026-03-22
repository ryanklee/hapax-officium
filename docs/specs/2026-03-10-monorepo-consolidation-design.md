# Monorepo Consolidation Design Spec

## Goal

Consolidate ~/projects/ into two public open-source GitHub repos, scrubbed of PII, with CI/CD, proper licensing, and documentation suitable for public consumption. Make it easy for anyone to clone one repo and have a working system.

## Decision Record

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Repo count | 2 | Management cockpit and personal automation are different audiences |
| hapaxromana | Folds into hapax-core | Architecture specs belong with the parent system |
| hapax-system | Into hapax-core | Claude Code config is personal system tooling |
| hapax-vscode | Into hapax-mgmt | VS Code extension serves management cockpit users |
| cockpit-web | One per repo, renamed | Parallel implementations, may converge later |
| sample-search | Not published | Stub, not ready |
| distro-work | Not published | Scratchpad, not structured |
| obsidian-hapax | Not published | Archived, replaced by hapax-vscode |
| License (hapax-mgmt) | Apache 2.0 | Employer transfer planned; patent grant + permissive |
| License (hapax-core) | MIT | Personal project, simplest permissive license |
| Git history | Fresh initial commits | PII in history; squash is simpler than filter-repo |
| cockpit-web naming | hapax-web (core), hapax-mgmt-web (mgmt) | Consistent branding |

## Repo 1: hapax-mgmt (Apache 2.0)

Management decision support cockpit for engineering managers. Agents prepare context for 1:1s, track management practice patterns, surface stale conversations, and profile management self-awareness. React dashboard provides the operational interface.

### Structure

```
hapax-mgmt/
├── agents/                    ← from agents/ (19 management agents)
├── shared/                    ← from shared/ (25 shared modules)
├── logos/                   ← from cockpit/ (API server + reactive engine)
├── hapax-mgmt-web/            ← from hapax-mgmt-web/ (React dashboard, renamed)
├── vscode/                    ← from vscode/ (VS Code extension)
├── demo-data/                 ← synthetic seed corpus (checked in)
├── axioms/                    ← management-scoped governance
├── docs/                      ← design specs, plans
├── scripts/                   ← bootstrap, operational scripts
├── config/                    ← role-matrix, org-dossier, scenarios
├── tests/                     ← test suite
├── profiles/                  ← gitignored runtime state
├── data/                      ← gitignored DATA_DIR
├── pyproject.toml
├── uv.lock
├── LICENSE                    ← Apache 2.0
├── README.md                  ← rewritten for public audience
├── CLAUDE.md                  ← scrubbed of PII
├── CONTRIBUTING.md
├── .github/workflows/ci.yml
├── .editorconfig
└── .gitignore
```

### Key Change: Flatten ai-agents/ 

Currently agents/, shared/, cockpit/, tests/, config/ are nested under ai-agents/ . For a focused repo they become top-level. This simplifies import paths and CI.

**Import path impact:** Python imports (`from agents.X`, `from shared.X`, `from cockpit.X`) remain unchanged — only the filesystem nesting changes. What must be updated:

- `pyproject.toml`: Package discovery paths (currently under the repo root, become repo root). The existing pyproject.toml uses `[tool.setuptools.packages.find]` with `where = ["."]` — this continues to work after flattening since the package directories stay the same names.
- `scripts/bootstrap-demo.sh` and other scripts: Replace `cd ai-agents &&` prefixes with direct commands from repo root.
- `CLAUDE.md` and `docs/`: All references to `agents/` become `agents/`, etc.
- `Dockerfile`: Build context and COPY paths updated to reflect flattened layout.
- `pytest` config: `testpaths` in pyproject.toml updated (currently `tests`, becomes `tests`).

**No `sys.path` manipulation exists** in any agent entry points — all use standard `python -m agents.X` invocation.

### Removed from hapax-mgmt

- `llm-stack/` — infrastructure config with env generation. Separate setup guide.
- `claude-config/` — personal Claude Code MCP config. Not portable.
- `hapax-system/` — moves to hapax-core.

### Cutover

The current `~/projects/hapax-mgmt/` working directory is untouched during assembly. Phase 2 builds `~/projects/hapax-mgmt-publish/` as a parallel directory. After validation (tests pass, PII verification clean), `hapax-mgmt-publish/` becomes the new working copy. The old `hapax-mgmt/` moves to `~/projects/.archive/hapax-mgmt-pre-publish/`.

## Repo 2: hapax-core (MIT)

Personal LLM-first automation system. 26 agents for sync, briefings, profiling, knowledge management, health monitoring, and development archaeology. Full cockpit with chat, voice, and interview interfaces.

### Structure

```
hapax-core/
├── agents/                    ← from agents/ (26 agents)
├── shared/                    ← from shared/ (44 modules)
├── logos/                   ← from cockpit/ (full cockpit)
├── hapax-web/                 ← from hapax-mgmt-web/ (renamed)
├── system/                    ← from hapax-system/ (skills, hooks, rules)
├── specs/                     ← from hapaxromana/ (architecture, axioms)
├── tests/
├── pyproject.toml
├── uv.lock
├── LICENSE                    ← MIT
├── README.md
├── CLAUDE.md                  ← scrubbed (based on CLAUDE.md as primary, merged with relevant sections from hapaxromana and hapax-system CLAUDE.md files)
├── CONTRIBUTING.md
├── .github/workflows/ci.yml
├── .editorconfig
└── .gitignore
```

### CLAUDE.md Composition

hapax-core merges code from 4 repos. The CLAUDE.md is composed as:

- **Base:** CLAUDE.md (primary — has agent roster, testing, conventions, project layout)
- **Merge in:** hapaxromana/CLAUDE.md architecture sections (agent tiers, service topology)
- **Merge in:** hapax-system/CLAUDE.md install/usage instructions (renamed to `system/` paths)
- **Discard:** hapax-mgmt-web/CLAUDE.md (it has its own README in hapax-web/)

### pyproject.toml

Each repo gets its own pyproject.toml derived from the source:

- **hapax-mgmt:** Fork from current `pyproject.toml`. Trim dependencies not used by the 19 management agents (e.g., remove google-auth, google-api-python-client if only sync agents use them). Keep simulator, demo pipeline, cockpit dependencies.
- **hapax-core:** Fork from `~/projects/pyproject.toml`. This is the full dependency set — no trimming needed since all 26 agents are included.

Both use `[tool.setuptools.packages.find]` with `where = ["."]` and `include = ["agents*", "shared*", "cockpit*"]`.

## PII Scrubbing

All tracked files across both repos require scrubbing before publishing.

### Substitution Table

| Find | Replace With | Scope |
|------|-------------|-------|
| "the operator" | "the operator" or remove | All files |
| "Operator name" (as operator reference, not in unrelated contexts) | "operator" | Axioms, docs, tests |
| "Family Member" + spouse/wife references | Remove entirely | demo-audiences.yaml, demo-personas.yaml |
| "Jordan Rivera" + title + characterization | Replace with fictional persona (e.g., "Jordan Rivera, Staff Engineer") | demo-audiences.yaml |
| "engineering leader" (job title) | Remove or generalize to "engineering leader" | demo-audiences.yaml |
| medical info tied to operator identity | See classification rule below | ~60 files |
| `~/...` expanded paths | `~/...` or relative paths | All files |
| `~/projects/...` absolute paths | Relative paths or generic examples | CLAUDE.md, docs |
| `data/`, `data/` | Remove or generalize to "vault path" | CLAUDE.md, rules |
| "user" (username in paths) | Scrub — use `~` or relative paths only | All files |

### Medical Info Classification Rule

Files referencing medical information fall into three categories:

1. **Remove:** Demo personas, audience profiles, presenter styles where medical info is tied to operator identity. Delete the references entirely.
2. **Generalize:** Architecture docs explaining accommodation features (e.g., "cognitive load management"). Replace specific diagnoses with "neurodivergent-friendly design patterns" or "cognitive load awareness."
3. **Keep:** If a reference is purely technical and not identity-linked (e.g., a generic UX principle). Review on a case-by-case basis — default to remove if uncertain.

### demo-audiences.yaml Location

This file lives in `profiles/demo-audiences.yaml`. The `profiles/` directory contents are gitignored (`*.json`, `*.md`, `*.jsonl`, `*.yaml`). However, `demo-audiences.yaml` and `demo-personas.yaml` are **seed configuration** that gets copied during bootstrap — they may need to be moved to `config/` (tracked) or remain in `profiles/` (gitignored, not published). If gitignored, scrubbing is moot for the published repo but should still happen for the working copy.

**Decision:** Move `demo-audiences.yaml` and `demo-personas.yaml` to `config/` (tracked, scrubbed) so they are available to anyone cloning the repo. The demo system needs them to function.

### Approach

1. Automated find/replace for clear cases (full name, spouse, colleague, username, paths).
2. Manual review for medical references using the classification rule above.
3. `demo-audiences.yaml` and `demo-personas.yaml` moved to `config/`, scrubbed, and tracked.
4. Fresh initial commits eliminate history scrubbing risk entirely.

### PII Verification Pass

After scrubbing and before the initial commit, run a grep-based verification:

```bash
# Must return zero results for each:
rg -i "operator-name" .
rg -i "operator-name" .
rg "\bFamily Member\b" .
rg -i "jordan rivera" .
rg "\bAVP\b" .
rg "~" .
rg "~/Documents/(Work|Personal)" .
# Review manually (may have legitimate uses):
rg -i "\b(medical-info)\b" .
```

This verification runs as the final step of Phase 2 and Phase 3, before the initial commit.

## CI/CD Pipeline

Minimal, effective, same pattern for both repos.

### Python CI

```yaml
on: [push, pull_request]
jobs:
  lint:
    - ruff check + ruff format --check
  typecheck:
    - pyright on agents/ shared/ cockpit/
  test:
    - uv run pytest tests/ -q
    # All tests mocked, no external services needed
```

### Web CI

```yaml
  web-lint:
    - pnpm lint (eslint)
  web-build:
    - pnpm build
```

### VS Code Extension CI (hapax-mgmt only)

```yaml
  vscode-build:
    - pnpm install && pnpm compile
```

### Not Adding Yet

- Docker image builds (needs registry)
- Integration tests against live services
- Deployment automation
- Code coverage gates

## Documentation

### README.md (rewritten per repo)

Structure for both:
- What it is (2-3 sentences)
- Architecture diagram
- Quick start (clone, install, run tests, run demo)
- Project structure
- Key concepts
- License

### CLAUDE.md

Stays in both repos (useful for Claude Code contributors). Scrubbed of PII and operator-specific paths. See "CLAUDE.md Composition" under hapax-core for merge strategy.

### CONTRIBUTING.md

Lightweight:
- How to run tests
- Commit conventions (conventional commits)
- Branch workflow (feature branches from main)
- Code style (ruff, type hints, pydantic models)

### Not Adding

- CHANGELOG (use GitHub releases)
- Detailed API docs (code + CLAUDE.md suffice)

## Execution Strategy

### Phase 1: Prep (safe, no disruption)

Create all new files in isolation:
- PII scrubbing mappings (exact find/replace per file)
- LICENSE, CONTRIBUTING.md, .editorconfig, ruff config, pyright config
- CI workflow files
- New README.md for each repo

No source repo modifications. All prep work is additive.

### Phase 2: Assemble hapax-mgmt

- Create `~/projects/hapax-mgmt-publish/` as fresh git repo
- Copy and restructure: flatten ai-agents/  up, rename cockpit-web → hapax-mgmt-web, add hapax-vscode → vscode/
- Move demo-audiences.yaml, demo-personas.yaml from profiles/ to config/
- Apply PII scrubbing (automated + manual)
- Update all import paths, script paths, and documentation references
- Update pyproject.toml package discovery and pytest config for flattened layout
- Run full test suite to verify nothing broke
- Run PII verification pass
- Single initial commit

### Phase 3: Assemble hapax-core

- Ensure all source repos (ai-agents, cockpit-web, hapaxromana, hapax-system) have clean working trees. If uncommitted changes exist, commit or stash them first.
- Create `~/projects/hapax-core/` as fresh git repo
- Copy from ai-agents (agents, shared, cockpit, tests, pyproject.toml), cockpit-web → hapax-web, hapaxromana → specs/, hapax-system → system/
- If dev-story branch has landed on ai-agents main, it's included automatically. If still on feature branch, merge to main first or cherry-pick.
- Apply PII scrubbing
- Compose CLAUDE.md from ai-agents + hapaxromana + hapax-system sources
- Update all references (hapaxromana → specs/, hapax-system → system/, cockpit-web → hapax-web)
- Run full test suite
- Run PII verification pass
- Single initial commit

### Phase 4: GitHub automation

- `gh repo create` for both (public, description, license)
- Push initial commits
- Enable branch protection on main

### Cutover and Archival

After both repos are on GitHub and validated:

1. `~/projects/hapax-mgmt/` → `~/projects/.archive/hapax-mgmt-pre-publish/`
2. `~/projects/hapax-mgmt-publish/` → `~/projects/hapax-mgmt/` (becomes working copy)
3. Source repos archived one at a time: ai-agents → .archive/, cockpit-web → .archive/, hapaxromana → .archive/, hapax-system → .archive/, hapax-vscode → .archive/
4. Update hapax-system install.sh symlinks to point at new `hapax-core/system/` path
5. Update any systemd timers or scripts referencing old paths

### Port Conflicts

Both repos use the same port numbers (8050 API, 8052 web). Since the operator runs only one system at a time, this is not a problem during normal use. During the migration transition period, avoid running both simultaneously. Document the port assignments in each repo's README.

## Reference Renaming Checklist

All references to these names must be updated in code, docs, configs, and imports:

| Old Name | New Name | Context |
|----------|----------|---------|
| cockpit-web (in hapax-mgmt) | hapax-mgmt-web | Directory, docs, Docker, nginx config |
| cockpit-web (in hapax-core) | hapax-web | Directory, docs, Docker |
| logos API / hapax-agents | hapax-mgmt-api (mgmt), hapax-api (core) | Docker service name, docs, port references |
| ai-agents/ (subdirectory) | top-level agents/, shared/, etc. | pyproject.toml, scripts, CLAUDE.md, Dockerfile |
| hapaxromana (in hapax-core) | specs/ | CLAUDE.md, cross-references, axiom docs |
| hapax-system (in hapax-core) | system/ | CLAUDE.md, install.sh, hook paths |
| hapax-vscode (in hapax-mgmt) | vscode/ | CLAUDE.md, docs |
| Python package paths in pyproject.toml | Update find/include patterns | Both repos |
| pytest testpaths | Update from tests to tests | pyproject.toml |
| bootstrap-demo.sh cd commands | Remove ai-agents/ prefix | scripts/ |
