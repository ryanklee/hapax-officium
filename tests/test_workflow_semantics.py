# ai-agents/tests/test_workflow_semantics.py
"""Validate workflow-semantics.yaml against demo-data/ corpus."""

from __future__ import annotations

from pathlib import Path

import yaml

_PROJECT_ROOT = Path(__file__).resolve().parent.parent
_WORKFLOW_SEMANTICS = _PROJECT_ROOT / "docs" / "workflow-semantics.yaml"
_DEMO_DATA = Path(__file__).resolve().parent.parent / "demo-data"


class TestWorkflowSemanticsConsistency:
    def test_semantics_file_exists(self):
        """workflow-semantics.yaml exists."""
        assert _WORKFLOW_SEMANTICS.is_file(), f"Missing {_WORKFLOW_SEMANTICS}"

    def test_all_demo_data_types_have_semantics(self):
        """Every document type in demo-data/ has a workflow-semantics entry."""
        semantics = yaml.safe_load(_WORKFLOW_SEMANTICS.read_text())
        defined_subdirs = {w["subdirectory"].rstrip("/") for w in semantics["workflows"].values()}

        # Subdirectories in demo-data that contain .md files with type: frontmatter
        data_subdirs = set()
        for md_file in _DEMO_DATA.rglob("*.md"):
            rel = md_file.relative_to(_DEMO_DATA)
            if len(rel.parts) >= 2:
                data_subdirs.add(rel.parts[0])

        # Exclude non-workflow directories
        non_workflow = {
            "people",
            "references",
            "1on1-prep",
            "inbox",
            "processed",
            "briefings",
            "status-updates",
            "review-prep",
        }
        data_subdirs -= non_workflow

        missing = data_subdirs - defined_subdirs
        assert not missing, (
            f"demo-data/ has document types not in workflow-semantics.yaml: {missing}"
        )

    def test_all_semantics_have_demo_data(self):
        """Every workflow-semantics entry has at least one example in demo-data/."""
        semantics = yaml.safe_load(_WORKFLOW_SEMANTICS.read_text())

        for name, workflow in semantics["workflows"].items():
            subdir = workflow["subdirectory"].rstrip("/")
            demo_dir = _DEMO_DATA / subdir
            md_files = list(demo_dir.glob("*.md")) if demo_dir.is_dir() else []
            assert len(md_files) > 0, (
                f"Workflow '{name}' (subdirectory: {subdir}) has no demo-data examples"
            )

    def test_role_matrix_exists(self):
        """role-matrix.yaml exists."""
        role_matrix = Path(__file__).resolve().parent.parent / "config" / "role-matrix.yaml"
        assert role_matrix.is_file()

    def test_role_matrix_workflows_match_semantics(self):
        """All workflows referenced in role-matrix.yaml exist in workflow-semantics.yaml."""
        semantics = yaml.safe_load(_WORKFLOW_SEMANTICS.read_text())
        role_matrix = yaml.safe_load(
            (Path(__file__).resolve().parent.parent / "config" / "role-matrix.yaml").read_text()
        )

        defined_workflows = set(semantics["workflows"].keys())

        for role_name, role_def in role_matrix["roles"].items():
            for wf in role_def.get("workflows", []):
                assert wf in defined_workflows, (
                    f"Role '{role_name}' references undefined workflow '{wf}'"
                )
