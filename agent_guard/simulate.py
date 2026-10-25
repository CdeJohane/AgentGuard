"""Demonstrate guarded execution and auditing without accessing real files."""

from .audit import audit_log
from .executor import execute_request


def display_result(request: object, allowed: bool, message: str) -> None:
    """Display simulated contents on success or the reason for denial."""
    status = "EXECUTED" if allowed else "DENIED"
    print(f"{status}: {request!r}")
    print(f"  {message}")


def display_audit_log() -> None:
    """Display permission records separately from execution output."""
    print("\nAudit trail:")
    for record in audit_log:
        print(f"  {record!r}")


def main() -> None:
    requests = [
        {"action": "read", "path": "notes.txt"},
        {"action": "write", "path": "notes.txt"},
        {"action": "read", "path": "secrets.txt"},
        None,
    ]

    audit_log.clear()
    print("Simulated requests only; no files will be accessed.\n")
    for request in requests:
        decision, msg = execute_request(request)
        display_result(request, decision, msg)

    display_audit_log()


if __name__ == "__main__":
    main()
