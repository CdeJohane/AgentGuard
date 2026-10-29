"""Fixed project rules for simulated requests; not connected to execution."""

from agent_guard.guard import is_valid_request


def evaluate_project_request(request: object) -> dict[str, str]:
    """Produce a project-layer record without reading or changing files.

    Paths are exact simulated labels, not resolved filesystem paths.
    """
    result = {
        "layer": "project",
        "decision": "deny",
        "reason": "Malformed request.",
    }
    if not is_valid_request(request):
        return result
    if not request["action"].strip() or not request["path"].strip():
        return result

    # Check the action before the path; reasons come from policy, not the request.
    if request["action"] != "read":
        result["decision"] = "deny"
        result["reason"] = "Action is not permitted."
    elif request["action"] == "read" and request["path"] == "notes.txt":
        result["decision"] = "allow"
        result["reason"] = "Reading notes.txt is permitted."
    else:
        result["decision"] = "review"
        result["reason"] = "File requires review."
    return result
