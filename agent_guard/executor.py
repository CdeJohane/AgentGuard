"""A guarded execution exercise. No real files are accessed."""

from .audit import record_decision
from .guard import check_request


def simulated_read(path: str) -> str:
    """Return pretend file contents without opening a file."""
    return f"Simulated contents of {path}"


def execute_request(request: object) -> tuple[bool, str]:
    """Return (True, contents) on success or (False, reason) on denial.

    Record the guard's permission decision before running an allowed operation.
    Denied requests never reach the simulated reader.
    """
    decision, msg = check_request(request)
    record_decision(request, decision, msg)
    if decision is True:
        msg = simulated_read(request["path"])
    return decision, msg

