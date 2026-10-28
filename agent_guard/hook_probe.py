"""Experimental hook responder; not installed or connected to Codex yet.

Only shell calls in the explicitly selected probe workspace are in scope.
This module never executes the proposed command or opens its target files.
"""

import argparse
import hashlib
import json
from pathlib import Path
import sys


MAX_EVENT_CHARACTERS = 65_536
BLOCK_REASON = "AgentGuard probe: shell execution is blocked in this disposable project."


def make_block_decision() -> dict:
    """Return the learner-written, documented PreToolUse denial object."""
    return {
        "hookSpecificOutput":{
            "hookEventName":"PreToolUse",
            "permissionDecision":"deny",
            "permissionDecisionReason":BLOCK_REASON
        }
    }


def _validated_denial(value: object) -> dict:
    """Reject unsupported fields/decisions before they reach the hook runtime."""
    if not isinstance(value, dict) or set(value) != {"hookSpecificOutput"}:
        raise ValueError("Invalid hook output.")
    decision = value["hookSpecificOutput"]
    if (
        not isinstance(decision, dict)
        or set(decision) != {"hookEventName", "permissionDecision", "permissionDecisionReason"}
        or decision["hookEventName"] != "PreToolUse"
        or decision["permissionDecision"] != "deny"
        or decision["permissionDecisionReason"] != BLOCK_REASON
    ):
        raise ValueError("Invalid hook denial.")
    return value


def _record_probe_call(workspace: Path, receipt: Path, command: str) -> None:
    """Keep minimal invocation evidence only in the disposable workspace."""
    expected = workspace.resolve() / "hook-receipts.jsonl"
    if receipt.resolve() != expected:
        raise ValueError("Receipt must stay at the expected probe path.")
    record = {
        "event": "PreToolUse", "tool": "Bash", "decision": "deny",
        "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
        "target_marker_mentioned": "blocked-marker.txt" in command,
    }
    with receipt.open("a", encoding="utf-8") as stream:
        stream.write(json.dumps(record) + "\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", required=True, type=Path, help="Disposable probe workspace")
    parser.add_argument("--receipt", type=Path, help="Optional workspace/hook-receipts.jsonl evidence file")
    args = parser.parse_args(argv)
    try:
        raw = sys.stdin.read(MAX_EVENT_CHARACTERS + 1)
        if len(raw) > MAX_EVENT_CHARACTERS:
            raise ValueError("Oversized hook input.")
        event = json.loads(raw)
        if not isinstance(event, dict) or not isinstance(event.get("cwd"), str) or not event["cwd"]:
            raise ValueError("Invalid hook event.")
        if (
            Path(event["cwd"]).resolve() != args.workspace.resolve()
            or event.get("hook_event_name") != "PreToolUse"
            or event.get("tool_name") != "Bash"
        ):
            # No explicit approval: leave unrelated work to its existing policy.
            print("{}")
            return 0
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
            raise ValueError("Invalid shell input.")
        response = _validated_denial(make_block_decision())
        if args.receipt is not None:
            _record_probe_call(args.workspace, args.receipt, tool_input["command"])
        print(json.dumps(response))
        return 0
    except Exception:
        # The documented PreToolUse exit code 2 blocks the call. Never print
        # exception text, raw input, commands, or credentials to either stream.
        print("AgentGuard probe could not validate this request; execution is blocked.", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
