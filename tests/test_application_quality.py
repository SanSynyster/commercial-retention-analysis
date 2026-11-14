from __future__ import annotations

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest import mock

from streamlit.testing.v1 import AppTest

ROOT = Path(__file__).resolve().parents[1]


class ApplicationQualityTests(unittest.TestCase):
    def test_targeting_page_renders_historical_workflow_and_capacity_interaction(self) -> None:
        app = AppTest.from_file(str(ROOT / "tests/targeting_explorer_page_app.py"), default_timeout=60).run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertEqual(app.title[0].value, "CRM Targeting Explorer")
        self.assertTrue(any("Retrospective targeting" in x.value for x in app.caption))
        self.assertTrue(any("not randomised treatment response" in x.value for x in app.warning))
        self.assertTrue(any(x.proto.page == "segmentation-intelligence" for x in app.page_link))
        self.assertTrue(any(x.label == "Evaluated contact capacity" for x in app.radio))
        app.radio(key="targeting_capacity").set_value("20%").run()
        self.assertFalse(app.exception, [e.value for e in app.exception])
        self.assertTrue(any("Policy comparison at 20% capacity" == x.value for x in app.subheader))

    def test_segmentation_and_causal_bundle_override_failure_states(self) -> None:
        cases = (
            ("P3_SEGMENTATION_BUNDLE", "tests/segmentation_intelligence_page_app.py", "app_data/p3_segmentation_v1.json", "segmentation"),
            ("P3_CAUSAL_BUNDLE", "tests/causal_evidence_page_app.py", "app_data/p3_causal_v1.json", "causal"),
        )
        for env_name, harness, committed, page_name in cases:
            original = json.loads((ROOT / committed).read_text(encoding="utf-8"))
            valid_temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
            json.dump(original, valid_temp)
            valid_temp.close()
            invalid_temp = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
            invalid_temp.write("{")
            invalid_temp.close()
            mismatch = dict(original)
            mismatch["content_sha256"] = "0" * 64
            mismatch_path = self._write_json(mismatch)
            unsupported = dict(original)
            unsupported["schema_version"] = 999
            unsupported_path = self._write_json(unsupported)
            unreadable_path = self._write_json(original)
            previous = os.environ.get(env_name)
            try:
                os.environ[env_name] = valid_temp.name
                valid = AppTest.from_file(str(ROOT / harness), default_timeout=60).run()
                self.assertFalse(valid.exception, [e.value for e in valid.exception])
                self.assertEqual(len(valid.error), 0)
                self.assertEqual(valid.title[0].value, "Segmentation Intelligence" if page_name == "segmentation" else "Causal Evidence & Experimentation")
                for path in (ROOT / "app_data/absent-quality-bundle.json", Path(invalid_temp.name), mismatch_path, unsupported_path):
                    with self.subTest(page=page_name, path=path.name):
                        os.environ[env_name] = str(path)
                        failed = AppTest.from_file(str(ROOT / harness), default_timeout=60).run()
                        self.assertFalse(failed.exception, [e.value for e in failed.exception])
                        self.assertEqual(len(failed.error), 1)
                        self.assertIn("could not be loaded", failed.error[0].value)
                        self.assertEqual(len(failed.metric), 0)
                if page_name == "segmentation":
                    real_read_text = Path.read_text

                    def selective_permission_error(path: Path, *args, **kwargs):
                        if path == unreadable_path:
                            raise PermissionError("permission denied for test bundle")
                        return real_read_text(path, *args, **kwargs)

                    os.environ[env_name] = str(unreadable_path)
                    with mock.patch.object(Path, "read_text", new=selective_permission_error):
                        unreadable = AppTest.from_file(str(ROOT / harness), default_timeout=60).run()
                    self.assertFalse(unreadable.exception, [e.value for e in unreadable.exception])
                    self.assertEqual(len(unreadable.error), 1)
                    self.assertIn("could not be loaded", unreadable.error[0].value)
                    self.assertEqual(len(unreadable.metric), 0)
            finally:
                if previous is None:
                    os.environ.pop(env_name, None)
                else:
                    os.environ[env_name] = previous
                for path in (Path(valid_temp.name), Path(invalid_temp.name), mismatch_path, unsupported_path, unreadable_path):
                    path.unlink(missing_ok=True)

    @staticmethod
    def _write_json(value: dict) -> Path:
        handle = tempfile.NamedTemporaryFile("w", suffix=".json", delete=False, encoding="utf-8")
        json.dump(value, handle)
        handle.close()
        return Path(handle.name)


if __name__ == "__main__":
    unittest.main()
