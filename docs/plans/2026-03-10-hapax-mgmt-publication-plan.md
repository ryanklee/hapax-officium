# hapax-mgmt GitHub Publication Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Assemble hapax-mgmt into a clean, PII-free, CI-ready public GitHub repo with Apache 2.0 licensing.

**Architecture:** Create a fresh git repo at `~/projects/hapax-mgmt-publish/` by copying from the current hapax-mgmt, flattening the ai-agents/ to top-level, renaming `hapax-mgmt-web/` → `hapax-mgmt-web/` and `vscode/` → `vscode/`, scrubbing all PII, adding CI/docs/licensing, then pushing to GitHub.

**Tech Stack:** Python 3.12+, uv, React/TypeScript (pnpm), GitHub Actions, ruff, pyright

**Spec:** `docs/specs/2026-03-10-monorepo-consolidation-design.md`

---

## File Structure

| Path | Action | Responsibility |
|------|--------|----------------|
| `pyproject.toml` | Create (from pyproject.toml) | Package metadata, deps, pytest config for flattened layout |
| `uv.lock` | Generate | Lock file (regenerated after pyproject.toml update) |
| `LICENSE` | Create | Apache 2.0 license text |
| `README.md` | Create | Public-facing project documentation |
| `CLAUDE.md` | Create (from root + ai-agents CLAUDE.md) | PII-scrubbed contributor guide |
| `CONTRIBUTING.md` | Create | Contribution guidelines |
| `SECURITY.md` | Copy | Security policy |
| `.editorconfig` | Create | Editor consistency |
| `.gitignore` | Create (merged from root + ai-agents) | Comprehensive ignore rules |
| `.github/workflows/ci.yml` | Create | Lint + typecheck + test + web build |
| `ruff.toml` | Create | Python linting config |
| `pyrightconfig.json` | Create | Python type checking config |
| `agents/` | Copy from agents/ | Agent implementations (unchanged) |
| `shared/` | Copy from shared/ | Shared modules (unchanged) |
| `cockpit/` | Copy from cockpit/ | API server + reactive engine (unchanged) |
| `tests/` | Copy from tests/ | Test suite (import paths unchanged) |
| `config/` | Copy from config/ + move profiles | Role matrix, org dossier, scenarios, audiences, personas |
| `demo-data/` | Copy | Synthetic seed corpus |
| `data/` | Create (.gitkeep only) | DATA_DIR placeholder |
| `profiles/` | Create (.gitkeep only) | Runtime state placeholder |
| `axioms/` | Copy | Governance axioms |
| `docs/` | Copy | Design docs and plans |
| `scripts/` | Copy from scripts/ | Bootstrap and operational scripts |
| `hapax-mgmt-web/` | Copy from hapax-mgmt-web/ (renamed) | React dashboard |
| `vscode/` | Copy from vscode/ | VS Code extension |
| `Dockerfile` | Create (from Dockerfile) | Agent image with flattened paths |
| `Dockerfile.dev` | Create (from root Dockerfile.dev) | Dev container with flattened paths |
| `entrypoint.sh` | Copy from entrypoint.sh | Docker entrypoint |
| `entrypoint-dev.sh` | Copy from root entrypoint-dev.sh | Dev container entrypoint |
| `.dockerignore` | Create (merged) | Docker build exclusions |
| `agent-architecture.md` | Copy | Architecture reference |
| `operations-manual.md` | Copy | Operations reference |

---

## Chunk 1: Scaffold and Licensing

### Task 1: Create fresh repo and add licensing

**Files:**
- Create: `~/projects/hapax-mgmt-publish/LICENSE`
- Create: `~/projects/hapax-mgmt-publish/.gitignore`
- Create: `~/projects/hapax-mgmt-publish/.editorconfig`

- [ ] **Step 1: Create the fresh repo directory**

```bash
mkdir -p ~/projects/hapax-mgmt-publish
cd ~/projects/hapax-mgmt-publish
git init -b main
```

- [ ] **Step 2: Create Apache 2.0 LICENSE**

Download the standard Apache 2.0 license text:

```bash
cd ~/projects/hapax-mgmt-publish
curl -sL https://www.apache.org/licenses/LICENSE-2.0.txt > LICENSE
```

Prepend the copyright notice to the top of the file:

```
Copyright 2026 the operator

Licensed under the Apache License, Version 2.0 (the "License");
you may not use this file except in compliance with the License.
```

Note: The full legal name stays in LICENSE — this is standard practice and required by the license. PII scrubbing does not apply to license files.

- [ ] **Step 3: Create .editorconfig**

```ini
root = true

[*]
indent_style = space
indent_size = 4
end_of_line = lf
charset = utf-8
trim_trailing_whitespace = true
insert_final_newline = true

[*.{js,jsx,ts,tsx,json,yaml,yml,css,html}]
indent_size = 2

[*.md]
trim_trailing_whitespace = false

[Makefile]
indent_style = tab
```

- [ ] **Step 4: Create comprehensive .gitignore**

Merge the root and ai-agents gitignores into one:

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
build/
dist/
wheels/
*.egg-info/
.venv/
.venv-*/

# Secrets
.env
.envrc

# Editor / OS
*.swp
*.swo
*~
.DS_Store
.idea/
.vscode/settings.json

# Claude Code
.claude/settings.local.json
.claude/agent-memory/

# Profiles (generated runtime state)
profiles/*.json
profiles/*.md
profiles/*.jsonl
profiles/*.yaml
profiles/*.bak
profiles/*.wav
!profiles/.gitkeep

# Management data (personal, never committed)
data/**/*.md
data/**/*.json
data/**/*.yaml
!data/.gitkeep

# Demo outputs
output/

# Video / Audio
*.mp4
*.wav

# Node
node_modules/
dist/

# Worktrees
.worktrees/

# Coverage
.coverage
htmlcov/
coverage/
```

- [ ] **Step 5: Initial commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add LICENSE .gitignore .editorconfig
git commit -m "chore: initial scaffold with Apache 2.0 license"
```

### Task 2: Add Python tooling configs

**Files:**
- Create: `~/projects/hapax-mgmt-publish/ruff.toml`
- Create: `~/projects/hapax-mgmt-publish/pyrightconfig.json`

- [ ] **Step 1: Create ruff.toml**

Start permissive — don't break existing code. Tighten over time.

```toml
target-version = "py312"
line-length = 100

[lint]
select = [
    "E",     # pycodestyle errors
    "F",     # pyflakes
    "I",     # isort
    "UP",    # pyupgrade
    "B",     # flake8-bugbear
    "SIM",   # flake8-simplify
    "TCH",   # flake8-type-checking
]
ignore = [
    "E501",  # line too long (handled by formatter)
    "SIM108", # ternary operator (readability preference)
]

[lint.isort]
known-first-party = ["agents", "shared", "cockpit"]

[format]
quote-style = "double"
```

- [ ] **Step 2: Create pyrightconfig.json**

Start in basic mode — don't overwhelm with existing type issues.

```json
{
    "include": ["agents", "shared", "cockpit"],
    "exclude": ["tests", "**/__pycache__"],
    "pythonVersion": "3.12",
    "typeCheckingMode": "basic",
    "reportMissingImports": true,
    "reportMissingTypeStubs": false
}
```

- [ ] **Step 3: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add ruff.toml pyrightconfig.json
git commit -m "chore: add ruff and pyright configs"
```

### Task 3: Add CI workflow

**Files:**
- Create: `~/projects/hapax-mgmt-publish/.github/workflows/ci.yml`

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
      - uses: astral-sh/ruff-action@v3
        with:
          args: "check"
      - uses: astral-sh/ruff-action@v3
        with:
          args: "format --check"

  typecheck:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run pyright

  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v5
      - run: uv sync
      - run: uv run pytest tests/ -q

  web-build:
    runs-on: ubuntu-latest
    defaults:
      run:
        working-directory: hapax-mgmt-web
    steps:
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
        with:
          version: 9
      - uses: actions/setup-node@v4
        with:
          node-version: 22
          cache: pnpm
          cache-dependency-path: hapax-mgmt-web/pnpm-lock.yaml
      - run: pnpm install --frozen-lockfile
      - run: pnpm lint
      - run: pnpm build

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
      - run: pnpm run compile
```

- [ ] **Step 2: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add .github/workflows/ci.yml
git commit -m "ci: add lint, typecheck, test, and build workflows"
```

---

## Chunk 2: Copy and Flatten Python Codebase

### Task 4: Copy and flatten ai-agents content to repo root

**Files:**
- Copy: `agents/`, `shared/`, `cockpit/`, `tests/`, `config/`, `demo-data/`, `scripts/`
- Create: `pyproject.toml`, `data/.gitkeep`, `profiles/.gitkeep`
- Copy: `entrypoint.sh`

- [ ] **Step 1: Copy Python source directories**

```bash
SRC=~/projects/hapax-mgmt/ai-agents
DEST=~/projects/hapax-mgmt-publish

cp -r "$SRC/agents" "$DEST/agents"
cp -r "$SRC/shared" "$DEST/shared"
cp -r "$SRC/cockpit" "$DEST/cockpit"
cp -r "$SRC/tests" "$DEST/tests"
cp -r "$SRC/config" "$DEST/config"
cp -r "$SRC/demo-data" "$DEST/demo-data"
cp -r "$SRC/scripts" "$DEST/scripts"
cp "$SRC/entrypoint.sh" "$DEST/entrypoint.sh"

# Create placeholder dirs
mkdir -p "$DEST/data" "$DEST/profiles"
touch "$DEST/data/.gitkeep" "$DEST/profiles/.gitkeep"
```

**Note:** The following directories from the source repo are intentionally excluded — they are not part of the published repo: `llm-stack/`, `claude-config/`, `hapax-system/`, `domains/`, `knowledge/`, `research/`. If you see them in the source, they belong to hapax-core or are infrastructure config.

- [ ] **Step 2: Create pyproject.toml for flattened layout**

Based on `pyproject.toml` with updated paths:

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.backends"

[project]
name = "hapax-mgmt"
version = "1.0.0"
requires-python = ">=3.12"
dependencies = [
    "fastapi>=0.115.0",
    "httpx>=0.28.0",
    "jinja2>=3.1",
    "langfuse>=3.14.5",
    "matplotlib>=3.9",
    "ollama>=0.6.1",
    "pillow>=11.0.0",
    "pydantic>=2.12.5",
    "pydantic-ai[litellm]>=1.63.0",
    "pyyaml>=6.0",
    "qdrant-client>=1.17.0",
    "sse-starlette>=2.0.0",
    "uvicorn>=0.34.0",
    "watchdog>=4.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=9.0.2",
    "pytest-asyncio>=1.3.0",
    "pyright>=1.1.390",
    "ruff>=0.9.0",
]

[project.scripts]
cockpit = "cockpit.__main__:main"
logos-api = "cockpit.api.__main__:main"

[tool.hatch.build.targets.wheel]
packages = ["agents", "cockpit", "shared"]

[tool.pytest.ini_options]
asyncio_mode = "auto"
markers = [
    "slow: marks tests as slow (deselect with '-m \"not slow\"')",
]

[tool.ruff]
extend = "ruff.toml"
```

- [ ] **Step 3: Generate lock file**

```bash
cd ~/projects/hapax-mgmt-publish
uv lock
```

- [ ] **Step 4: Run tests to verify flattened layout works**

```bash
cd ~/projects/hapax-mgmt-publish
uv sync
uv run pytest tests/ -q --tb=short 2>&1 | tail -15
```

Expected: All tests pass (approximately 1253 passed, 31 skipped). If import errors occur, they indicate paths that need adjustment — fix before continuing.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add agents/ shared/ cockpit/ tests/ config/ demo-data/ scripts/ data/ profiles/ pyproject.toml uv.lock entrypoint.sh
git commit -m "feat: add Python codebase with flattened directory structure"
```

### Task 5: Copy remaining project files

**Files:**
- Copy: `axioms/`, `docs/`, `agent-architecture.md`, `operations-manual.md`, `SECURITY.md`
- Copy and update: `Dockerfile`, `Dockerfile.dev`, `entrypoint-dev.sh`, `.dockerignore`

- [ ] **Step 1: Copy documentation and axioms**

```bash
SRC=~/projects/hapax-mgmt
DEST=~/projects/hapax-mgmt-publish

cp -r "$SRC/axioms" "$DEST/axioms"
cp -r "$SRC/docs" "$DEST/docs"
cp "$SRC/agent-architecture.md" "$DEST/"
cp "$SRC/operations-manual.md" "$DEST/"
cp "$SRC/SECURITY.md" "$DEST/"
cp "$SRC/entrypoint-dev.sh" "$DEST/"
cp "$SRC/.dockerignore" "$DEST/"
```

- [ ] **Step 2: Create Dockerfile (flattened paths)**

Based on `Dockerfile`, update COPY paths:

Replace all `COPY` lines that reference the ai-agents/ subdirectories with root-level equivalents:
- `COPY agents/ agents/` (was `COPY agents/ agents/` or similar)
- `COPY shared/ shared/`
- `COPY cockpit/ cockpit/`
- `COPY pyproject.toml uv.lock ./`
- `COPY demo-data/ demo-data/`
- `COPY config/ config/`
- `COPY profiles/ profiles/`

Read the original Dockerfile, replicate its structure with updated paths. The WORKDIR stays `/app`. The CMD stays `python -m cockpit.api`.

Also rename the Docker service/image from `hapax-agents` to `hapax-mgmt-api` in the Dockerfile and any docker-compose references:

```bash
rg -l "hapax-agents" ~/projects/hapax-mgmt-publish/ --glob '*.yml' --glob '*.yaml' --glob 'Dockerfile*' --glob '*.conf'
```

Update any matches found.

- [ ] **Step 3: Create Dockerfile.dev (flattened paths)**

Based on root `Dockerfile.dev`, update paths:
- Remove `COPY ai-agents/ ` prefix — files are now at root
- Remove `WORKDIR /app/ai-agents` — WORKDIR is `/app`
- Update any `cd ai-agents` references

- [ ] **Step 4: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add axioms/ docs/ agent-architecture.md operations-manual.md SECURITY.md Dockerfile Dockerfile.dev entrypoint-dev.sh .dockerignore
git commit -m "feat: add docs, axioms, Dockerfiles, and operational references"
```

### Task 6: Copy and rename cockpit-web → hapax-mgmt-web

**Files:**
- Copy: `~/projects/hapax-mgmt/hapax-mgmt-web/` → `~/projects/hapax-mgmt-publish/hapax-mgmt-web/`

- [ ] **Step 1: Copy and rename**

```bash
cp -r ~/projects/hapax-mgmt/cockpit-web ~/projects/hapax-mgmt-publish/hapax-mgmt-web
# Remove node_modules and dist if copied
rm -rf ~/projects/hapax-mgmt-publish/hapax-mgmt-web/node_modules
rm -rf ~/projects/hapax-mgmt-publish/hapax-mgmt-web/dist
```

- [ ] **Step 2: Update package.json name**

In `hapax-mgmt-web/package.json`, change the `"name"` field from `"cockpit-web"` (or whatever it currently is) to `"hapax-mgmt-web"`.

- [ ] **Step 3: Update Dockerfile service name references**

In `hapax-mgmt-web/Dockerfile`, `hapax-mgmt-web/nginx.conf`, and any docker-compose references, rename service from `cockpit-web` to `hapax-mgmt-web`.

- [ ] **Step 4: Verify web build**

```bash
cd ~/projects/hapax-mgmt-publish/hapax-mgmt-web
pnpm install
pnpm build
```

Expected: Clean build, no errors.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add hapax-mgmt-web/
git commit -m "feat: add hapax-mgmt-web dashboard (renamed from cockpit-web)"
```

### Task 7: Copy and rename hapax-vscode → vscode

**Files:**
- Copy: `~/projects/hapax-mgmt/vscode/` → `~/projects/hapax-mgmt-publish/vscode/`

- [ ] **Step 1: Copy and rename**

Copy from the in-repo copy (not the sibling project directory):

```bash
cp -r ~/projects/hapax-mgmt/hapax-vscode ~/projects/hapax-mgmt-publish/vscode
rm -rf ~/projects/hapax-mgmt-publish/vscode/node_modules
rm -rf ~/projects/hapax-mgmt-publish/vscode/dist
rm -rf ~/projects/hapax-mgmt-publish/vscode/.git
```

- [ ] **Step 2: Verify extension compiles**

```bash
cd ~/projects/hapax-mgmt-publish/vscode
pnpm install
pnpm run compile
```

Expected: Clean compile, no errors.

- [ ] **Step 3: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add vscode/
git commit -m "feat: add VS Code extension (from hapax-vscode)"
```

---

## Chunk 3: PII Scrubbing

### Task 8: Move demo config files from profiles to config

**Files:**
- Move: `profiles/demo-audiences.yaml` → `config/demo-audiences.yaml`
- Move: `profiles/demo-personas.yaml` → `config/demo-personas.yaml`
- Move: `profiles/presenter-style.yaml` → `config/presenter-style.yaml`
- Update: `.gitignore` (remove profile exceptions for moved files)

- [ ] **Step 1: Move files**

These were already copied to `~/projects/hapax-mgmt-publish/` under their original locations. Move them:

```bash
cd ~/projects/hapax-mgmt-publish
# These files are in profiles/ but were excepted from gitignore in the source.
# Copy from the source profiles directory since they may not have been included in the initial copy.
cp ~/projects/hapax-mgmt/profiles/demo-audiences.yaml config/demo-audiences.yaml
cp ~/projects/hapax-mgmt/profiles/demo-personas.yaml config/demo-personas.yaml
cp ~/projects/hapax-mgmt/profiles/presenter-style.yaml config/presenter-style.yaml
cp ~/projects/hapax-mgmt/profiles/workflow-registry.yaml config/workflow-registry.yaml
# Note: component-registry.yaml is runtime-generated, not a seed file. It does not exist on disk and is not needed.
```

- [ ] **Step 2: Update any code that references profiles/ paths for these files**

Search for references to `profiles/demo-audiences`, `profiles/demo-personas`, `profiles/presenter-style`, `profiles/workflow-registry` in the Python code and update to `config/`:

```bash
cd ~/projects/hapax-mgmt-publish
rg "profiles/(demo-audiences|demo-personas|presenter-style|workflow-registry)" agents/ shared/ cockpit/ --files-with-matches
```

Update each file found to reference `config/` instead of `profiles/`.

- [ ] **Step 3: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add config/demo-audiences.yaml config/demo-personas.yaml config/presenter-style.yaml config/workflow-registry.yaml
git commit -m "chore: move seed config files from profiles/ to config/"
```

### Task 9: Scrub real names and PII

**Files:**
- Modify: All files containing "the operator", "Family Member", "Jordan Rivera", "engineering leader"

- [ ] **Step 1: Scrub "the operator" → "the operator"**

```bash
cd ~/projects/hapax-mgmt-publish
# Find all occurrences
rg -l "the operator" --glob '!LICENSE'
```

For each file found, replace "the operator" with "the operator" (or contextually appropriate alternative). Key files:

- `tests/test_operator.py`: Replace in mock data and assertions. Change `"name": "the operator"` to `"name": "Operator"` in test fixtures.
- `tests/test_context_tools.py`: Same pattern — mock operator data.
- `hapax-system/rules/axioms.md` (if present): "the operator (Hapax)" → "the operator (Hapax)"
- `docs/plans/*.md`: Replace in axiom definitions.
- `research/axiom-enforcement.md`: Replace.

- [ ] **Step 2: Scrub operator first name in operator-identity contexts**

```bash
rg -l "\bRyan\b" --glob '!LICENSE'
```

Replace operator name with "the operator" or "Operator" where it refers to the system operator. Do NOT replace in unrelated contexts (e.g., fictional character names if any exist). Key locations:

- `axioms/implications/single-operator.yaml`: "the operator's preferences" → "the operator's preferences"
- `config/demo-audiences.yaml`: References in audience characterizations
- Test files: Mock data references

- [ ] **Step 3: Scrub spouse and colleague data from demo-audiences.yaml**

Edit `config/demo-audiences.yaml`:

- Remove the "a family member" / "Family Member" audience section entirely, or replace with a generic "family" persona using fictional details:
  ```yaml
  - name: Family Member
    archetype: family
    description: "A non-technical family member curious about what the system does"
  ```
- Replace "Jordan Rivera" with a fictional persona:
  ```yaml
  - name: Jordan Rivera
    archetype: leadership
    description: "A senior technical leader evaluating the system for engineering management"
  ```
- Remove "engineering leader" title references
- Remove any characterization that identifies real people

- [ ] **Step 4: Scrub absolute paths**

```bash
cd ~/projects/hapax-mgmt-publish
rg -l "~" --glob '!LICENSE'
```

Replace `~/projects/...` with relative paths or `~/...` as appropriate. In documentation and plans, use generic examples like `~/projects/hapax-mgmt/`.

- [ ] **Step 5: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add -A
git commit -m "chore: scrub PII (names, paths, personal identifiers)"
```

### Task 10: Scrub medical and neurodivergence references

**Files:**
- Modify: Files containing medical info tied to operator identity

- [ ] **Step 1: Identify all files**

```bash
cd ~/projects/hapax-mgmt-publish
rg -li "\b(medical-info)\b"
```

- [ ] **Step 2: Classify each file using the three-category rule**

For each file found, apply:

1. **REMOVE** — Demo personas, audience profiles, presenter styles where medical info is tied to operator identity. Delete the references.
   - `config/demo-audiences.yaml`: Remove medical information from audience descriptions
   - `config/presenter-style.yaml`: Remove medical references tied to operator
   - `vscode/package.json`: Remove medical information from system prompt
   - `vscode/src/settings.ts`: Remove medical references

2. **GENERALIZE** — Architecture docs explaining accommodation features.
   - `agents/demo_pipeline/domain_corpus/executive-function-accommodation.md`: Replace specific diagnoses with "neurodivergent-friendly design patterns"
   - `agents/demo_pipeline/domain_corpus/cognitive-load-theory.md`: Keep if generic; generalize if tied to operator
   - `agents/demo_pipeline/domain_corpus/neurodivergent-technology-design.md`: Keep — this is about design principles, not operator identity

3. **KEEP** — Purely technical references not identity-linked. Default to REMOVE if uncertain.

- [ ] **Step 3: Apply changes**

Edit each file per the classification above.

- [ ] **Step 4: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add -A
git commit -m "chore: scrub medical references per classification rule"
```

### Task 11: Run PII verification pass

- [ ] **Step 1: Run all PII verification greps**

```bash
cd ~/projects/hapax-mgmt-publish

echo "=== Full name ==="
rg -i "operator-name" --glob '!LICENSE'

echo "=== Spouse ==="
rg "\bFamily Member\b" .

echo "=== Colleague ==="
rg -i "jordan rivera" .
rg -i "\bchris b\b" .

echo "=== Job title ==="
rg "\bAVP\b" .

echo "=== Home directory ==="
rg "~" .

echo "=== Username ==="
rg "user" .

echo "=== Personal paths ==="
rg "~/Documents/(Work|Personal)" .

echo "=== Medical (review manually) ==="
rg -i "\b(medical-info)\b" .
```

Expected: Zero results for all except the medical grep, which should only show generalized/technical references (not identity-linked).

- [ ] **Step 2: Fix any remaining PII found**

If any grep returns results, fix and re-run until clean.

- [ ] **Step 3: Commit if any fixes were made**

```bash
cd ~/projects/hapax-mgmt-publish
git add -A
git commit -m "chore: final PII scrubbing pass"
```

---

## Chunk 4: Documentation and Reference Updates

### Task 12: Update all documentation references for flattened layout

**Files:**
- Modify: `CLAUDE.md` (create new), `docs/` files, `agent-architecture.md`, `operations-manual.md`

- [ ] **Step 1: Create scrubbed CLAUDE.md**

Write a new CLAUDE.md that merges the root and ai-agents CLAUDE.md files, with these changes:

- Remove all the ai-agents/ path prefixes (e.g., `agents/` → `agents/`)
- Remove `~/projects/...` absolute paths
- Remove references to `llm-stack/`, `claude-config/`, `hapax-system/` (not in this repo)
- Update `hapax-mgmt-web/` references to `hapax-mgmt-web/`
- Remove any operator-specific context (home directory, personal vault paths)
- Keep: agent roster, testing instructions, conventions, project layout, data directory docs, reactive engine docs
- Update running instructions: `uv run python -m agents.<name>` (no `cd ai-agents` prefix)
- Update test instructions: `uv run pytest tests/ -q` (no `cd ai-agents` prefix)

- [ ] **Step 2: Update docs/ references**

Search all markdown files in `docs/` for references to the old directory structure:

```bash
cd ~/projects/hapax-mgmt-publish
rg "" docs/ --files-with-matches
rg "hapax-mgmt-web/" docs/ --files-with-matches
rg "hapax-vscode" docs/ --files-with-matches
```

Update each reference:
- `agents/` → `agents/`
- `shared/` → `shared/`
- `cockpit/` → `cockpit/`
- `tests/` → `tests/`
- `config/` → `config/`
- `hapax-mgmt-web/` → `hapax-mgmt-web/`
- `vscode/` → `vscode/`

- [ ] **Step 3: Update agent-architecture.md and operations-manual.md**

Same reference updates as above. Search and replace the ai-agents/ prefixes.

- [ ] **Step 4: Update scripts/bootstrap-demo.sh**

Remove any `cd ai-agents` prefix. The script now runs from the repo root. Update paths:
- `uv run python -m agents.X` stays the same
- Any `$AI_AGENTS_DIR` variable should point to repo root, not a subdirectory
- Update doc references in script comments

- [ ] **Step 5: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add -A
git commit -m "docs: update all references for flattened layout and renames"
```

### Task 13: Write public README.md

**Files:**
- Create: `~/projects/hapax-mgmt-publish/README.md`

- [ ] **Step 1: Write README**

```markdown
# hapax-mgmt

A management decision support cockpit for engineering managers. AI agents prepare context for 1:1s, track management practice patterns, surface stale conversations and open loops, and profile management self-awareness. A React dashboard provides the operational interface.

**Safety principle:** LLMs prepare, humans deliver. The system never generates feedback language, coaching recommendations, or evaluations of individual team members.

## Quick Start

```bash
# Clone and install
git clone https://github.com/<user>/hapax-mgmt.git
cd hapax-mgmt
uv sync

# Run tests (all mocked, no external services needed)
uv run pytest tests/ -q

# Bootstrap with demo data (requires Qdrant, LiteLLM, Ollama)
./scripts/bootstrap-demo.sh

# Run the logos API
uv run python -m cockpit.api --host 127.0.0.1 --port 8050
```

## Project Structure

```
hapax-mgmt/
├── agents/           AI agents (management prep, briefing, profiling, simulator, demo)
├── shared/           Shared modules (config, notifications, data bridge, axiom governance)
├── logos/          FastAPI API server + reactive engine
├── hapax-mgmt-web/   React dashboard
├── vscode/           VS Code extension
├── demo-data/        Synthetic seed corpus for demo hydration
├── config/           Role matrix, org dossier, scenarios, audience personas
├── axioms/           Constitutional governance axioms
├── tests/            Test suite (1250+ tests, all mocked)
├── scripts/          Bootstrap and operational scripts
└── docs/             Design specs and implementation plans
```

## Agents

| Agent | LLM? | Purpose |
|-------|------|---------|
| management_prep | Yes | 1:1 prep docs, team snapshots, management overviews |
| meeting_lifecycle | Yes | Meeting prep automation, transcript processing |
| management_briefing | Yes | Morning management briefing |
| management_profiler | Yes | Management self-awareness profiling (6 dimensions) |
| management_activity | No | Management practice metrics (1:1 rates, feedback timing) |
| digest | Yes | Content/knowledge digest from Qdrant |
| scout | Yes | Horizon scanning for component fitness |
| drift_detector | Yes | Documentation drift detection |
| status_update | Yes | Upward-facing status reports |
| review_prep | Yes | Performance review evidence aggregation |
| simulator | Yes | Temporal simulation of management activity |
| demo | Yes | Audience-tailored system demonstrations |
| system_check | No | Health checks for core services |

## Demo System

The demo seed system produces a fully-hydrated replica with realistic synthetic data. Bootstrap it with `./scripts/bootstrap-demo.sh` — this copies `demo-data/` into `data/`, runs deterministic agents, then LLM synthesis agents. After completion, the logos API serves live management state with real nudges, team health indicators, and briefings.

Use `--skip-llm` for data-pipeline-only testing (no external services needed beyond the filesystem).

## Infrastructure

The cockpit requires three external services:

| Service | Purpose | Default Port |
|---------|---------|-------------|
| LiteLLM | LLM API gateway | 4000 |
| Qdrant | Vector database | 6333 |
| Ollama | Local model inference | 11434 |

All LLM calls route through LiteLLM for observability. Embeddings use `nomic-embed-text` (768 dimensions).

## License

Apache License 2.0. See [LICENSE](LICENSE).
```

- [ ] **Step 2: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add README.md
git commit -m "docs: add public README"
```

### Task 14: Write CONTRIBUTING.md

**Files:**
- Create: `~/projects/hapax-mgmt-publish/CONTRIBUTING.md`

- [ ] **Step 1: Write CONTRIBUTING.md**

```markdown
# Contributing to hapax-mgmt

## Development Setup

```bash
git clone https://github.com/<user>/hapax-mgmt.git
cd hapax-mgmt
uv sync
```

## Running Tests

```bash
uv run pytest tests/ -q
```

All tests are mocked — no external services (Qdrant, LiteLLM, Ollama) needed.

## Code Style

- **Python 3.12+** with mandatory type hints
- **Pydantic models** for structured data
- **ruff** for linting and formatting: `uv run ruff check . && uv run ruff format --check .`
- **pyright** for type checking: `uv run pyright`
- **Conventional commits** (feat:, fix:, chore:, docs:, ci:, refactor:, test:)

## Branch Workflow

1. Create a feature branch from `main`
2. Make changes, add tests
3. Ensure all tests pass and linting is clean
4. Open a pull request

## Safety Principle

This system follows the principle: **LLMs prepare, humans deliver.** Contributions must not add features that generate feedback language, coaching recommendations, or evaluations of individual team members. See `axioms/registry.yaml` for the full governance framework.
```

- [ ] **Step 2: Commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add CONTRIBUTING.md
git commit -m "docs: add CONTRIBUTING.md"
```

---

## Chunk 5: Final Validation and GitHub Push

### Task 15: Full validation

- [ ] **Step 1: Run Python test suite**

```bash
cd ~/projects/hapax-mgmt-publish
uv run pytest tests/ -q --tb=short 2>&1 | tail -15
```

Expected: All tests pass (approximately 1253 passed, 31 skipped).

- [ ] **Step 2: Run ruff lint**

```bash
cd ~/projects/hapax-mgmt-publish
uv run ruff check . 2>&1 | tail -20
```

Note: First run may show existing violations. If so, either fix them or add to `ruff.toml` ignore list. The goal is CI-green, not zero warnings on day one.

- [ ] **Step 3: Run ruff format check**

```bash
cd ~/projects/hapax-mgmt-publish
uv run ruff format --check . 2>&1 | tail -20
```

If files need reformatting, run `uv run ruff format .` and commit.

- [ ] **Step 4: Run pyright**

```bash
cd ~/projects/hapax-mgmt-publish
uv run pyright 2>&1 | tail -20
```

Note: May show type errors in existing code. Adjust `pyrightconfig.json` strictness or add type stubs as needed. The goal is CI-green.

- [ ] **Step 5: Verify web build**

```bash
cd ~/projects/hapax-mgmt-publish/hapax-mgmt-web
pnpm install && pnpm build
```

- [ ] **Step 6: Verify VS Code extension build**

```bash
cd ~/projects/hapax-mgmt-publish/vscode
pnpm install && pnpm run compile
```

- [ ] **Step 7: Final PII verification**

```bash
cd ~/projects/hapax-mgmt-publish
rg -i "operator-name" --glob '!LICENSE'
rg "\bFamily Member\b" .
rg -i "jordan rivera" .
rg "\bAVP\b" .
rg "~" .
rg "user" .
rg "~/Documents/(Work|Personal)" .
```

Expected: Zero results for all.

- [ ] **Step 8: Fix any issues found and commit**

```bash
cd ~/projects/hapax-mgmt-publish
git add -A
git commit -m "chore: final validation fixes"
```

### Task 16: Squash history, create GitHub repo, and push

The assembly process created multiple intermediate commits, some of which contain PII that was later scrubbed. Squash into a single clean initial commit before pushing.

- [ ] **Step 1: Squash all commits into one**

```bash
cd ~/projects/hapax-mgmt-publish
git reset --soft $(git rev-list --max-parents=0 HEAD)
git commit --amend -m "feat: initial release of hapax-mgmt management cockpit"
```

This collapses all commits into a single initial commit with no PII in history.

- [ ] **Step 2: Create GitHub repo**

Replace `<user>` with your GitHub username throughout this task.

```bash
gh repo create hapax-mgmt \
  --public \
  --description "Management decision support cockpit for engineering managers"
```

Note: Do not use `--license` since the LICENSE file is already committed.

- [ ] **Step 3: Add remote and push**

```bash
cd ~/projects/hapax-mgmt-publish
git remote add origin git@github.com:<user>/hapax-mgmt.git
git push -u origin main
```

- [ ] **Step 4: Verify on GitHub**

```bash
gh repo view hapax-mgmt --web
```

Check: README renders correctly, LICENSE shows Apache 2.0, CI workflow triggers on the push.

- [ ] **Step 5: Enable branch protection**

```bash
gh api repos/<user>/hapax-mgmt/branches/main/protection \
  -X PUT \
  -f "required_status_checks[strict]=true" \
  -f "required_status_checks[contexts][]=lint" \
  -f "required_status_checks[contexts][]=test" \
  -f "enforce_admins=false" \
  -f "required_pull_request_reviews=null" \
  -f "restrictions=null"
```

### Task 17: Cutover local workspace

- [ ] **Step 1: Archive old repo**

```bash
mkdir -p ~/projects/.archive
mv ~/projects/hapax-mgmt ~/projects/.archive/hapax-mgmt-pre-publish
```

- [ ] **Step 2: Rename publish directory**

```bash
mv ~/projects/hapax-mgmt-publish ~/projects/hapax-mgmt
```

- [ ] **Step 3: Verify working copy**

```bash
cd ~/projects/hapax-mgmt
git remote -v    # Should show GitHub origin
uv run pytest tests/ -q --tb=short 2>&1 | tail -5   # Should pass
```

- [ ] **Step 4: Update Claude Code memory**

Update `~/.claude/projects/-home-user-projects-hapax-mgmt/memory/MEMORY.md` to reflect the new repo structure (flattened layout, renamed directories).
