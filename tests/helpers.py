"""Disposable filesystem fixtures under the ignored workspace state directory."""

from contextlib import contextmanager
from pathlib import Path
import shutil
from uuid import uuid4


@contextmanager
def local_test_directory():
    """Create a fixture directory with inherited Windows filesystem permissions."""
    repository_root = Path(__file__).resolve().parents[1]
    base = repository_root / ".agent_guard" / "test-tmp"
    if not base.resolve().is_relative_to(repository_root):
        raise RuntimeError("Test fixtures must remain inside the repository.")
    base.mkdir(parents=True, exist_ok=True)
    directory = base / uuid4().hex
    directory.mkdir()
    try:
        yield directory
    finally:
        # Verify the resolved target before recursive cleanup, including on Windows.
        target = directory.resolve()
        if (
            directory.is_symlink()
            or target.parent != base.resolve()
            or not target.is_relative_to(repository_root)
        ):
            raise RuntimeError("Refusing to clean up a fixture outside its workspace directory.")
        shutil.rmtree(target)
