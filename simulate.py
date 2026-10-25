"""Propose file operations and show the guard's decisions. No files are opened."""

from guard import is_allowed


def main() -> None:
    requests = [
        {"action": "read", "path": "notes.txt"},
        {"action": "write", "path": "notes.txt"},
        {"action": "read", "path": "secrets.txt"},
        {"action": "delete", "path": "notes.txt"},
    ]

    print("Simulated requests only; no files will be accessed.\n")
    for request in requests:
        allowed = is_allowed(request)
        decision = "ALLOW" if allowed else "DENY"
        print(f"{decision}: {request['action']} {request['path']}")


if __name__ == "__main__":
    main()
