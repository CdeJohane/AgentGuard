"""Learner-owned connection from completed model text to guarded execution."""

from .executor import execute_request
from .model_requests import parse_model_request


def execute_model_response(text: str) -> dict[str, bool | str]:
    """Decode a completed proposal and return the guarded executor's result.

    Keep the decoded value unchanged so the guard can reject malformed or
    forbidden proposals.
    """
    parsed = parse_model_request(text)
    return execute_request(parsed)
