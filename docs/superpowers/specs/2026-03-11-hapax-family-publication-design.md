# Hapax Family Publication Design

## Goal

Publish the complete Hapax system as three coordinated repos: architectural pattern documentation, the full operational system, and the management domain instantiation — with a coherent naming hierarchy and uniform privacy controls.

## Naming

| Published Name | Source | Identity |
|---|---|---|
| **hapax-core** | hapaxromana | The constitution: architectural pattern specs, axiom governance framework |
| **hapax-council** | ai-agents + hapax-system + cockpit-web + hapax-vscode | The deliberative body: full operational agent platform |
| **hapax-officium** | hapax-mgmt (rename) | The duty: management decision support instantiation |

Naming rationale: *core* is the foundational pattern that governs; *council* is the deliberative body of agents that operates under it; *officium* (Latin: duty, service, obligation) is the management-specific instantiation. Hapax-officium was previously published as hapax-mgmt.

## Key Decisions

### No shared library

The ~4,200 LOC of shared code between hapax-council and hapax-officium is residue of common origin, not a library. What's actually common is an **architectural pattern** (axiom-governed reactive agent platform with filesystem-as-bus), not code. Each system owns its full stack. Reasons:

- **Specialization freedom**: hapax-officium evolves toward management domain needs without coordination costs
- **Employer safety**: No bidirectional code flow. Fork with clear provenance is legally clean.
- **Practical**: Packaging overhead exceeds the shared code volume

### ADHD/autism framing is intentionally public

The executive function accommodation architecture is the system's thesis statement, not private medical data. The diagnosis is an interesting and valuable genealogical fact about why the system exists. Neurodivergent design rationale, communication preferences, and domain corpus documents are all publishable. Only **intimate behavioral details** (substance use patterns, hygiene markers, psychological state descriptions) are private.

### Full operational system is publishable

Applying the four privacy criteria (PII, employer IP, operational security, personal safety) uniformly across all content reveals that nearly all **code logic** passes. Failures are concentrated in **string content** (~10 scrubable replacements) and one **data file** (operator.json intimate fields). No structural failures remain once the ADHD/autism framing is intentionally public.

### Git history preservation

Source repos' git histories are archived as bundles before cutover. Dev_story agent indexes bundles as additional history sources for commit correlation with Claude Code conversations. Published repos get fresh squashed commits (PII-free history).

---

## hapax-core

**Source:** ~/projects/hapaxromana/

**Purpose:** Architectural pattern documentation. The "reference architecture" for axiom-governed reactive agent platforms, with two existence proofs (hapax-council, hapax-officium).

### Contents

- `axioms/registry.yaml` — Axiom definitions (single_operator, decision_support, management_safety, executive_function, corporate_boundary)
- `axioms/implications/` — Derived T0/T1/T2 blocking implications per axiom
- `agent-architecture.md` — Three-tier system design (Tier 1: interactive, Tier 2: on-demand agents, Tier 3: autonomous timers)
- `pattern-guide.md` — **New.** Generalized pattern document covering:
  - Filesystem-as-bus (markdown + YAML frontmatter as state)
  - Agent architecture (Pydantic AI agents reading/writing the bus)
  - Axiom governance (constitutional constraints on LLM agents)
  - Reactive engine (inotify watcher -> rule evaluation -> phased execution)
  - Annotated code examples drawn from hapax-council
- `README.md` — **New.** Frames repo as architectural pattern with links to council and officium
- `LICENSE` — Apache 2.0
- Existing design docs and specs in `docs/`

### Scrubbing

- Operator name in axiom text -> "the operator"
- Employer references in corporate_boundary axiom -> generalized
- Team member names in design docs -> removed/generalized
- Home directory absolute paths -> relative

### No CI

Documentation repo. No runnable code, no tests. Just markdown and YAML.

---

## hapax-council

**Sources:** ~/projects/ai-agents/ + ~/projects/hapax-system/ + ~/projects/cockpit-web/ + ~/projects/hapax-vscode/

**Purpose:** Full operational agent platform. Externalized executive function infrastructure. Reactive cockpit, voice daemon, sync pipeline, Claude Code integration.

### Agent Manifest

Agent and module counts are derived from the source repos at execution time via `ls` / `find`. The counts stated here (26 agents, 42 shared modules) are from the exploration audit and should be verified during Track 2 consolidation. The authoritative source is the contents of `ai-agents/agents/` and `ai-agents/shared/` at time of copy.

**Agent categories:**
- Management (Tier 2): briefing, profiler, activity_analyzer
- Sync/RAG (Tier 3): gdrive_sync, gcalendar_sync, gmail_sync, youtube_sync, chrome_sync, claude_code_sync, obsidian_sync
- Analysis (Tier 2): research, code_review, drift_detector, scout
- System (Tier 2/3): health_monitor, introspect, knowledge_maint
- Content (Tier 2): digest, ingest
- Demo: demo, demo_eval
- Special: query, hapax_voice (daemon), audio_processor

**Agent packages (multi-module subsystems):**
- `hapax_voice/` (~39 modules) — Voice daemon: wake word, presence, Gemini Live, speaker ID, ambient classification, desktop awareness
- `demo_pipeline/` (~22 modules) — Demo generation: audio, video, slides, screencasts, critique, narrative
- `dev_story/` (~11 modules) — Development narrative: git extraction, phase detection, critical moments, commit-conversation correlation
- `system_ops/`, `knowledge/` — Query agents for operational database + Qdrant knowledge search

Dev_story is an existing agent package in ai-agents. It extracts development narratives from git history and correlates them with Claude Code conversation transcripts. After publication, it will be configured to index the git bundle archives (see Git History Preservation) as additional history sources.

### Layout

```
hapax-council/
├── agents/                # 26 agents + 4 agent packages (voice, demo_pipeline, dev_story, system_ops)
├── shared/                # 42 shared modules
├── cockpit/               # FastAPI API + data collectors + reactive engine
├── council-web/           # React dashboard (from cockpit-web, renamed)
├── vscode/                # VS Code extension (from hapax-vscode)
├── skills/                # Claude Code skills (from hapax-system)
├── hooks/                 # Claude Code hooks (from hapax-system)
├── axioms/                # Axiom registry + implications (instantiation of hapax-core pattern)
├── systemd/               # Timer/service units
├── docker/                # Dockerfiles + docker-compose.yml
├── tests/                 # Test suite
├── config/                # Seed configs
├── demo-data/             # Synthetic seed corpus (if applicable)
├── docs/                  # Design docs, operations manual
├── pyproject.toml
├── ruff.toml
├── CLAUDE.md
├── README.md
└── LICENSE
```

### Source Mapping

| Source | Destination | Notes |
|---|---|---|
| ai-agents/agents/ | agents/ | Direct move |
| ai-agents/shared/ | shared/ | Direct move |
| ai-agents/cockpit/ | cockpit/ | Direct move |
| ai-agents/tests/ | tests/ | Direct move |
| ai-agents/axioms/ | axioms/ | Direct move |
| ai-agents/pyproject.toml | pyproject.toml | Rename package to hapax-council |
| ai-agents/docker-compose.yml, Dockerfile.* | docker/ | Consolidated |
| ai-agents/systemd/ | systemd/ | Direct move |
| ai-agents/demo-data/ | demo-data/ | Verify at copy time; hapax-council may not have a demo corpus like hapax-officium |
| ai-agents/config/ | config/ | Direct move |
| hapax-system/skills/ | skills/ | Claude Code slash commands |
| hapax-system/hooks/ | hooks/ | Axiom scanning, session context |
| hapax-system/rules/ | docs/rules/ | System context docs (not ~/.claude/ rules) |
| hapax-system/install.sh | scripts/install-claude-code.sh | Renamed |
| cockpit-web/ | council-web/ | Renamed |
| hapax-vscode/ | vscode/ | Direct move |

### What Gets Dropped

- `.git/` from each source repo (fresh squashed commit)
- `.venv/`, `node_modules/`, `__pycache__/`
- Source-repo-specific CI configs (replaced with unified CI)
- hapax-system's symlink logic for `~/.claude/rules/` (personal machine config — post-publication, operator installs rules from hapax-council via `scripts/install-claude-code.sh` which symlinks skills/, hooks/, and rules into `~/.claude/`)

### Path Resolution

Same approach as hapax-officium: flattened layout means `_PROJECT_ROOT` chains lose `.parent` levels wherever ai-agents had extra nesting. Systematic `rg` search to find and fix all `Path(__file__).resolve().parent` chains.

### Scrubbing Rules

**Replace with generic equivalent:**
- "Ryan Kleeberger" -> "the operator" (except LICENSE)
- "Ryan" in code fallbacks (voice.py, persona.py) -> "Operator" or config-driven
- "Minneapolis-St. Paul, MN" -> remove
- "CST" timezone -> remove or "America/Chicago"
- Family references -> remove
- "ChatGPT Enterprise" -> "employer-provided LLM tools"
- Work/personal vault paths -> generic

**Remove entirely (from operator.json):**
- Substance use details (THC patterns, timing)
- Hygiene/sexual behavior markers
- Psychological state categorization
- Sleep pattern specifics
- Location data

**Keep as-is (intentionally public):**
- ADHD/autism diagnosis and executive function framing
- Neurodivergent communication preferences in prompts
- Domain corpus documents
- Executive function axiom
- Hardware details, service topology
- Agent logic, accommodation patterns, context gating

**operator.json:** Scrub intimate behavioral fields, keep structural fields (dimensions, goals, schedule framework). Profile structure is part of the system's design.

### License

Apache 2.0, same as hapax-core and hapax-officium. All three repos use the same license.

### CI

5-job GitHub Actions workflow (same structure as hapax-officium):
1. lint — ruff check + format
2. typecheck — pyright
3. test — pytest
4. web-build — council-web ESLint + Vite build
5. vscode-build — TypeScript compile

---

## hapax-officium

**Source:** ~/projects/hapax-mgmt/ (already published as hapax-mgmt)

**Purpose:** Management decision support instantiation. Rename + scrub verification + cross-references.

### Scrub Verification

Although hapax-mgmt was scrubbed during initial publication, re-audit under the unified scrubbing rules to catch anything that may have passed the first time (e.g., absolute home paths in docs, string patterns added during CI fix commits). This is a verification pass, not a full re-scrub.

### GitHub-Level

- Rename repo `ryanklee/hapax-mgmt` -> `ryanklee/hapax-officium` via GitHub API
- GitHub auto-redirects old URL

### Code Changes

- `pyproject.toml`: name -> "hapax-officium"
- `hapax-mgmt-web/` -> `officium-web/` (directory rename)
- `hapax-mgmt-web/package.json`: name field update
- CI workflow references updated
- README.md: repo name, clone URL, cross-references to hapax-core and hapax-council
- CLAUDE.md: full update — layout tree (`hapax-mgmt/` root, `hapax-mgmt-web/` references), Data Directory section, repo description, all directory references. This is more than find-and-replace; the layout diagram and multiple narrative sections reference the old name.
- Import paths or config referencing old name

### Local Cutover

- `mv ~/projects/hapax-mgmt ~/projects/hapax-officium`
- Update git remote URL
- Recreate .venv
- Update `~/.claude/projects/` memory directory

---

## Git History Preservation

Before cutover from any source repo:

```bash
git bundle create ~/backups/ai-agents-history.bundle --all
git bundle create ~/backups/hapaxromana-history.bundle --all
git bundle create ~/backups/hapax-system-history.bundle --all
git bundle create ~/backups/cockpit-web-history.bundle --all
git bundle create ~/backups/hapax-vscode-history.bundle --all
```

Dev_story's git extractor will be configured to index these bundles as additional history sources alongside the current repo's history. Commit SHA correlation with Claude Code conversations is preserved.

### Claude Code Conversation Histories

Claude Code conversation transcripts (JSONL files in `~/.claude/projects/`) contain the development narrative — design discussions, architectural reasoning, debugging sessions — that git history alone cannot capture. Before any directory renames or cutover:

```bash
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-mgmt/ ~/backups/claude-conversations/hapax-mgmt/
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-ai-agents/ ~/backups/claude-conversations/ai-agents/
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-hapaxromana/ ~/backups/claude-conversations/hapaxromana/
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-system/ ~/backups/claude-conversations/hapax-system/
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-cockpit-web/ ~/backups/claude-conversations/cockpit-web/
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-vscode/ ~/backups/claude-conversations/hapax-vscode/
```

Dev_story should index these alongside git bundles for complete commit-conversation correlation across the pre-publication history.

Original repos archived at `~/projects/.archive/` after cutover (same pattern as hapax-mgmt -> hapax-mgmt-pre-publish).

---

## Execution Strategy

Three parallel tracks, all following the hapax-officium playbook. **Track ordering:** Track 3 (hapax-officium rename) should execute last, after hapax-core and hapax-council exist, so cross-reference URLs in READMEs resolve. If Track 2 stalls, Tracks 1 and 3 can ship independently — the cross-references will point to a not-yet-existing hapax-council repo, which is acceptable (the URL will resolve once council publishes).

### Track 1: hapax-core (small)
1. Copy hapaxromana to working directory
2. Scrub (~10-15 files)
3. Write pattern-guide.md and README.md
4. Fresh squashed commit
5. Create GitHub repo, push

### Track 2: hapax-council (large)
1. Create working directory
2. Copy + consolidate 5 source repos into unified layout
3. Fix path resolution (_PROJECT_ROOT chains)
4. Scrub (~10 string replacements + operator.json)
5. Fix imports, update package names
6. Run tests, lint, typecheck — fix failures
7. Set up CI
8. Fresh squashed commit
9. Create GitHub repo, push

### Track 3: hapax-officium (mechanical)
1. Rename GitHub repo via API
2. Rename directory and package references
3. Update README with cross-references
4. Push, verify CI

### Post-Publication
- Git bundle all source repos
- Archive originals to ~/.archive/
- Cutover local working directories
- Update ~/.claude/ memory and project configs (create new project memory directories for hapax-officium and hapax-council, migrate relevant content from hapax-mgmt memory)
- Set up branch protection on new repos
- Verify all CI green

---

## Cross-References

Each repo's README links to the other two:

**Note on axiom sets:** hapax-core documents the full axiom vocabulary (single_operator, decision_support, management_safety, executive_function, corporate_boundary). hapax-council instantiates all five. hapax-officium instantiates a subset (single_operator, decision_support, management_safety + dormant corporate_boundary). The executive_function axiom is specific to the personal system.

- hapax-core: "See [hapax-council](link) for the operational implementation and [hapax-officium](link) for a management domain instantiation."
- hapax-council: "Built on the architectural pattern defined in [hapax-core](link). See [hapax-officium](link) for a domain-specific fork."
- hapax-officium: "A management instantiation of the [hapax-core](link) pattern. See [hapax-council](link) for the full operational system."
