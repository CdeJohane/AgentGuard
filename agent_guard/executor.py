"""Guarded simulated execution with separate decision and execution fields."""

from .audit import record_decision
from .guard import check_request


class OperationError(Exception):
    """An expected read failure with a fixed, safe-to-display message."""

    def __init__(self):
        super().__init__("The permitted read failed.")


def simulated_read(path: str) -> str:
    """Return pretend file contents without opening a file."""
    return f"Simulated contents of {path}"


def execute_request(request: object) -> dict[str, bool | str]:
    """Return a dictionary containing decision, executed, and message.

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
        return {
            "decision": "allow",
            "executed": True,
            "message": msg,
        }
    return {
        "decision": "deny",
        "executed": False,
        "message": msg,
    }

