"""Permission rules for simulated agent requests."""


def is_allowed(request: object) -> bool:
    """Return only the boolean part of the permission decision."""
    allowed, _ = check_request(request)
    return allowed


def check_request(request: object) -> tuple[bool, str]:
    """Return a permission decision and a human-readable reason.

    Check structure, then action, then path, then allow.
    """
    if not is_valid_request(request):
        return (False, "Malformed request.")
    elif request["action"] != "read":
        return (False, "Action is not permitted.")
    elif request["path"] != "notes.txt":
        return (False, "File is not permitted.")
    else:
        return (True, "Reading notes.txt is permitted.")

def is_valid_request(request: object) -> bool:
    # Check the container, required keys, and value types in that order.
    if isinstance(request, dict):
        if "action" in request and "path" in request:
            if isinstance(request["action"], str) and isinstance(request["path"], str):
                return True
    return False
