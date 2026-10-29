"""Demonstrate guarded execution and auditing without accessing real files."""

from .audit import audit_log
from .executor import OperationError, execute_request


def display_result(request: object, executed: bool, message: str) -> None:
    """Display simulated contents on success or the reason for denial."""
    status = "EXECUTED" if executed else "DENIED"
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
        try:
            result = execute_request(request)
            display_result(request, result["executed"] is True, result["message"])
        except OperationError as error:
            print(f"FAILED: {request!r}")
            print(f"  {error}")

    display_audit_log()


if __name__ == "__main__":
    main()
