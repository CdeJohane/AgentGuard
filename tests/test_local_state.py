"""Host-ID exercise: python -m unittest tests.test_local_state -v"""

import json
from pathlib import Path
import unittest
from uuid import UUID, uuid4

from agent_guard.local_state import load_or_create_host_id
from tests.helpers import local_test_directory


class HostIdTests(unittest.TestCase):
    def test_creates_parent_directory_and_uuid_host_metadata(self):
        with local_test_directory() as directory:
            path = Path(directory) / "local-state" / "host.json"
            host_id = load_or_create_host_id(path)
            parsed = UUID(host_id)
            self.assertEqual(parsed.version, 4)
            self.assertEqual(host_id, parsed.urn)
            self.assertEqual(json.loads(path.read_text(encoding="utf-8")), {"host_id": host_id})
            self.assertEqual(load_or_create_host_id(path), host_id)

    def test_reuses_existing_metadata_without_rewriting_it(self):
        with local_test_directory() as directory:
            path = Path(directory) / "host.json"
            host_id = uuid4().urn
            original = '{\n  "host_id": "' + host_id + '"\n}\n'
            path.write_text(original, encoding="utf-8")
            self.assertEqual(load_or_create_host_id(path), host_id)
            self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_invalid_saved_data_is_rejected_without_overwriting(self):
        cases = [
            "not JSON", "{}", "[]", '{"host_id": null}',
            '{"host_id": "not-a-uuid"}',
            '{"host_id": "urn:uuid:00000000-0000-0000-0000-000000000000"}',
        ]
        with local_test_directory() as directory:
            path = Path(directory) / "host.json"
            for original in cases:
                path.write_text(original, encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_or_create_host_id(path)
                self.assertEqual(path.read_text(encoding="utf-8"), original)

    def test_a_directory_at_the_file_path_is_not_replaced(self):
        with local_test_directory() as directory:
            path = Path(directory) / "host.json"
            path.mkdir()
            with self.assertRaises(OSError):
                load_or_create_host_id(path)
            self.assertTrue(path.is_dir())


if __name__ == "__main__":
    unittest.main()
