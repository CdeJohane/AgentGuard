"""A guarded execution exercise. No real files are accessed."""

from .audit import record_decision
from .guard import check_request


class OperationError(Exception):
    """An expected read failure with a fixed, safe-to-display message."""

    def __init__(self):
        super().__init__("The permitted read failed.")


def simulated_read(path: str) -> str:
    """Return pretend file contents without opening a file."""
    return f"Simulated contents of {path}"


def execute_request(request: object) -> tuple[bool, str]:
    """Return (True, contents) on success or (False, reason) on denial.

    Record the guard's permission decision before running an allowed operation.
    Denied requests never reach the simulated reader.
    Raise OperationError with a safe message if the permitted reader fails.
    """
    decision, msg = check_request(request)
    record_decision(request, decision, msg)
    if decision is True:
        try:
            msg = simulated_read(request["path"])
        except OSError:
            raise OperationError() from None  # Hide the original exception context.
    return decision, msg

