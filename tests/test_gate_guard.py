"""
tests/test_gate_guard.py

Unit tests for hooks/aidlc-gate-guard.py.
Tests state sequence enforcement, fail-closed handling, agent normalization,
Unicode handling, CWD resolution, and permission decisions.
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path


class TestGateGuardHook(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.mkdtemp()
        self.old_cwd = os.getcwd()
        os.chdir(self.temp_dir)
        self.hook_script = Path(self.old_cwd) / "hooks" / "aidlc-gate-guard.py"

    def tearDown(self):
        os.chdir(self.old_cwd)
        shutil.rmtree(self.temp_dir, ignore_errors=True)

    def run_hook(self, payload: dict) -> dict:
        proc = subprocess.run(
            [sys.executable, str(self.hook_script)],
            input=json.dumps(payload, ensure_ascii=False),
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        self.assertEqual(proc.returncode, 0, f"Hook crashed with code {proc.returncode}: {proc.stderr}")
        try:
            return json.loads(proc.stdout)["hookSpecificOutput"]
        except Exception as e:
            self.fail(f"Failed to parse hook stdout as JSON: {proc.stdout} | stderr: {proc.stderr} | err: {e}")

    def test_non_gated_prompt_allowed(self):
        payload = {"tool_input": {"prompt": "Review this pull request"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("not a gated", res["permissionDecisionReason"])

    def test_stage_producing_agent_missing_tag_denied(self):
        payload = {
            "tool_input": {
                "subagent_type": "aidlc-implementer",
                "prompt": "Implement the order cancellation endpoint",
            }
        }
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("must begin with '[STAGE:", res["permissionDecisionReason"])

    def test_stage_producing_agent_normalized_casing_and_separators(self):
        """Verifies that casing or separator variations (aidlc_implementer, Aidlc-Implementer) don't bypass checks."""
        for variant in ["aidlc_implementer", "Aidlc-Implementer", "AIDLC_IMPLEMENTER", "aidlc implementer"]:
            payload = {
                "tool_input": {
                    "subagent_type": variant,
                    "prompt": "Implement code without a stage tag",
                }
            }
            res = self.run_hook(payload)
            self.assertEqual(
                res["permissionDecision"],
                "deny",
                f"Variant '{variant}' bypassed stage gate enforcement!",
            )

    def test_non_stage_agent_missing_tag_allowed(self):
        payload = {
            "tool_input": {
                "subagent_type": "aidlc-reviewer",
                "prompt": "Review this implementation",
            }
        }
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("not a gated", res["permissionDecisionReason"])

    def test_invalid_stage_name_denied(self):
        payload = {"tool_input": {"prompt": "[STAGE:my-feat:99-invalid-stage]\nDo something"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("not a recognized AIDLC stage id", res["permissionDecisionReason"])

    def test_first_stage_00_scope_allowed_without_state(self):
        payload = {"tool_input": {"prompt": "[STAGE:my-feat:00-scope]\nAssess scope"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("first stage", res["permissionDecisionReason"])

    def test_later_stage_denied_without_state(self):
        payload = {"tool_input": {"prompt": "[STAGE:my-feat:01-requirements]\nDraft requirements"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("no ", res["permissionDecisionReason"])
        self.assertIn(".gate-state.json found", res["permissionDecisionReason"])

    def test_valid_next_stage_allowed(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": "00-scope", "enforcement": "on"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:01-requirements]\nDraft requirements"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_skipping_stages_denied(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": "00-scope", "enforcement": "on"}, f)

        # Skipping 01-requirements and 02-user-stories, jumping straight to 03-design
        payload = {"tool_input": {"prompt": "[STAGE:my-feat:03-design]\nWrite architecture"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("skips ahead", res["permissionDecisionReason"])

    def test_rerunning_current_stage_allowed(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": "01-requirements", "enforcement": "on"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:01-requirements]\nUpdate requirements"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_rerunning_earlier_stage_allowed_with_rework_note(self):
        """Re-running an earlier stage for rework is permitted but notes state update."""
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": "04-implementation-code", "enforcement": "on"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:01-requirements]\nUpdate requirements"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("re-running prior stage", res["permissionDecisionReason"])

    def test_enforcement_off_allows_any_stage(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": "00-scope", "enforcement": "off"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:04-implementation-code]\nWrite code"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("enforcement is off", res["permissionDecisionReason"])

    def test_fast_track_mode_allows_skipping_inception(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": "00-scope", "mode": "fast-track", "enforcement": "on"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:04-implementation-code]\nWrite code"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("permitted in fast-track", res["permissionDecisionReason"])

    def test_fast_track_mode_cannot_skip_testing_to_pr(self):
        """Ensures fast-track changes cannot skip test-plan or test-results directly to pr-plan."""
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": "04-implementation-code", "mode": "fast-track", "enforcement": "on"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:06-pr-plan]\nCreate PR without testing"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("skips ahead", res["permissionDecisionReason"])

    def test_low_risk_case_insensitive_allows_skipping_inception(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": "00-scope", "risk": "Low", "enforcement": "on"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:04-implementation-code]\nWrite code"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("permitted in fast-track", res["permissionDecisionReason"])

    def test_human_reviewed_allows_arbitrary_stage(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": "00-scope", "human_reviewed": True, "enforcement": "on"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:05-test-results]\nTest results"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("human authority", res["permissionDecisionReason"])

    def test_standalone_tag_allows_stage_producing_agent_without_prior_state(self):
        payload = {
            "tool_input": {
                "subagent_type": "aidlc-implementer",
                "prompt": "[STANDALONE]\nRefactor the authentication middleware directly",
            }
        }
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("standalone mode", res["permissionDecisionReason"])

    def test_standalone_mode_with_subtag_allows_execution(self):
        payload = {
            "tool_input": {
                "subagent_type": "aidlc-tester",
                "prompt": "[STANDALONE:test]\nGenerate and run pytest fixtures for orders API",
            }
        }
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("standalone mode 'test'", res["permissionDecisionReason"])

    def test_path_traversal_slug_denied(self):
        payload = {
            "tool_input": {
                "subagent_type": "aidlc-implementer",
                "prompt": "[STAGE:../../etc:04-implementation-code]\nMalicious path traversal attempt",
            }
        }
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("must begin with '[STAGE:<feature-slug>:<stage-id>]'", res["permissionDecisionReason"])

    def test_payload_cwd_resolution(self):
        """Verifies hook resolves .gate-state.json using payload 'cwd' when process cwd is different."""
        alt_project_dir = Path(tempfile.mkdtemp())
        try:
            state_dir = alt_project_dir / "aidlc-docs" / "ext-feat"
            state_dir.mkdir(parents=True, exist_ok=True)
            with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
                json.dump({"last_approved_stage": "00-scope", "enforcement": "on"}, f)

            payload = {
                "cwd": str(alt_project_dir),
                "tool_input": {
                    "subagent_type": "aidlc-requirements-analyst",
                    "prompt": "[STAGE:ext-feat:01-requirements]\nDraft requirements",
                },
            }
            res = self.run_hook(payload)
            self.assertEqual(res["permissionDecision"], "allow")
        finally:
            shutil.rmtree(alt_project_dir, ignore_errors=True)

    def test_markdown_formatted_stage_tag_allowed(self):
        """Verifies bold, backticks, or whitespace formatting in tags are tolerated."""
        state_dir = Path("aidlc-docs") / "fmt-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": "00-scope", "enforcement": "on"}, f)

        test_prompts = [
            "**[STAGE:fmt-feat:01-requirements]**\nDraft requirements",
            "`[STAGE:fmt-feat:01-requirements]`\nDraft requirements",
            "[STAGE : fmt-feat : 01-requirements]\nDraft requirements",
            "# Section Header\n[STAGE:fmt-feat:01-requirements]\nDraft requirements",
        ]
        for prompt in test_prompts:
            payload = {"tool_input": {"prompt": prompt}}
            res = self.run_hook(payload)
            self.assertEqual(res["permissionDecision"], "allow", f"Failed to match prompt: {prompt}")

    def test_unicode_and_emojis_in_prompt_do_not_crash(self):
        """Ensures non-ASCII characters, emojis, and smart punctuation decode cleanly."""
        payload = {
            "tool_input": {
                "prompt": "[STAGE:emoji-feat:00-scope]\n🚀 Implement authentication — with smart quotes “test” and ✓ checkmark."
            }
        }
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_non_dict_state_file_handled_gracefully(self):
        """Ensures a malformed .gate-state.json containing a JSON list doesn't crash the hook."""
        state_dir = Path("aidlc-docs") / "corrupt-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            f.write("[]")

        payload = {"tool_input": {"prompt": "[STAGE:corrupt-feat:01-requirements]\nDo work"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("does not contain a JSON object", res["permissionDecisionReason"])

    def test_null_last_approved_stage_handled_gracefully(self):
        """Ensures a null/None last_approved_stage value doesn't crash the hook."""
        state_dir = Path("aidlc-docs") / "null-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w", encoding="utf-8") as f:
            json.dump({"last_approved_stage": None, "enforcement": "on"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:null-feat:01-requirements]\nDo work"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("no stage approved yet", res["permissionDecisionReason"])


if __name__ == "__main__":
    unittest.main()
