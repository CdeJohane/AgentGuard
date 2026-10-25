"""A guarded execution exercise. No real files are accessed."""

from .guard import check_request


def simulated_read(path: str) -> str:
    """Return pretend file contents without opening a file."""
    return f"Simulated contents of {path}"


def execute_request(request: object) -> tuple[bool, str]:
    """Return (True, contents) on success or (False, reason) on denial.

    Your exercise:
    1. Call check_request() and unpack its decision and reason.
    2. If denied, return the denial and reason before accessing request keys.
    3. If allowed, call simulated_read() with the requested path exactly once.
    4. Return success and the contents produced by that reader.
    """
    decision, msg = check_request(request)
    if decision is True:
        msg = simulated_read(request["path"])
    return decision, msg

