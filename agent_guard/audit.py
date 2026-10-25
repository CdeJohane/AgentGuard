"""In-memory permission decisions. Records last only for this Python process."""

audit_log: list[dict] = []


def record_decision(request: object, allowed: bool, reason: str) -> None:
    """Append one new dictionary to audit_log, without returning a value.

    Your exercise:
    - Include exactly action, path, allowed, and reason in the record.
    - For action and path, keep string values; use None for missing or invalid
      values. A non-dictionary request has neither field.
    - Build a fresh dictionary instead of appending the request itself.
    - Append it to audit_log; do not replace the list or keep extra request keys.
    """
    
    record = {
        "action": request["action"] if isinstance(request, dict) and "action" in request and isinstance(request["action"], str) else None,
        "path": request["path"] if isinstance(request, dict) and "path" in request and isinstance(request["path"], str) else None,
        "allowed": allowed,
        "reason": reason
    }
    audit_log.append(record)
