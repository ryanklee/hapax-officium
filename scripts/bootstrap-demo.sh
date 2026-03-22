#!/usr/bin/env bash
set -euo pipefail

# ============================================================================
# bootstrap-demo.sh — Hydrate the logos system from demo seed data
#
# Takes the system from empty to fully warm:
#   Phase 0: Pre-flight checks (infrastructure healthy)
#   Phase 1: Seed DATA_DIR and profiles/ from demo-data/
#   Phase 2: Ensure Qdrant collections exist
#   Phase 3: Run deterministic agents (parallel)
#   Phase 4: Run LLM synthesis agents (sequential)
#   Phase 5: Validate warm state
#
# Usage:
#   ./scripts/bootstrap-demo.sh [--skip-llm] [--verbose]
#
# Flags:
#   --skip-llm    Skip LLM-dependent agents (phases 4). Useful for testing
#                 the data pipeline without API keys.
#   --verbose     Show agent output instead of suppressing it.
# ============================================================================

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AI_AGENTS_DIR="$(cd "$SCRIPT_DIR/.." && pwd)"
DEMO_DATA_DIR="$AI_AGENTS_DIR/demo-data"
DATA_DIR="$AI_AGENTS_DIR/data"
PROFILES_DIR="$AI_AGENTS_DIR/profiles"

QDRANT_URL="${QDRANT_URL:-http://127.0.0.1:6433}"
LITELLM_BASE="${LITELLM_API_BASE:-http://127.0.0.1:4100}"
OLLAMA_URL="${OLLAMA_URL:-http://127.0.0.1:11434}"
EMBED_DIMS=768

SKIP_LLM=false
VERBOSE=false

for arg in "$@"; do
    case "$arg" in
        --skip-llm) SKIP_LLM=true ;;
        --verbose)  VERBOSE=true ;;
        *) echo "Unknown flag: $arg" >&2; exit 1 ;;
    esac
done

# ── Helpers ────────────────────────────────────────────────────────────────

_log() { echo "bootstrap: $*"; }
_ok()  { echo "  ✓ $*"; }
_warn(){ echo "  ⚠ $*" >&2; }
HAVE_FAILURES=false
_fail(){ echo "  ✗ $*" >&2; HAVE_FAILURES=true; exit 1; }

_run_agent() {
    local name="$1"; shift
    _log "Running $name ..."
    if $VERBOSE; then
        uv run python -m "$name" "$@"
    else
        uv run python -m "$name" "$@" 2>/dev/null
    fi
}

_check_http() {
    local url="$1" label="$2"
    if curl -sf --connect-timeout 5 --max-time 10 "$url" >/dev/null 2>&1; then
        _ok "$label reachable"
        return 0
    else
        return 1
    fi
}

# ── Phase 0: Pre-flight checks ────────────────────────────────────────────

_log "Phase 0: Pre-flight checks"

[ -d "$DEMO_DATA_DIR" ] || _fail "demo-data/ directory not found at $DEMO_DATA_DIR"
[ -d "$DEMO_DATA_DIR/people" ] || _fail "demo-data/people/ not found"

PEOPLE_COUNT=$(find "$DEMO_DATA_DIR/people" -name '*.md' | wc -l)
[ "$PEOPLE_COUNT" -gt 0 ] || _fail "No person files in demo-data/people/"
_ok "$PEOPLE_COUNT person files in demo-data/"

_check_http "${QDRANT_URL}/healthz" "Qdrant" || _fail "Qdrant not reachable at $QDRANT_URL"
_check_http "${OLLAMA_URL}/api/tags" "Ollama" || _warn "Ollama not reachable (embeddings will fail)"

if ! $SKIP_LLM; then
    _check_http "${LITELLM_BASE}/health/liveliness" "LiteLLM" || _warn "LiteLLM not reachable (LLM agents will fail)"
fi

# ── Phase 1: Seed DATA_DIR from demo-data/ ────────────────────────────────

_log "Phase 1: Seeding DATA_DIR from demo-data/"

# Copy demo data into DATA_DIR (preserving existing structure)
for subdir in people coaching feedback meetings decisions references okrs goals incidents postmortem-actions review-cycles status-reports; do
    src="$DEMO_DATA_DIR/$subdir"
    dst="$DATA_DIR/$subdir"
    if [ -d "$src" ] && [ "$(ls -A "$src" 2>/dev/null)" ]; then
        mkdir -p "$dst"
        cp -a "$src/"* "$dst/"
        count=$(find "$src" -maxdepth 1 -name '*.md' -o -name '*.json' | wc -l)
        _ok "Copied $count files to data/$subdir/"
    fi
done

# Copy operator.json to profiles/ if present
if [ -f "$DEMO_DATA_DIR/operator.json" ]; then
    mkdir -p "$PROFILES_DIR"
    cp "$DEMO_DATA_DIR/operator.json" "$PROFILES_DIR/operator.json"
    _ok "Copied operator.json to profiles/"
fi

# ── Phase 2: Ensure Qdrant collections ─────────────────────────────────────

_log "Phase 2: Ensuring Qdrant collections"

for coll in documents samples claude-memory profile-facts; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
        -X PUT "${QDRANT_URL}/collections/${coll}" \
        -H "Content-Type: application/json" \
        -d "{\"vectors\":{\"size\":${EMBED_DIMS},\"distance\":\"Cosine\"}}" \
        2>/dev/null || echo "000")

    case "$HTTP_CODE" in
        200) _ok "Created collection '$coll'" ;;
        409) _ok "Collection '$coll' exists" ;;
        *)   _warn "Failed to create '$coll' (HTTP $HTTP_CODE)" ;;
    esac
done

# ── Phase 2.5: Index project documentation ────────────────────────────────

_log "Phase 2.5: Indexing project documentation"
uv run python scripts/index-docs.py && _ok "Documentation indexed" || _warn "Documentation indexing failed (non-fatal)"

# ── Phase 3: Deterministic agents (parallel) ───────────────────────────────

_log "Phase 3: Running deterministic agents"

# These have no inter-dependencies and no LLM calls
pids=()

_run_agent agents.management_activity --json --days 30 &
pids+=($!)

_run_agent agents.introspect --save &
pids+=($!)

# Wait for all parallel agents
failed=0
for pid in "${pids[@]}"; do
    if ! wait "$pid"; then
        ((failed++))
    fi
done

if [ "$failed" -gt 0 ]; then
    _warn "$failed deterministic agent(s) failed (non-fatal)"
else
    _ok "All deterministic agents completed"
fi

# ── Phase 4: LLM synthesis agents (sequential) ────────────────────────────

if $SKIP_LLM; then
    _log "Phase 4: Skipped (--skip-llm)"
else
    _log "Phase 4: Running LLM synthesis agents"

    # Profiler first — indexes facts to Qdrant for downstream agents
    _run_agent agents.management_profiler --auto && _ok "Profiler completed" || _warn "Profiler failed"

    # Briefing — generates morning briefing from management state
    _run_agent agents.management_briefing --save && _ok "Briefing completed" || _warn "Briefing failed"

    # Digest — generates content digest from Qdrant documents
    _run_agent agents.digest --save --hours 720 && _ok "Digest completed" || _warn "Digest failed"

    # Team snapshot — generates overview of all teams
    _run_agent agents.management_prep --team-snapshot --save && _ok "Team snapshot completed" || _warn "Team snapshot failed"
fi

# ── Phase 5: Validate warm state ──────────────────────────────────────────

_log "Phase 5: Validating warm state"

# Check DATA_DIR has content
people_count=$(find "$DATA_DIR/people" -name '*.md' -type f 2>/dev/null | wc -l)
coaching_count=$(find "$DATA_DIR/coaching" -name '*.md' -type f 2>/dev/null | wc -l)
feedback_count=$(find "$DATA_DIR/feedback" -name '*.md' -type f 2>/dev/null | wc -l)

[ "$people_count" -gt 0 ] && _ok "$people_count people" || _warn "No people files"
[ "$coaching_count" -gt 0 ] && _ok "$coaching_count coaching records" || _warn "No coaching files"
[ "$feedback_count" -gt 0 ] && _ok "$feedback_count feedback records" || _warn "No feedback files"

# Check profiles/ for generated state
[ -f "$PROFILES_DIR/operator.json" ] && _ok "operator.json present" || _warn "No operator.json"

if ! $SKIP_LLM; then
    [ -f "$PROFILES_DIR/management-briefing.json" ] && _ok "Briefing generated" || _warn "No briefing"
fi

# Quick Qdrant check
for coll in documents profile-facts; do
    count=$(curl -sf "${QDRANT_URL}/collections/${coll}" 2>/dev/null \
        | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('points_count',0))" 2>/dev/null || echo "?")
    _ok "Qdrant '$coll': $count points"
done

# Check hapax-mgmt doc chunks in Qdrant (source filter)
doc_chunk_count=$(curl -sf -X POST "${QDRANT_URL}/collections/documents/points/count" \
    -H "Content-Type: application/json" \
    -d '{"filter":{"must":[{"key":"source","match":{"text":"hapax-mgmt"}}]},"exact":true}' 2>/dev/null \
    | python3 -c "import sys,json; print(json.load(sys.stdin).get('result',{}).get('count',0))" 2>/dev/null || echo "0")
if [ "$doc_chunk_count" -lt 50 ] 2>/dev/null; then
    _warn "Only $doc_chunk_count hapax-mgmt doc chunks indexed (expected >= 50). Run: uv run python scripts/index-docs.py"
else
    _ok "$doc_chunk_count hapax-mgmt doc chunks indexed"
fi

# ── Summary ────────────────────────────────────────────────────────────────

echo ""
_log "Bootstrap complete."
echo ""
echo "  Data:     $DATA_DIR"
echo "  Profiles: $PROFILES_DIR"
echo "  Qdrant:   $QDRANT_URL"
echo ""
if $SKIP_LLM; then
    echo "  Note: LLM agents were skipped. Run without --skip-llm for full hydration."
fi
echo "  Start the logos API:  uv run python -m logos.api --host 127.0.0.1 --port 8050"
echo "  The dashboard will show live management state at http://127.0.0.1:8052"
echo ""

# Exit non-zero if any _fail was called during bootstrap
if $HAVE_FAILURES; then
    exit 1
fi
