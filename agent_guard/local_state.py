"""Local non-secret installation metadata. Do not store login tokens here."""

import json
from pathlib import Path
from uuid import UUID, uuid4


def load_or_create_host_id(path: Path = Path(".agent_guard/host.json")) -> str:
    """Return the saved UUIDv4 URN, or generate and save one on first use.

    Invalid saved data raises ValueError without rewriting the file.
    """

    # First use: generate an ID and save it once.
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        host_id = uuid4().urn
        with path.open("x", encoding="utf-8") as file:
            json.dump({"host_id": host_id}, file)
        return host_id

    # Existing file: read it without changing its contents.
    # Invalid JSON already raises JSONDecodeError, a subclass of ValueError.
    with path.open("r", encoding="utf-8") as file:
        data = json.load(file)

    # Validate the saved structure before parsing the host ID.
    if not isinstance(data, dict) or not isinstance(data.get("host_id"), str):
        raise ValueError("Saved host metadata must contain a string host_id.")
    else:
        my_uuid = UUID(data["host_id"])
        if my_uuid.version == 4 and my_uuid.urn == data["host_id"]:
            return data["host_id"]
        else:
            raise ValueError("Saved host ID must be a canonical UUIDv4 URN.")
