"""Disposable native-profile comparison, run from a normal Windows terminal.

No model calls or saved-policy edits. Copy beside a native_profile_comparison
probe-plan.json. Child commands can create only three fixed dummy marker files.
"""

import argparse
import hashlib
import json
from pathlib import Path
import subprocess
import sys


MARKER_CONTENT = "AGENTGUARD_NATIVE_PROFILE_PROBE\n"
MARKERS = ("direct-marker.txt", "workspace-marker.txt", "readonly-marker.txt")
STARTED = "AGENTGUARD_WRITE_STARTED"
WRITTEN = "AGENTGUARD_WRITE_SUCCEEDED"
DENIED = "AGENTGUARD_WRITE_DENIED"


def write_marker(workspace: Path, name: str) -> int:
    print(STARTED, flush=True)
    try:
        with (workspace / name).open("x", encoding="utf-8") as stream:
            stream.write(MARKER_CONTENT)
    except PermissionError:
        print(DENIED, file=sys.stderr)
        return 13
    except OSError:
        print("AGENTGUARD_OTHER_WRITE_ERROR", file=sys.stderr)
        return 14
    print(WRITTEN)
    return 0


def run_child(arguments: list[str], workspace: Path, marker: str) -> dict:
    try:
        result = subprocess.run(arguments, cwd=workspace, capture_output=True,
                                text=True, errors="replace", timeout=30)
        lines = (result.stdout + "\n" + result.stderr).splitlines()
        evidence = {
            "exit_code": result.returncode, "writer_started": STARTED in lines,
            "write_succeeded": WRITTEN in lines, "permission_denied": DENIED in lines,
            "timed_out": False,
            "restricted_token_87": any("CreateRestrictedToken failed: 87" in line for line in lines),
        }
    except (OSError, subprocess.TimeoutExpired) as error:
        evidence = {"exit_code": None, "writer_started": False, "write_succeeded": False,
                    "permission_denied": False, "timed_out": isinstance(error, subprocess.TimeoutExpired),
                    "launch_error_type": type(error).__name__}
    path = workspace / marker
    evidence["marker_exists"] = path.exists()
    try:
        # The worker writes text: accept the platform's normal newline encoding.
        evidence["marker_content_matches"] = path.is_file() and path.read_text(encoding="utf-8") == MARKER_CONTENT
    except OSError:
        evidence["marker_content_matches"] = False
    return evidence


def classify_outcome(results: dict) -> str:
    def succeeded(item):
        return (item["exit_code"] == 0 and item["writer_started"] and item["write_succeeded"]
                and item["marker_exists"] and item["marker_content_matches"] and not item["timed_out"])

    if not succeeded(results["direct"]) or not succeeded(results["workspace"]):
        return "inconclusive_controls_not_verified"
    readonly = results["readonly"]
    if (
        readonly["writer_started"] and readonly["permission_denied"]
        and readonly["exit_code"] not in (None, 0) and not readonly["marker_exists"]
        and not readonly["timed_out"]
    ):
        return "readonly_write_denied_observed"
    if succeeded(readonly):
        return "write_allowed_under_requested_readonly_profile"
    return "inconclusive_readonly_result"


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--worker", choices=MARKERS)
    parser.add_argument("--codex", type=Path)
    args = parser.parse_args(argv)
    workspace = Path(__file__).resolve().parent
    try:
        plan = json.loads((workspace / "probe-plan.json").read_text(encoding="utf-8"))
        if plan.get("scenario") != "native_profile_comparison":
            raise ValueError("Wrong fixture.")
        if hashlib.sha256(Path(__file__).read_bytes()).hexdigest() != plan["source_sha256"]:
            raise ValueError("Source differs from prepared fixture.")
    except Exception:
        print("AGENTGUARD_INVALID_NATIVE_PROBE_SETUP", file=sys.stderr)
        return 2
    if args.worker:
        return write_marker(workspace, args.worker)
    if args.codex is None or not args.codex.is_file():
        parser.error("--codex must name the installed executable")
    output = workspace / "native-verification.json"
    if output.exists() or any((workspace / name).exists() for name in MARKERS):
        print("Existing experiment artifacts found; use a fresh fixture.")
        return 2
    results = {}
    for key, profile, marker in zip(("direct", "workspace", "readonly"),
                                    (None, ":workspace", ":read-only"), MARKERS):
        print(f"Running {key} case...", flush=True)
        command = [sys.executable, "-I", "-B", str(Path(__file__).resolve()), "--worker", marker]
        if profile is not None:
            command = [str(args.codex), "sandbox", "--permission-profile", profile,
                       "--include-managed-config", "--cd", str(workspace)] + command
        results[key] = run_child(command, workspace, marker)
    evidence = {"status": classify_outcome(results), "probe_id": plan["probe_id"],
                "requested_profiles": [":workspace", ":read-only"],
                "managed_config_included": True, "source_sha256": plan["source_sha256"],
                "python_version": sys.version.split()[0], "results": results}
    output.write_text(json.dumps(evidence, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(evidence, indent=2))
    return 0 if evidence["status"] == "readonly_write_denied_observed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
