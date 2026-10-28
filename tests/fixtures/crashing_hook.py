"""Deliberately broken hook for a disposable crash experiment, never production.

Copy beside a probe-plan.json with scenario=intentional_crash before running.
The validated invocation is recorded before the intentional uncaught error.
No proposed command is executed by this script.
"""

import hashlib
import json
from pathlib import Path
import sys


def main() -> int:
    workspace = Path(__file__).resolve().parent
    try:
        plan = json.loads((workspace / "probe-plan.json").read_text(encoding="utf-8"))
        if not isinstance(plan, dict) or plan.get("scenario") != "intentional_crash":
            raise ValueError("Not an intentional crash workspace.")
        raw = sys.stdin.read(65_537)
        if len(raw) > 65_536:
            raise ValueError("Oversized event.")
        event = json.loads(raw)
        if not isinstance(event, dict) or not isinstance(event.get("cwd"), str) or not event["cwd"]:
            raise ValueError("Invalid hook event.")
        if (
            Path(event["cwd"]).resolve() != workspace
            or event.get("hook_event_name") != "PreToolUse"
            or event.get("tool_name") != "Bash"
        ):
            print("{}")
            return 0
        tool_input = event.get("tool_input")
        if not isinstance(tool_input, dict) or not isinstance(tool_input.get("command"), str):
            raise ValueError("Invalid shell input.")
        command = tool_input["command"]
        record = {
            "event": "PreToolUse", "tool": "Bash", "phase": "before_intentional_crash",
            "command_sha256": hashlib.sha256(command.encode("utf-8")).hexdigest(),
            "target_marker_mentioned": "crash-marker.txt" in command,
        }
        receipt = workspace / "crash-receipts.jsonl"
        if receipt.resolve() != workspace / "crash-receipts.jsonl":
            raise ValueError("Receipt path escaped workspace.")
        with receipt.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(record) + "\n")
    except Exception:
        print("AgentGuard crash probe setup or input was invalid; stop the experiment.", file=sys.stderr)
        return 2

    # Intentionally OUTSIDE the validation handler: process exit 1, no deny JSON.
    raise RuntimeError("AgentGuard intentional crash probe.")


if __name__ == "__main__":
    raise SystemExit(main())
