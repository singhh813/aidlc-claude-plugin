"""
tests/test_gate_guard.py

Unit tests for hooks/aidlc-gate-guard.py.
Tests state sequence enforcement, fail-closed handling, and permission decisions.
"""

import io
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
            input=json.dumps(payload),
            capture_output=True,
            text=True,
        )
        self.assertEqual(proc.returncode, 0, f"Hook crashed: {proc.stderr}")
        return json.loads(proc.stdout)["hookSpecificOutput"]

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
        self.assertIn("no aidlc-docs", res["permissionDecisionReason"])

    def test_valid_next_stage_allowed(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w") as f:
            json.dump({"last_approved_stage": "00-scope", "enforcement": "on"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:01-requirements]\nDraft requirements"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_skipping_stages_denied(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w") as f:
            json.dump({"last_approved_stage": "00-scope", "enforcement": "on"}, f)

        # Skipping 01-requirements and 02-user-stories, jumping straight to 03-design
        payload = {"tool_input": {"prompt": "[STAGE:my-feat:03-design]\nWrite architecture"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "deny")
        self.assertIn("skips ahead", res["permissionDecisionReason"])

    def test_rerunning_current_stage_allowed(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w") as f:
            json.dump({"last_approved_stage": "01-requirements", "enforcement": "on"}, f)

        # Re-running 01-requirements (e.g. revision) is allowed
        payload = {"tool_input": {"prompt": "[STAGE:my-feat:01-requirements]\nUpdate requirements"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")

    def test_enforcement_off_allows_any_stage(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w") as f:
            json.dump({"last_approved_stage": "00-scope", "enforcement": "off"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:04-implementation-code]\nWrite code"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("enforcement is off", res["permissionDecisionReason"])

    def test_fast_track_mode_allows_skipping_inception(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w") as f:
            json.dump({"last_approved_stage": "00-scope", "mode": "fast-track", "enforcement": "on"}, f)

        # In fast-track mode, jumping from 00-scope directly to 04-implementation-code is allowed
        payload = {"tool_input": {"prompt": "[STAGE:my-feat:04-implementation-code]\nWrite code"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("permitted in fast-track", res["permissionDecisionReason"])

    def test_fast_track_from_requirements_allowed(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w") as f:
            json.dump({"last_approved_stage": "01-requirements", "mode": "fast-track", "enforcement": "on"}, f)

        payload = {
            "tool_input": {
                "subagent_type": "aidlc-implementer",
                "prompt": "[STAGE:my-feat:04-implementation-code]\nWrite code",
            }
        }
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("permitted in fast-track", res["permissionDecisionReason"])

    def test_low_risk_allows_skipping_inception(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w") as f:
            json.dump({"last_approved_stage": "00-scope", "risk": "low", "enforcement": "on"}, f)

        payload = {"tool_input": {"prompt": "[STAGE:my-feat:04-implementation-code]\nWrite code"}}
        res = self.run_hook(payload)
        self.assertEqual(res["permissionDecision"], "allow")
        self.assertIn("permitted in fast-track", res["permissionDecisionReason"])

    def test_human_reviewed_allows_arbitrary_stage(self):
        state_dir = Path("aidlc-docs") / "my-feat"
        state_dir.mkdir(parents=True, exist_ok=True)
        with open(state_dir / ".gate-state.json", "w") as f:
            json.dump({"last_approved_stage": "00-scope", "human_reviewed": True, "enforcement": "on"}, f)

        # Human reviewed override allows jumping to any valid stage (e.g. 05-test-results)
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


if __name__ == "__main__":
    unittest.main()

