"""Evidence classification checks; native sandbox itself is tested manually."""

import hashlib
import json
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch

from tests.fixtures.native_boundary_probe import MARKER_CONTENT, classify_outcome, run_child
from tests.helpers import local_test_directory


def successful_write():
    return {"exit_code": 0, "writer_started": True, "write_succeeded": True,
            "permission_denied": False, "marker_exists": True,
            "marker_content_matches": True, "timed_out": False}


def denied_write():
    return {"exit_code": 13, "writer_started": True, "write_succeeded": False,
            "permission_denied": True, "marker_exists": False,
            "marker_content_matches": False, "timed_out": False}


class NativeBoundaryEvidenceTests(unittest.TestCase):
    def test_text_verification_accepts_windows_newlines_and_rejects_wrong_contents(self):
        with local_test_directory() as workspace:
            marker = workspace / "direct-marker.txt"
            marker.write_bytes(MARKER_CONTENT.replace("\n", "\r\n").encode("utf-8"))
            completed = subprocess.CompletedProcess(
                ["fixture"], 0, "AGENTGUARD_WRITE_STARTED\nAGENTGUARD_WRITE_SUCCEEDED\n", "",
            )
            with patch("tests.fixtures.native_boundary_probe.subprocess.run", return_value=completed):
                self.assertTrue(run_child(["fixture"], workspace, marker.name)["marker_content_matches"])
                marker.write_bytes(b"incorrect contents\r\n")
                self.assertFalse(run_child(["fixture"], workspace, marker.name)["marker_content_matches"])

    def test_startup_error_or_missing_writer_cannot_count_as_write_denial(self):
        for changes in ({"writer_started": False}, {"exit_code": None}, {"timed_out": True},
                        {"permission_denied": False}, {"marker_exists": True}):
            results = {"direct": successful_write(), "workspace": successful_write(),
                       "readonly": {**denied_write(), **changes}}
            with self.subTest(changes=changes):
                self.assertEqual(classify_outcome(results), "inconclusive_readonly_result")

    def test_both_successful_controls_are_required_for_a_denial_claim(self):
        for key in ("direct", "workspace"):
            results = {"direct": successful_write(), "workspace": successful_write(), "readonly": denied_write()}
            results[key]["marker_content_matches"] = False
            with self.subTest(key=key):
                self.assertEqual(classify_outcome(results), "inconclusive_controls_not_verified")

    def test_measured_denial_is_distinguished_from_a_write_under_requested_readonly(self):
        results = {"direct": successful_write(), "workspace": successful_write(), "readonly": denied_write()}
        self.assertEqual(classify_outcome(results), "readonly_write_denied_observed")
        results["readonly"] = successful_write()
        self.assertEqual(classify_outcome(results), "write_allowed_under_requested_readonly_profile")

    def test_real_worker_creates_only_its_fixed_dummy_target_in_a_disposable_fixture(self):
        with local_test_directory() as workspace:
            script = workspace / "native_boundary_probe.py"
            source = Path(__file__).parent / "fixtures/native_boundary_probe.py"
            script.write_bytes(source.read_bytes())
            plan = {"scenario": "native_profile_comparison", "source_sha256": hashlib.sha256(script.read_bytes()).hexdigest()}
            (workspace / "probe-plan.json").write_text(json.dumps(plan), encoding="utf-8")
            result = subprocess.run([sys.executable, "-I", "-B", str(script), "--worker", "direct-marker.txt"],
                                    cwd=workspace, capture_output=True, text=True)
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertEqual((workspace / "direct-marker.txt").read_text(encoding="utf-8"), MARKER_CONTENT)
            rejected = subprocess.run([sys.executable, "-I", "-B", str(script), "--worker", "../outside.txt"],
                                      cwd=workspace, capture_output=True, text=True)
            self.assertEqual(rejected.returncode, 2)
            self.assertEqual(set(path.name for path in workspace.iterdir()),
                             {"native_boundary_probe.py", "probe-plan.json", "direct-marker.txt"})
