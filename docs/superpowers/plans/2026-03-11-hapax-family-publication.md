# Hapax Family Publication Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Publish the complete Hapax system as three coordinated repos: hapax-core (architectural patterns), hapax-council (operational system), hapax-officium (management instantiation).

**Architecture:** Three parallel tracks following the proven hapax-mgmt publication playbook. Each track produces a fresh-squashed public repo. Git histories are preserved as bundles before cutover. Claude Code conversation histories are preserved separately (they contain the development narrative context that git history alone cannot capture). Privacy enforcement uses 4 non-negotiable criteria (PII, employer IP, operational security, personal safety). ADHD/autism framing is intentionally public.

**Tech Stack:** Python (uv), React (pnpm/Vite), TypeScript (esbuild), GitHub Actions CI, git bundles, gh CLI

**Design Spec:** `docs/superpowers/specs/2026-03-11-hapax-family-publication-design.md`

---

## Chunk 1: Track 1 — hapax-core (Documentation Repo)

### Task 1: Create working directory and copy source

**Files:**
- Source: `~/projects/hapaxromana/` (entire repo)
- Create: `~/projects/hapax-core/` (working directory)

- [ ] **Step 1: Create working directory**

```bash
mkdir -p ~/projects/hapax-core
```

- [ ] **Step 2: Copy hapaxromana contents (excluding .git)**

```bash
rsync -av \
  --exclude='.git' \
  --exclude='__pycache__' \
  --exclude='.claude' \
  --exclude='.playwright-mcp' \
  ~/projects/hapaxromana/ ~/projects/hapax-core/
```

- [ ] **Step 3: Initialize fresh git repo**

```bash
cd ~/projects/hapax-core && git init && git checkout -b main
```

- [ ] **Step 4: Verify copy**

```bash
ls -la ~/projects/hapax-core/
```

Expected: axioms/, docs/, domains/, knowledge/, research/, CLAUDE.md, README.md, agent-architecture.md, operations-manual.md, plus image files.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/hapax-core
git add -A
git commit -m "chore: initial copy from hapaxromana"
```

---

### Task 2: Scrub hapax-core content

**Files:**
- Modify: All markdown and YAML files in `~/projects/hapax-core/`
- Key files: `axioms/registry.yaml`, `axioms/implications/*.yaml`, `CLAUDE.md`, `docs/**/*.md`, `domains/**/*.md`, `knowledge/**/*.md`

Scrubbing rules (from design spec):
- Operator name ("Ryan Kleeberger", "Ryan") → "the operator"
- Employer references in corporate_boundary axiom → generalized
- Team member names in design docs → removed/generalized
- Home directory absolute paths (`/home/hapaxlegomenon/`, `~/projects/`) → relative paths
- Location data ("Minneapolis-St. Paul", "CST") → removed
- Family references → removed

ADHD/autism diagnosis, executive function framing, neurodivergent communication preferences → **keep as-is** (intentionally public).

- [ ] **Step 1: Search for scrub targets**

```bash
cd ~/projects/hapax-core
# Search for operator name
rg -i "ryan|kleeberger" --type md --type yaml -l
# Search for absolute home paths
rg "/home/hapaxlegomenon|~/projects/" --type md --type yaml -l
# Search for location data
rg -i "minneapolis|CST|central\s+standard" --type md --type yaml -l
# Search for employer references
rg -i "employer|company name" --type md --type yaml -l
# Search for family references
rg -i "wife|husband|partner|children|kids|family" --type md --type yaml -l
```

- [ ] **Step 2: Apply scrubs to each identified file**

For each file found in step 1, open and replace:
- `Ryan Kleeberger` → `the operator` (except in LICENSE)
- `Ryan` (standalone, as a name reference) → `the operator`
- `/home/hapaxlegomenon/projects/X` → relative path or `<project-root>/`
- `~/projects/X` → relative path or `<project-root>/`
- Location references → remove the containing sentence
- Family references → remove the containing sentence
- Employer name → "the employer" or "employer-provided tools"

- [ ] **Step 3: Verify no scrub targets remain**

```bash
cd ~/projects/hapax-core
rg -i "ryan|kleeberger|hapaxlegomenon|minneapolis" --type md --type yaml
```

Expected: Zero matches (except LICENSE which retains legal name).

- [ ] **Step 4: Privacy review of sensitive directories**

Explicitly review these files for intimate behavioral data (substance use, hygiene, psychological state, sleep patterns) that keyword scrubs won't catch:

```bash
cd ~/projects/hapax-core
cat knowledge/personal-sufficiency.yaml
```

Remove or redact any intimate behavioral content. Keep structural/architectural content.

Also review `research/` directory contents for private data:

```bash
ls research/
# Read each file and verify no private content
```

- [ ] **Step 5: Run a manual read-through of key files**

Read `axioms/registry.yaml`, `agent-architecture.md`, and `operations-manual.md` to verify scrubs read naturally and no private content remains.

- [ ] **Step 6: Commit**

```bash
cd ~/projects/hapax-core
git add -A
git commit -m "chore: scrub PII and private content"
```

---

### Task 3: Write pattern-guide.md

**Files:**
- Create: `~/projects/hapax-core/pattern-guide.md`

This is a **new document** that generalizes the Hapax architectural pattern. It covers:
1. Filesystem-as-bus (markdown + YAML frontmatter as state)
2. Agent architecture (Pydantic AI agents reading/writing the bus)
3. Axiom governance (constitutional constraints on LLM agents)
4. Reactive engine (inotify watcher → rule evaluation → phased execution)
5. Annotated code examples drawn from hapax-council

- [ ] **Step 1: Read source material for pattern extraction**

Read these files from `~/projects/ai-agents/` (the source, NOT the working copy) to extract generalizable patterns:
- `shared/config.py` — filesystem-as-bus, path constants
- `shared/frontmatter.py` — YAML frontmatter parsing
- `cockpit/engine/watcher.py` — inotify watcher
- `cockpit/engine/rules.py` — rule evaluation
- `cockpit/engine/executor.py` — phased execution
- `shared/axiom_registry.py` — axiom loading
- `shared/axiom_tools.py` — agent axiom tools
- `agent-architecture.md` — existing architecture doc

- [ ] **Step 2: Write pattern-guide.md**

Write the document with these sections:
```markdown
# Hapax Architectural Pattern Guide

## Overview
[One paragraph: axiom-governed reactive agent platform with filesystem-as-bus]

## Pattern 1: Filesystem-as-Bus
[Markdown files with YAML frontmatter as the state bus. Explain the data model,
frontmatter conventions, directory-as-collection pattern. Annotated example.]

## Pattern 2: Agent Architecture
[Three-tier agent system: Tier 1 (interactive), Tier 2 (on-demand), Tier 3 (autonomous).
Pydantic AI agents reading/writing the bus. Annotated example from an agent.]

## Pattern 3: Axiom Governance
[Constitutional constraints. Axiom registry (YAML). Implications (compatibility/sufficiency).
Precedent store. Agent tools for runtime compliance checks. Annotated examples.]

## Pattern 4: Reactive Engine
[inotify watcher → rule evaluation → phased execution (deterministic phase 0,
LLM phase 1+, semaphore-bounded). Annotated engine code.]

## Existence Proofs
[Link to hapax-council and hapax-officium as two instantiations of this pattern.]
```

- [ ] **Step 3: Review the document for quality and completeness**

Read through and verify:
- All code examples are scrubbed (no PII)
- Examples are self-contained and understandable
- Links to hapax-council and hapax-officium use correct GitHub URLs

- [ ] **Step 4: Commit**

```bash
cd ~/projects/hapax-core
git add pattern-guide.md
git commit -m "docs: add architectural pattern guide"
```

---

### Task 4: Write README.md and add LICENSE

**Files:**
- Modify: `~/projects/hapax-core/README.md` (rewrite)
- Create: `~/projects/hapax-core/LICENSE` (Apache 2.0)

- [ ] **Step 1: Write README.md**

```markdown
# hapax-core

Architectural pattern documentation for axiom-governed reactive agent platforms.

hapax-core defines the reference architecture — a constitutional governance
framework where LLM agents operate under explicit axioms, communicate through
a filesystem-as-bus, and react to state changes through a phased execution engine.

## Contents

- `axioms/` — Axiom definitions and derived implications
- `pattern-guide.md` — Generalized architectural pattern with annotated examples
- `agent-architecture.md` — Three-tier agent system design
- `operations-manual.md` — Operational reference
- `docs/` — Design documents and specifications
- `domains/` — Domain-specific extensions
- `knowledge/` — Knowledge base documents

## Existence Proofs

- **[hapax-council](https://github.com/ryanklee/hapax-council)** — Full operational
  implementation: reactive cockpit, voice daemon, sync pipeline, Claude Code integration.
  Instantiates all five axioms.
- **[hapax-officium](https://github.com/ryanklee/hapax-officium)** — Management domain
  instantiation: decision support, team health tracking, management profiling.
  Instantiates a subset of axioms (single_operator, decision_support, management_safety).

## License

Apache 2.0 — see [LICENSE](LICENSE).
```

- [ ] **Step 2: Create LICENSE file**

Use the standard Apache 2.0 license text with copyright holder "Ryan Kleeberger".

- [ ] **Step 3: Commit**

```bash
cd ~/projects/hapax-core
git add README.md LICENSE
git commit -m "docs: add README and Apache 2.0 license"
```

---

### Task 5: Remove non-publication files and clean up

**Files:**
- Remove: Image files (`.png`), any files that don't belong in a documentation repo
- Modify: Directory structure as needed

- [ ] **Step 1: Identify files to remove**

```bash
cd ~/projects/hapax-core
# List image files (screenshots from development, not documentation)
find . -name "*.png" -o -name "*.jpg" -o -name "*.gif" | head -20
# List any other non-documentation files
find . -type f ! -name "*.md" ! -name "*.yaml" ! -name "*.yml" ! -name "LICENSE" ! -name ".gitignore" | head -20
```

- [ ] **Step 2: Remove development screenshots**

Remove `.png` files that are development screenshots (chat-adaptive.png, dashboard-*.png, demo-*.png, etc.) unless they are referenced in documentation.

```bash
cd ~/projects/hapax-core
# Check which images are referenced in docs
rg "\.png" --type md
# Remove unreferenced images
rm -f chat-adaptive.png chat-gruvbox.png dashboard-*.png demo-*.png title-slide-check.png voice-demo-title.png
```

- [ ] **Step 3: Remove CLAUDE.md** (this is the source repo's working config, not documentation)

The published repo gets its own minimal CLAUDE.md or none at all (it's a docs repo with no runnable code).

```bash
rm ~/projects/hapax-core/CLAUDE.md
```

- [ ] **Step 4: Create .gitignore**

```bash
cat > ~/projects/hapax-core/.gitignore << 'EOF'
__pycache__/
.claude/
.playwright-mcp/
*.pyc
EOF
```

- [ ] **Step 5: Commit**

```bash
cd ~/projects/hapax-core
git add -A
git commit -m "chore: remove non-publication files"
```

---

### Task 6: Squash and publish hapax-core

**Files:**
- Modify: Git history (squash to single commit)
- Create: GitHub repo `ryanklee/hapax-core`

- [ ] **Step 1: Squash all commits into one**

```bash
cd ~/projects/hapax-core
git reset --soft $(git rev-list --max-parents=0 HEAD)
git commit -m "Initial publication of hapax-core: architectural pattern documentation for axiom-governed reactive agent platforms"
```

- [ ] **Step 2: Final review of all content**

```bash
cd ~/projects/hapax-core
# One last PII check
rg -i "ryan|kleeberger|hapaxlegomenon|minneapolis" --type md --type yaml
# Verify structure
find . -type f ! -path './.git/*' | sort
```

- [ ] **Step 3: Create GitHub repo and push**

```bash
# Create empty repo (no --license flag — LICENSE already exists locally)
gh repo create ryanklee/hapax-core --public --description "Architectural pattern documentation for axiom-governed reactive agent platforms"
cd ~/projects/hapax-core
git remote add origin git@github.com:ryanklee/hapax-core.git
git push -u origin main
```

- [ ] **Step 4: Verify publication**

```bash
gh repo view ryanklee/hapax-core
```

- [ ] **Step 5: Commit verification**

Visually verify the repo at `https://github.com/ryanklee/hapax-core` — README renders, no PII visible, all links correct.

---

## Chunk 2: Track 3 — hapax-officium (Rename of hapax-mgmt)

Track 3 is placed before Track 2 because it's mechanical and fast. Track 2 (hapax-council) is large and complex.

### Task 7: Bundle hapax-mgmt git history

**Files:**
- Create: `~/backups/hapax-mgmt-history.bundle`

- [ ] **Step 1: Create backups directory**

```bash
mkdir -p ~/backups
```

- [ ] **Step 2: Create git bundle**

```bash
cd ~/projects/hapax-mgmt
git bundle create ~/backups/hapax-mgmt-history.bundle --all
```

- [ ] **Step 3: Verify bundle**

```bash
git bundle verify ~/backups/hapax-mgmt-history.bundle
```

Expected: Bundle is valid, lists all refs.

- [ ] **Step 4: Commit (no code changes — this is a backup step)**

No commit needed. Bundle is a backup artifact.

---

### Task 8: Rename GitHub repo and update code references

**Files:**
- Modify (GitHub): `ryanklee/hapax-mgmt` → `ryanklee/hapax-officium`
- Modify: `pyproject.toml` (name field)
- Modify: `hapax-mgmt-web/package.json` (name field)
- Modify: `README.md` (repo name, clone URL, cross-references)
- Modify: `CLAUDE.md` (layout tree, directory references, repo description)
- Modify: `.github/workflows/ci.yml` (if it references repo name)

- [ ] **Step 1: Rename repo on GitHub**

```bash
gh repo rename hapax-officium --repo ryanklee/hapax-mgmt --yes
```

- [ ] **Step 2: Update local git remote**

```bash
cd ~/projects/hapax-mgmt
git remote set-url origin git@github.com:ryanklee/hapax-officium.git
```

- [ ] **Step 3: Update pyproject.toml**

Change `name = "hapax-mgmt"` to `name = "hapax-officium"`.

- [ ] **Step 4: Rename hapax-mgmt-web/ directory**

```bash
cd ~/projects/hapax-mgmt
mv hapax-mgmt-web officium-web
```

- [ ] **Step 5: Update officium-web/package.json**

Change `"name": "hapax-mgmt-web"` to `"name": "officium-web"`.

- [ ] **Step 6: Update CI workflow**

In `.github/workflows/ci.yml`, update any references to `hapax-mgmt-web` → `officium-web` (the web-build job's working directory).

- [ ] **Step 7: Update README.md**

Update:
- Title and description
- Clone URL: `git@github.com:ryanklee/hapax-officium.git`
- Add cross-references:
  - "A management instantiation of the [hapax-core](https://github.com/ryanklee/hapax-core) pattern."
  - "See [hapax-council](https://github.com/ryanklee/hapax-council) for the full operational system."

- [ ] **Step 8: Update CLAUDE.md**

This is more than find-and-replace. Update:
- Layout tree: `hapax-mgmt/` root references, `hapax-mgmt-web/` → `officium-web/`
- Repo description: mention hapax-officium identity
- Data Directory section references
- Build commands (web working directory)
- Any narrative sections referencing old name

- [ ] **Step 9: Search for remaining references**

```bash
cd ~/projects/hapax-mgmt
rg "hapax-mgmt" --type py --type yaml --type toml --type json --type md -l
rg "hapax.mgmt" --type py -l
rg "hapax_mgmt" --type py -l
```

Update any remaining references found.

- [ ] **Step 10: Run tests**

```bash
cd ~/projects/hapax-mgmt
uv run pytest tests/ -q
```

Expected: All 1253+ tests pass.

- [ ] **Step 11: Run lint and typecheck**

```bash
uv run ruff check .
uv run pyright
```

- [ ] **Step 12: Commit and push**

```bash
cd ~/projects/hapax-mgmt
git add -A
git commit -m "chore: rename to hapax-officium"
git push
```

- [ ] **Step 13: Verify CI**

```bash
gh run watch
```

Expected: All 5 jobs pass.

- [ ] **Step 14: Verify branch protection survived rename**

```bash
gh api repos/ryanklee/hapax-officium/branches/main/protection --jq '.required_status_checks.contexts'
```

Expected: Should list all 5 status checks. If the CI workflow rename changed job names or the protection didn't survive, re-apply:

```bash
# Only if protection is missing or stale:
gh api repos/ryanklee/hapax-officium/branches/main/protection \
  --method PUT \
  --input - <<'EOF'
{
  "required_status_checks": {"strict": true, "contexts": ["lint", "typecheck", "test", "web-build", "vscode-build"]},
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
EOF
```

---

### Task 9: Scrub re-audit for hapax-officium

**Files:**
- Audit: All files in `~/projects/hapax-mgmt/`

The original hapax-mgmt was scrubbed during initial publication, but re-audit under the unified scrubbing rules.

- [ ] **Step 1: Search for scrub targets**

```bash
cd ~/projects/hapax-mgmt
# Operator name (should already be clean)
rg -i "ryan kleeberger" --type py --type md --type yaml -l
# Absolute home paths
rg "/home/hapaxlegomenon" --type py --type md --type yaml -l
rg "~/projects/" --type py --type md --type yaml --type toml -l
# Location data
rg -i "minneapolis|CST" --type py --type md --type yaml -l
# Employer references
rg -i "chatgpt enterprise" --type py --type md --type yaml -l
# Intimate behavioral data in operator.json
cat profiles/operator.json 2>/dev/null | head -50
```

- [ ] **Step 2: Fix any findings**

Apply same scrub rules as Track 1.

- [ ] **Step 3: Commit if changes were needed**

```bash
cd ~/projects/hapax-mgmt
git add -A
git commit -m "chore: scrub re-audit under unified rules"
git push
```

---

### Task 10: Local cutover for hapax-officium

**Files:**
- Move: `~/projects/hapax-mgmt/` → `~/projects/hapax-officium/`
- Update: `~/.claude/projects/` memory directory

- [ ] **Step 1: Rename local directory**

```bash
mv ~/projects/hapax-mgmt ~/projects/hapax-officium
```

- [ ] **Step 2: Recreate .venv**

```bash
cd ~/projects/hapax-officium
rm -rf .venv
uv venv
uv sync
```

- [ ] **Step 3: Verify tests still pass**

```bash
cd ~/projects/hapax-officium
uv run pytest tests/ -q
```

- [ ] **Step 4: Update Claude Code project memory**

Create new project memory directory for hapax-officium and migrate relevant content from hapax-mgmt memory.

```bash
# The old memory path
ls ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-mgmt/
# Create new path (Claude Code will auto-create on next session, but we can seed it)
mkdir -p ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-officium/memory/
cp ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-mgmt/memory/MEMORY.md \
   ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-officium/memory/MEMORY.md
```

- [ ] **Step 5: Update MEMORY.md with new repo info**

Edit the copied MEMORY.md to reflect the rename (hapax-mgmt → hapax-officium, new URLs, etc.).

---

## Chunk 3: Track 2 — hapax-council (Large Consolidation)

This is the largest track. It consolidates 5 source repos into one.

### Task 11: Bundle source repo git histories

**Files:**
- Create: `~/backups/ai-agents-history.bundle`
- Create: `~/backups/hapax-system-history.bundle`
- Create: `~/backups/cockpit-web-history.bundle`
- Create: `~/backups/hapax-vscode-history.bundle`
- Create: `~/backups/hapaxromana-history.bundle`

- [ ] **Step 1: Bundle all source repos**

```bash
mkdir -p ~/backups
cd ~/projects/ai-agents && git bundle create ~/backups/ai-agents-history.bundle --all
cd ~/projects/hapax-system && git bundle create ~/backups/hapax-system-history.bundle --all
cd ~/projects/cockpit-web && git bundle create ~/backups/cockpit-web-history.bundle --all
cd ~/projects/hapax-vscode && git bundle create ~/backups/hapax-vscode-history.bundle --all
cd ~/projects/hapaxromana && git bundle create ~/backups/hapaxromana-history.bundle --all
```

- [ ] **Step 2: Verify all bundles**

```bash
for bundle in ~/backups/*.bundle; do echo "=== $bundle ===" && git bundle verify "$bundle" && echo "OK"; done
```

Expected: All bundles valid.

- [ ] **Step 3: No commit — backup artifacts**

---

### Task 12: Create working directory and copy ai-agents

**Files:**
- Source: `~/projects/ai-agents/` (primary source)
- Create: `~/projects/hapax-council/`

- [ ] **Step 1: Create working directory**

```bash
mkdir -p ~/projects/hapax-council
```

- [ ] **Step 2: Copy ai-agents contents (excluding .git, .venv, __pycache__, node_modules)**

```bash
rsync -av \
  --exclude='.git' \
  --exclude='.venv' \
  --exclude='__pycache__' \
  --exclude='node_modules' \
  --exclude='output' \
  --exclude='.ruff_cache' \
  --exclude='.pyright' \
  ~/projects/ai-agents/ ~/projects/hapax-council/
```

- [ ] **Step 3: Initialize fresh git repo**

```bash
cd ~/projects/hapax-council && git init && git checkout -b main
```

- [ ] **Step 4: Verify copy**

```bash
ls -la ~/projects/hapax-council/
```

Expected: agents/, cockpit/, shared/, tests/, pyproject.toml, docker-compose.yml, Dockerfile.*, systemd/, etc.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/hapax-council
git add -A
git commit -m "chore: initial copy from ai-agents"
```

---

### Task 13: Consolidate secondary repos into hapax-council

**Files:**
- Source: `~/projects/cockpit-web/` → `council-web/`
- Source: `~/projects/hapax-vscode/` → `vscode/`
- Source: `~/projects/hapax-system/skills/` → `skills/`
- Source: `~/projects/hapax-system/hooks/` → `hooks/`
- Source: `~/projects/hapax-system/rules/` → `docs/rules/`
- Source: `~/projects/hapax-system/install.sh` → `scripts/install-claude-code.sh`

- [ ] **Step 1: Copy cockpit-web as council-web**

```bash
rsync -av \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='dist' \
  ~/projects/cockpit-web/ ~/projects/hapax-council/council-web/
```

- [ ] **Step 2: Copy hapax-vscode as vscode**

```bash
rsync -av \
  --exclude='.git' \
  --exclude='node_modules' \
  --exclude='dist' \
  ~/projects/hapax-vscode/ ~/projects/hapax-council/vscode/
```

- [ ] **Step 3: Copy hapax-system components**

```bash
# Skills
rsync -av ~/projects/hapax-system/skills/ ~/projects/hapax-council/skills/
# Hooks
rsync -av ~/projects/hapax-system/hooks/ ~/projects/hapax-council/hooks/
# Rules as documentation
mkdir -p ~/projects/hapax-council/docs/rules
rsync -av ~/projects/hapax-system/rules/ ~/projects/hapax-council/docs/rules/
# Install script
mkdir -p ~/projects/hapax-council/scripts
cp ~/projects/hapax-system/install.sh ~/projects/hapax-council/scripts/install-claude-code.sh
```

- [ ] **Step 4: Consolidate Docker files**

```bash
mkdir -p ~/projects/hapax-council/docker
mv ~/projects/hapax-council/docker-compose.yml ~/projects/hapax-council/docker/
mv ~/projects/hapax-council/Dockerfile.* ~/projects/hapax-council/docker/
# Move sync-pipeline crontab and entrypoint into docker/
mv ~/projects/hapax-council/sync-pipeline/ ~/projects/hapax-council/docker/sync-pipeline/
```

- [ ] **Step 5: Update docker/docker-compose.yml paths**

Since docker-compose.yml moved into `docker/`, update any relative paths (build contexts, volume mounts) to account for the new location. The build context paths need `../` prefix. Also update sync-pipeline references to `docker/sync-pipeline/`.

- [ ] **Step 6: Verify structure**

```bash
cd ~/projects/hapax-council
find . -maxdepth 2 -type d ! -path './.git*' | sort
```

Expected: agents/, cockpit/, shared/, tests/, council-web/, vscode/, skills/, hooks/, docs/, docker/, systemd/, scripts/, profiles/, data/

**Note:** ai-agents does NOT have `axioms/`, `config/`, or `demo-data/` directories (those are hapax-mgmt-specific). If axiom definitions are needed, they should be copied from hapaxromana in a later step.

- [ ] **Step 7: Commit**

```bash
cd ~/projects/hapax-council
git add -A
git commit -m "chore: consolidate cockpit-web, hapax-vscode, hapax-system into unified layout"
```

---

### Task 14: Fix path resolution

**Files:**
- Modify: All Python files with `Path(__file__).resolve().parent` chains
- Key file: `shared/config.py` (PROJECT_ROOT definition)

The flattened layout may require adjusting `_PROJECT_ROOT` chains. This was already done for hapax-mgmt — follow the same pattern.

- [ ] **Step 1: Find all path resolution patterns**

```bash
cd ~/projects/hapax-council
rg "Path\(__file__\)\.resolve\(\)\.parent" --type py -n
rg "_PROJECT_ROOT" --type py -n
rg "PROJECT_ROOT" --type py -n
```

- [ ] **Step 2: Verify PROJECT_ROOT resolves correctly**

Check `shared/config.py` — `PROJECT_ROOT = Path(__file__).resolve().parent.parent` should point to repo root. If ai-agents had extra nesting, adjust.

- [ ] **Step 3: Fix any broken path chains**

For each file found, verify the `.parent` chain produces the correct path in the flattened layout. Adjust as needed.

Also check for references to `docker-compose.yml` at repo root (now at `docker/docker-compose.yml`):

```bash
rg "docker-compose" --type py --type sh -n
```

- [ ] **Step 4: Commit**

```bash
cd ~/projects/hapax-council
git add -A
git commit -m "fix: adjust path resolution for flattened layout"
```

---

### Task 14b: Remove non-publication files from hapax-council

**Files:**
- Remove: Development screenshots, n8n workflows, promptfoo configs, and other non-publication artifacts

ai-agents contains development artifacts that should not be published.

- [ ] **Step 1: Identify non-publication files**

```bash
cd ~/projects/hapax-council
# Development screenshots
find . -name "*.png" -o -name "*.jpg" | head -20
# n8n workflows (internal automation, not part of the agent platform)
ls n8n-workflows/ 2>/dev/null
# promptfoo config (testing config, may contain private prompts)
ls promptfooconfig.yaml 2>/dev/null
# Makefile (check if needed)
cat Makefile 2>/dev/null | head -10
# Output directory (generated artifacts)
ls output/ 2>/dev/null
```

- [ ] **Step 2: Remove non-publication artifacts**

```bash
cd ~/projects/hapax-council
rm -rf n8n-workflows/ output/
rm -f promptfooconfig.yaml
# Remove dev screenshots (check which are referenced in docs first)
rg "\.png" --type md
# Remove unreferenced images
find . -maxdepth 1 -name "*.png" -delete
```

- [ ] **Step 3: Audit profiles/ and test-data/ directories**

```bash
cd ~/projects/hapax-council
# Check all files in profiles/ (not just operator.json)
ls -la profiles/
# Check test-data/ for private content
ls -la test-data/
```

Review each file for private content. Remove or scrub as needed.

- [ ] **Step 4: Commit**

```bash
cd ~/projects/hapax-council
git add -A
git commit -m "chore: remove non-publication files"
```

---

### Task 15: Rename package and update imports

**Files:**
- Modify: `pyproject.toml` (name, package references)
- Modify: Any import paths referencing old package name

- [ ] **Step 1: Update pyproject.toml**

Change `name = "ai-agents"` (or whatever the current name is) to `name = "hapax-council"`.

- [ ] **Step 2: Search for old package references**

```bash
cd ~/projects/hapax-council
rg "ai.agents" --type py --type toml --type yaml -l
rg "ai_agents" --type py --type toml --type yaml -l
```

- [ ] **Step 3: Update any found references**

Replace old package name with hapax-council equivalents.

- [ ] **Step 4: Commit**

```bash
cd ~/projects/hapax-council
git add -A
git commit -m "chore: rename package to hapax-council"
```

---

### Task 16: Scrub hapax-council content

**Files:**
- Modify: All files matching scrub patterns

Scrub patterns (from design spec):
- "Ryan Kleeberger" → "the operator" (except LICENSE)
- "Ryan" in code fallbacks (voice.py, persona.py) → "Operator" or config-driven
- "Minneapolis-St. Paul, MN" → remove
- "CST" timezone → remove or "America/Chicago"
- Family references → remove
- "ChatGPT Enterprise" → "employer-provided LLM tools"
- Work/personal vault paths → generic
- operator.json intimate behavioral fields → remove (keep structural fields)

- [ ] **Step 1: Search for all scrub targets**

```bash
cd ~/projects/hapax-council
rg -i "ryan kleeberger|ryan" --type py --type md --type yaml --type json -l
rg -i "minneapolis|CST|central.standard" --type py --type md --type yaml -l
rg "/home/hapaxlegomenon|~/projects/" --type py --type md --type yaml --type toml -l
# Catch hapaxlegomenon in any context (GitHub URLs, Docker mounts, systemd units)
rg "hapaxlegomenon" -l
rg -i "chatgpt enterprise" --type py --type md --type yaml -l
rg -i "wife|husband|partner|children|family" --type py --type md --type yaml --type json -l
rg "Documents/Work|Documents/Personal|obsidian" --type py --type md --type yaml -l
```

- [ ] **Step 2: Apply scrubs to each file**

Follow the same rules as Task 2 (hapax-core scrub). Additionally:
- In voice agent code, replace hardcoded "Ryan" with config-driven operator name
- In persona code, replace personal references with generic
- Update vault paths to generic placeholders

- [ ] **Step 3: Scrub operator.json**

```bash
cat ~/projects/hapax-council/profiles/operator.json 2>/dev/null
```

Remove intimate behavioral fields:
- Substance use details (THC patterns, timing)
- Hygiene/sexual behavior markers
- Psychological state categorization
- Sleep pattern specifics
- Location data

Keep structural fields (dimensions, goals, schedule framework).

- [ ] **Step 4: Verify no scrub targets remain**

```bash
cd ~/projects/hapax-council
rg -i "ryan kleeberger|hapaxlegomenon|minneapolis" --type py --type md --type yaml --type json
```

Expected: Zero matches (except LICENSE).

- [ ] **Step 5: Commit**

```bash
cd ~/projects/hapax-council
git add -A
git commit -m "chore: scrub PII and private content"
```

---

### Task 17: Write README.md, LICENSE, and CLAUDE.md

**Files:**
- Create/Modify: `~/projects/hapax-council/README.md`
- Create: `~/projects/hapax-council/LICENSE` (Apache 2.0)
- Create/Modify: `~/projects/hapax-council/CLAUDE.md`

- [ ] **Step 1: Write README.md**

```markdown
# hapax-council

The deliberative body: a full operational agent platform implementing externalized
executive function infrastructure. Reactive cockpit, voice daemon, sync pipeline,
Claude Code integration — all governed by constitutional axioms.

Built on the architectural pattern defined in [hapax-core](https://github.com/ryanklee/hapax-core).
See [hapax-officium](https://github.com/ryanklee/hapax-officium) for a management domain instantiation.

## Architecture

- **Agents**: 26+ Pydantic AI agents across management, sync/RAG, analysis, system, and content categories
- **Agent Packages**: hapax_voice (voice daemon), demo_pipeline (demo generation), dev_story (development narrative)
- **Cockpit API**: FastAPI backend with reactive engine (inotify → rule evaluation → phased execution)
- **Dashboard**: React SPA (council-web)
- **VS Code Extension**: Chat, RAG search, management integration
- **Claude Code Integration**: Skills, hooks, and rules for Claude Code sessions

## Quick Start

[Installation and setup instructions]

## License

Apache 2.0 — see [LICENSE](LICENSE).
```

- [ ] **Step 2: Create LICENSE**

Apache 2.0 with copyright holder "Ryan Kleeberger".

- [ ] **Step 3: Update CLAUDE.md**

Adapt the existing CLAUDE.md from ai-agents to reflect the consolidated repo layout, updated paths, and hapax-council identity.

- [ ] **Step 4: Commit**

```bash
cd ~/projects/hapax-council
git add README.md LICENSE CLAUDE.md
git commit -m "docs: add README, LICENSE, and CLAUDE.md"
```

---

### Task 18: Set up CI for hapax-council

**Files:**
- Create: `~/projects/hapax-council/.github/workflows/ci.yml`

5-job GitHub Actions workflow (same structure as hapax-officium):

- [ ] **Step 1: Create CI workflow**

```yaml
name: CI
on:
  push:
    branches: [main]
  pull_request:
    branches: [main]
jobs:
  lint:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run ruff check .
      - run: uv run ruff format --check .
  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run pyright
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync --frozen
      - run: uv run pytest tests/ -q
  web-build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: council-web
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: council-web/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm run lint
      - run: pnpm run build
  vscode-build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: vscode
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: vscode/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      # Verify actual script name in vscode/package.json — may be "build" not "compile"
      - run: pnpm run build
```

**Note:** Check `vscode/package.json` for the actual build script name. The existing hapax-mgmt CI uses `build`. Adjust if the actual script is named differently.

- [ ] **Step 2: Commit**

```bash
cd ~/projects/hapax-council
mkdir -p .github/workflows
git add .github/workflows/ci.yml
git commit -m "ci: add 5-job GitHub Actions workflow"
```

---

### Task 19: Fix lint, typecheck, and test failures

**Files:**
- Modify: Various files as needed to pass CI checks

This task follows the same pattern as the hapax-mgmt CI fix. Expect similar issues:
- ruff lint errors (same ruff.toml ignore list may be needed)
- pyright errors (qdrant SDK nullable types, forward references)
- Test failures (missing env vars, import issues from consolidation)

- [ ] **Step 1: Run ruff and fix lint errors**

```bash
cd ~/projects/hapax-council
uv run ruff check . --fix
uv run ruff format .
```

Review and fix any remaining errors manually. Add same ruff.toml ignore rules as hapax-officium if needed (E402, E501, E741, SIM105, SIM108).

- [ ] **Step 2: Run pyright and fix type errors**

```bash
cd ~/projects/hapax-council
uv run pyright
```

Fix errors following same patterns as hapax-officium (nullable qdrant payloads, RunContext imports, etc.).

- [ ] **Step 3: Run tests and fix failures**

```bash
cd ~/projects/hapax-council
uv run pytest tests/ -q
```

Fix failures. Common issues:
- Import paths changed by consolidation
- Missing test data paths
- Environment variable assumptions

- [ ] **Step 4: Run web build**

```bash
cd ~/projects/hapax-council/council-web
pnpm install
pnpm run lint
pnpm run build
```

Fix ESLint errors following same patterns as hapax-officium.

- [ ] **Step 5: Run vscode build**

```bash
cd ~/projects/hapax-council/vscode
pnpm install
pnpm run compile
```

- [ ] **Step 6: Commit all fixes**

```bash
cd ~/projects/hapax-council
git add -A
git commit -m "fix: resolve lint, typecheck, and test failures"
```

---

### Task 20: Squash and publish hapax-council

**Files:**
- Modify: Git history (squash to single commit)
- Create: GitHub repo `ryanklee/hapax-council`

- [ ] **Step 1: Squash all commits into one**

```bash
cd ~/projects/hapax-council
git reset --soft $(git rev-list --max-parents=0 HEAD)
git commit -m "Initial publication of hapax-council: axiom-governed reactive agent platform with externalized executive function infrastructure"
```

- [ ] **Step 2: Final PII check**

```bash
cd ~/projects/hapax-council
rg -i "ryan kleeberger|hapaxlegomenon|minneapolis" --type py --type md --type yaml --type json
```

Expected: Zero matches (except LICENSE).

- [ ] **Step 3: Create GitHub repo and push**

```bash
# Create empty repo (no --license flag — LICENSE already exists locally)
gh repo create ryanklee/hapax-council --public --description "Axiom-governed reactive agent platform: externalized executive function infrastructure"
cd ~/projects/hapax-council
git remote add origin git@github.com:ryanklee/hapax-council.git
git push -u origin main
```

- [ ] **Step 4: Set up branch protection**

```bash
gh api repos/ryanklee/hapax-council/branches/main/protection \
  --method PUT \
  --input - <<'EOF'
{
  "required_status_checks": {
    "strict": true,
    "contexts": ["lint", "typecheck", "test", "web-build", "vscode-build"]
  },
  "enforce_admins": false,
  "required_pull_request_reviews": null,
  "restrictions": null
}
EOF
```

- [ ] **Step 5: Verify CI passes**

```bash
cd ~/projects/hapax-council
gh run watch
```

Expected: All 5 jobs pass.

---

## Chunk 4: Post-Publication

### Task 21: Archive source repos

**Files:**
- Move: Source repos to `~/projects/.archive/`

- [ ] **Step 1: Create archive directory**

```bash
mkdir -p ~/projects/.archive
```

- [ ] **Step 2: Archive source repos**

```bash
mv ~/projects/ai-agents ~/projects/.archive/ai-agents-pre-council
mv ~/projects/hapax-system ~/projects/.archive/hapax-system-pre-council
mv ~/projects/cockpit-web ~/projects/.archive/cockpit-web-pre-council
mv ~/projects/hapax-vscode ~/projects/.archive/hapax-vscode-pre-council
mv ~/projects/hapaxromana ~/projects/.archive/hapaxromana-pre-core
```

- [ ] **Step 3: Verify archives exist**

```bash
ls ~/projects/.archive/
```

---

### Task 22: Update cross-references and verify

**Files:**
- Verify: All three repos' READMEs have correct cross-reference URLs

- [ ] **Step 1: Verify hapax-core cross-references**

Check that README.md links to hapax-council and hapax-officium resolve.

```bash
gh repo view ryanklee/hapax-council --json url
gh repo view ryanklee/hapax-officium --json url
gh repo view ryanklee/hapax-core --json url
```

- [ ] **Step 2: Update hapax-officium README if needed**

If hapax-officium was published before hapax-council existed, the cross-reference URL to hapax-council now resolves. Verify it works.

- [ ] **Step 3: Verify all CI green across all three repos**

```bash
gh run list --repo ryanklee/hapax-core --limit 1
gh run list --repo ryanklee/hapax-council --limit 1
gh run list --repo ryanklee/hapax-officium --limit 1
```

---

### Task 23: Preserve Claude Code conversation histories

**Files:**
- Archive: `~/.claude/projects/` conversation transcripts for all affected projects

Claude Code conversation histories contain the development narrative context — design discussions, architectural reasoning, debugging sessions — that git history alone cannot capture. These must be preserved before any directory renames or cutover.

- [ ] **Step 1: Identify conversation history locations**

```bash
# List all project memory directories
ls -la ~/.claude/projects/

# Find conversation transcript files (JSONL format)
find ~/.claude/projects/ -name "*.jsonl" -type f | head -20

# Check sizes
du -sh ~/.claude/projects/*/
```

- [ ] **Step 2: Archive conversation histories**

```bash
mkdir -p ~/backups/claude-conversations

# Archive all project conversation transcripts
# hapax-mgmt conversations
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-mgmt/ \
  ~/backups/claude-conversations/hapax-mgmt-conversations/

# ai-agents conversations (if they exist)
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-ai-agents/ \
  ~/backups/claude-conversations/ai-agents-conversations/ 2>/dev/null || true

# hapaxromana conversations (if they exist)
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-hapaxromana/ \
  ~/backups/claude-conversations/hapaxromana-conversations/ 2>/dev/null || true

# hapax-system conversations (if they exist)
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-system/ \
  ~/backups/claude-conversations/hapax-system-conversations/ 2>/dev/null || true

# cockpit-web conversations (if they exist)
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-cockpit-web/ \
  ~/backups/claude-conversations/cockpit-web-conversations/ 2>/dev/null || true

# hapax-vscode conversations (if they exist)
cp -r ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-vscode/ \
  ~/backups/claude-conversations/hapax-vscode-conversations/ 2>/dev/null || true
```

- [ ] **Step 3: Verify archives**

```bash
ls -la ~/backups/claude-conversations/
# Count transcript files
find ~/backups/claude-conversations/ -name "*.jsonl" | wc -l
```

- [ ] **Step 4: Document the archive**

Create an index file:

```bash
cat > ~/backups/claude-conversations/INDEX.md << 'EOF'
# Claude Code Conversation Archive

Archived before hapax family publication (2026-03-11).

| Directory | Source Project | Published As |
|-----------|---------------|--------------|
| hapax-mgmt-conversations/ | ~/projects/hapax-mgmt | hapax-officium |
| ai-agents-conversations/ | ~/projects/ai-agents | hapax-council |
| hapaxromana-conversations/ | ~/projects/hapaxromana | hapax-core |
| hapax-system-conversations/ | ~/projects/hapax-system | hapax-council (merged) |
| cockpit-web-conversations/ | ~/projects/cockpit-web | hapax-council (merged) |
| hapax-vscode-conversations/ | ~/projects/hapax-vscode | hapax-council (merged) |

These transcripts contain the full development narrative — design discussions,
architectural reasoning, debugging sessions — that git history alone cannot capture.
dev_story agent should be configured to index these alongside git bundles.
EOF
```

---

### Task 24: Configure dev_story for bundle and conversation indexing

**Files:**
- Modify: `~/projects/hapax-council/agents/dev_story/` source code (may require feature development)

- [ ] **Step 1: Assess current dev_story capabilities**

Read the dev_story agent source to understand:
- How it discovers git history sources
- Whether it already supports git bundles as additional sources
- How it correlates commits with Claude Code conversations

```bash
cd ~/projects/hapax-council
find agents/dev_story/ -name "*.py" | head -20
# Read the main module and git extraction code
```

- [ ] **Step 2: Determine scope — configuration vs feature development**

If dev_story already supports configurable history sources and bundle paths, this is a configuration task. If it does not, this becomes a feature development task that should be planned separately.

For configuration: add bundle and conversation archive paths to dev_story's config.

For feature development: create a separate design spec and plan for dev_story bundle support. The key capability needed:
- Read git bundles as additional history sources
- Index conversation transcripts from the archive directory
- Correlate commits across bundles with conversations across archived projects

- [ ] **Step 3: Configure or note for future implementation**

If configurable:
```bash
cd ~/projects/hapax-council
# Add configuration (exact mechanism depends on Step 1 findings)
```

If feature development needed:
Note this as a follow-up task. The bundles and conversation archives are preserved and waiting.

- [ ] **Step 4: Commit if changes were made**

```bash
cd ~/projects/hapax-council
git add -A
git commit -m "feat: configure dev_story to index archived git bundles and conversation histories"
```

---

### Task 25: Update Claude Code project configurations

**Files:**
- Update: `~/.claude/projects/` memory directories
- Update: `~/projects/hapax-system/rules/system-context.md` references (if still used)

- [ ] **Step 1: Create hapax-council project memory**

```bash
mkdir -p ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-council/memory/
```

- [ ] **Step 2: Migrate ai-agents project memory if it exists**

```bash
# Check for existing ai-agents memory
ls ~/.claude/projects/-home-hapaxlegomenon-projects-ai-agents/memory/ 2>/dev/null
```

If it exists, copy and adapt the content for hapax-council:

```bash
cp ~/.claude/projects/-home-hapaxlegomenon-projects-ai-agents/memory/MEMORY.md \
   ~/.claude/projects/-home-hapaxlegomenon-projects-hapax-council/memory/MEMORY.md
```

Then edit the copied MEMORY.md to reflect the hapax-council identity, consolidated layout, and new repo URLs.

- [ ] **Step 3: Seed MEMORY.md for hapax-council**

If no ai-agents memory existed, write initial MEMORY.md with:
- Repo status (published, URL, license)
- Layout (consolidated from 5 repos)
- CI configuration
- Key architecture decisions

- [ ] **Step 4: Update hapax-system rules if still in use**

If `~/projects/hapax-system/rules/system-context.md` is still symlinked into `~/.claude/rules/`, update the references to reflect new repo names and locations. Since hapax-system is now archived, the symlinks may need to point to hapax-council equivalents:

```bash
# Check current symlinks
ls -la ~/.claude/rules/
# Update any that point to archived repos
```

- [ ] **Step 5: Verify Claude Code recognizes new projects**

Start a new Claude Code session in each project directory and verify it picks up the correct CLAUDE.md and memory.
