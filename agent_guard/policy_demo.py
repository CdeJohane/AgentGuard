"""Demonstrate offline policy decisions without actions or audit writes."""

from .policy import explain_decisions
from .project_policy import evaluate_project_request


def display_decision(label: str, decision: str, explanation: str) -> None:
    """Display a policy decision without claiming execution occurred."""
    print(f"{label}: {decision.upper()}")
    print(f"  {explanation}")


def main() -> None:
    """Evaluate and explain four requests using the fixed project policy."""
    cases = [
        ("Read notes.txt", {"action": "read", "path": "notes.txt"}),
        ("Read draft.txt", {"action": "read", "path": "draft.txt"}),
        ("Write notes.txt", {"action": "write", "path": "notes.txt"}),
        ("Malformed request", None),
    ]
    print("Policy decisions only; no actions will be executed.\n")
    for label, request in cases:
        # The explanation helper expects a list of layer records.
        result = evaluate_project_request(request)
        reason = explain_decisions([result])
        display_decision(label, reason[0], reason[1])


if __name__ == "__main__":
    main()
