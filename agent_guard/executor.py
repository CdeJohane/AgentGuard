"""Guarded simulated execution with separate decision and execution fields."""

from .audit import record_decision
from .guard import check_request
from .policy import explain_decisions
from .project_policy import evaluate_project_request


class OperationError(Exception):
    """An expected read failure with a fixed, safe-to-display message."""

    def __init__(self):
        super().__init__("The permitted read failed.")


def simulated_read(path: str) -> str:
    """Return pretend file contents without opening a file."""
    return f"Simulated contents of {path}"


def _allows_execution(decision: object) -> bool:
    """Only the exact allow decision may execute."""
    return True if decision == "allow" else False


def execute_request(
    request: object, *, use_project_policy: bool = False,
) -> dict[str, bool | str]:
    """Return a dictionary containing decision, executed, and message.

    The keyword selects project policy in trusted calling code, not model input.
    Default callers retain the original guard. Review and deny never reach
    the simulated reader.
    Record permission once before running an allowed operation.
    Raise OperationError with a safe message if the permitted reader fails.
    """
    if use_project_policy:
        layer_record = evaluate_project_request(request)
        decision, msg = explain_decisions([layer_record])
        allowed = _allows_execution(decision)
    else:
        allowed, msg = check_request(request)
        decision = "allow" if allowed is True else "deny"
    record_decision(request, allowed is True, msg)
    if allowed is True:
        try:
            msg = simulated_read(request["path"])
        except OSError:
            raise OperationError() from None  # Hide the original exception context.
        return {
            "decision": decision,
            "executed": True,
            "message": msg,
        }
    return {
        "decision": decision,
        "executed": False,
        "message": msg,
    }

