"""Decode proposed model requests before passing them to the guarded executor."""

import json


def parse_model_request(text: str) -> object:
    """Decode JSON text, returning None if the JSON decoder rejects it.

    Your exercise:
    - Use json.loads() to convert the text to a Python value.
    - Catch json.JSONDecodeError and return None for invalid JSON.
    - Return valid JSON values as decoded, including lists, strings, and null.
      The existing guard decides whether their structure and action are allowed.
    - Do not repair prose or Markdown fences, or execute the text as Python.
    """
    try:
        return (json.loads(text))
    except json.JSONDecodeError:
        return None
