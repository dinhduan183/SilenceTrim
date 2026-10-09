import json
from pathlib import Path
import sys
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from silencetrim.updates import newer_tag


class UpdateTests(unittest.TestCase):
    def release(self, tag, **fields):
        return json.dumps(dict(tag_name=tag, draft=False, prerelease=False, **fields)).encode()

    def test_numeric_version_comparison(self):
        for tag, expected in [("v2.3", "v2.3"), ("v2.10", "v2.10"), ("2.2.1", "v2.2.1"),
                              ("v3.0", "v3.0"), ("v2.2", None), ("v2.2.0", None), ("v2.1", None)]:
            with self.subTest(tag=tag):
                self.assertEqual(newer_tag(self.release(tag), current="2.2"), expected)

    def test_unpublished_prerelease_and_invalid_responses(self):
        for fields in [{"draft": True}, {"prerelease": True}]:
            payload = dict(tag_name="v3.0", draft=False, prerelease=False)
            payload.update(fields)
            self.assertIsNone(newer_tag(json.dumps(payload)))
        for tag in ["v2.3-beta", "v2..3", "release-3", "", None, 3]:
            self.assertIsNone(newer_tag(self.release(tag)))
        for data in [b"", b"not json", b"\xff", b"[]", b"null", b'{"message":"rate limited"}', b'{"tag_name":"v3.0"}']:
            self.assertIsNone(newer_tag(data))


if __name__ == "__main__":
    unittest.main()
