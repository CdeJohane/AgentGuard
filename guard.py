"""Permission rules for simulated agent requests."""


def is_allowed(request: dict) -> bool:
    """Allow only reading notes.txt; deny every other action/path pair.

    For this exercise, requests contain string values for 'action' and 'path'.
    Paths are compared as exact strings, without touching the filesystem.
    """
    # Your part: replace this default denial with the agreed permission rule.
    return False
