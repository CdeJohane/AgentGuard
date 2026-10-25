"""Propose file operations and show the guard's decisions. No files are opened."""

from .guard import check_request


def main() -> None:
    requests = [
        {"action": "read", "path": "notes.txt"},
        {"action": "write", "path": "notes.txt"},
        {"action": "read", "path": "secrets.txt"},
        {"action": "delete", "path": "notes.txt"},
        {},
        {"action": "read"},
        {"path": "notes.txt"},
        {"action": 123, "path": "notes.txt"},
        {"action": "read", "path": None},
        None,
        [],
    ]

    print("Simulated requests only; no files will be accessed.\n")
    for request in requests:
        try:
            allowed, reason = check_request(request)
        except (KeyError, TypeError) as error:
            # Show failures and continue so every sample can be inspected.
            print(f"ERROR ({type(error).__name__}): {request!r}")
            continue
        decision = "ALLOW" if allowed else "DENY"
        print(f"{decision}: {request!r} -- {reason}")


if __name__ == "__main__":
    main()
