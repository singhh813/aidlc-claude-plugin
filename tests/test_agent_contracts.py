"""
tests/test_agent_contracts.py

Automated contract and integrity tests for AIDLC agent markdown definitions,
tool permission bindings, template alignment, and skill schemas.
"""

import os
import re
import sys
import unittest
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


class TestAgentContracts(unittest.TestCase):
    def setUp(self):
        self.agents_dir = REPO_ROOT / "agents"
        self.agent_files = list(self.agents_dir.glob("*.md"))
        self.assertTrue(len(self.agent_files) > 0, "No agent markdown files found")

    def parse_frontmatter(self, file_path: Path) -> dict:
        content = file_path.read_text(encoding="utf-8")
        match = re.match(r"^---\s*\n(.*?)\n---\s*\n", content, re.DOTALL)
        self.assertIsNotNone(match, f"File {file_path.name} missing YAML frontmatter")
        fm_text = match.group(1)

        data = {}
        for line in fm_text.splitlines():
            line = line.strip()
            if not line or line.startswith("#") or line.startswith("-"):
                continue
            if ":" in line:
                key, val = line.split(":", 1)
                data[key.strip()] = val.strip()
        return data, content[match.end() :]

    def test_all_agents_have_required_frontmatter_fields(self):
        required_fields = {"name", "description", "tools", "model"}
        for agent_file in self.agent_files:
            data, _ = self.parse_frontmatter(agent_file)
            for field in required_fields:
                self.assertIn(
                    field,
                    data,
                    f"Agent {agent_file.name} missing required frontmatter field: '{field}'",
                )
            self.assertTrue(len(data["tools"]) > 0, f"Agent {agent_file.name} has empty tools list")

    def test_tools_alignment_with_prompt_instructions(self):
        for agent_file in self.agent_files:
            data, body = self.parse_frontmatter(agent_file)
            tools = [t.strip() for t in data["tools"].split(",")]

            # 1. If agent instructions run git commands or curl, Bash must be in tools
            if re.search(r"\b(git status|git fetch|git log|curl|gh pr)\b", body):
                self.assertIn(
                    "Bash",
                    tools,
                    f"Agent {agent_file.name} instructs running CLI commands (git/curl/gh) but lacks 'Bash' in tools",
                )

            # 2. If agent instructions write markdown files or scripts to disk, Write must be in tools
            if re.search(r"Write `aidlc-docs/", body) or re.search(r"author .*`verify\.sh`", body):
                self.assertIn(
                    "Write",
                    tools,
                    f"Agent {agent_file.name} instructs writing files to disk but lacks 'Write' in tools",
                )

    def test_operations_artifact_naming(self):
        ops_file = self.agents_dir / "aidlc-ops-planner.md"
        content = ops_file.read_text(encoding="utf-8")
        self.assertIn(
            "08-operations.md",
            content,
            "aidlc-ops-planner should write 08-operations.md to match stage ID 08-operations",
        )
        self.assertNotIn("06-operations.md", content, "aidlc-ops-planner still references 06-operations.md")

    def test_templates_exist_and_cover_required_sections(self):
        templates_dir = REPO_ROOT / "skills" / "aidlc" / "assets" / "templates"
        self.assertTrue(templates_dir.exists(), "Templates directory missing")

        scope_template = (templates_dir / "scope.md").read_text(encoding="utf-8")
        self.assertIn("**Risk:**", scope_template)
        self.assertIn("**Review Mode:**", scope_template)
        self.assertIn("API verification:", scope_template)

        plan_template = (templates_dir / "implementation-plan.md").read_text(encoding="utf-8")
        self.assertIn("## Database changes", plan_template)

    def test_all_agents_specify_status_output_contract(self):
        """Verifies that every agent enforces the STATUS: COMPLETED | BLOCKED | NEEDS_INPUT contract."""
        for agent_file in self.agent_files:
            content = agent_file.read_text(encoding="utf-8")
            self.assertIn(
                "STATUS: COMPLETED | BLOCKED | NEEDS_INPUT",
                content,
                f"Agent {agent_file.name} lacks required output protocol 'STATUS: COMPLETED | BLOCKED | NEEDS_INPUT'",
            )

    def test_all_agents_have_lifecycle_phase_metadata(self):
        """Verifies that all agents declare a recognized SDLC lifecycle phase."""
        valid_phases = {
            "intake",
            "scoping",
            "inception",
            "construction",
            "delivery",
            "verification",
            "operations",
            "governance",
        }
        for agent_file in self.agent_files:
            data, _ = self.parse_frontmatter(agent_file)
            self.assertIn(
                "phase",
                data,
                f"Agent {agent_file.name} missing 'phase' metadata field in frontmatter",
            )
            self.assertIn(
                data["phase"],
                valid_phases,
                f"Agent {agent_file.name} has unrecognized phase '{data.get('phase')}'",
            )

    def test_stage_producing_agents_contract_alignment(self):
        """Verifies that stage-producing agents declare valid stage IDs and reference [STAGE:...] tags."""
        sys.path.insert(0, str(REPO_ROOT / "hooks"))
        import importlib
        gate_guard = importlib.import_module("aidlc-gate-guard")

        for agent_name in gate_guard.STAGE_PRODUCING_AGENTS:
            agent_file = self.agents_dir / f"{agent_name}.md"
            self.assertTrue(agent_file.exists(), f"Stage-producing agent file {agent_file.name} missing")

            data, body = self.parse_frontmatter(agent_file)
            self.assertIn("stage_id", data, f"Agent {agent_name} missing 'stage_id' in frontmatter")
            self.assertIn(
                data["stage_id"],
                gate_guard.STAGES,
                f"Agent {agent_name} stage_id '{data.get('stage_id')}' not in STAGES list",
            )
            self.assertIn(
                "[STAGE:",
                body,
                f"Agent {agent_name} instructions missing required '[STAGE:' tag reference",
            )

    def test_modular_commands_exist_and_have_descriptions(self):
        """Verifies all required slash commands exist and declare frontmatter descriptions."""
        commands_dir = REPO_ROOT / "commands"
        expected_commands = [
            "aidlc.md",
            "scope.md",
            "design.md",
            "build.md",
            "review.md",
            "dev.md",
            "test.md",
        ]
        for cmd_file in expected_commands:
            target = commands_dir / cmd_file
            self.assertTrue(target.exists(), f"Command file {cmd_file} does not exist")
            content = target.read_text(encoding="utf-8")
            self.assertTrue(
                content.startswith("---") and "description:" in content,
                f"Command {cmd_file} missing description frontmatter",
            )


if __name__ == "__main__":
    unittest.main()

