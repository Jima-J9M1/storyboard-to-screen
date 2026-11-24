import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import paths
from core.cache import Cache
from core.runlog import input_hash, logged_call


class TempRepoTestCase(unittest.TestCase):
    """Redirects the repo paths to a temporary folder so tests never touch real logs."""

    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        for name, value in {
            "ROOT": self.root,
            "RUNS_PATH": self.root / "runs.jsonl",
            "CACHE_DIR": self.root / "cache",
        }.items():
            patcher = mock.patch.object(paths, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def log_lines(self) -> list[dict]:
        return [json.loads(line) for line in paths.RUNS_PATH.read_text().splitlines()]


class LoggedCallTests(TempRepoTestCase):
    CALL = dict(stage="test", model="fake-model", params={"steps": 4}, key="abc", seed=7, base_delay_s=0)

    def test_success_writes_one_complete_line(self):
        self.assertEqual(logged_call(lambda: "done", cost_usd=0.01, **self.CALL), "done")
        (line,) = self.log_lines()
        for field in ("ts", "stage", "model", "params", "seed", "latency_s", "cost_usd", "status"):
            self.assertIn(field, line)
        self.assertEqual((line["status"], line["seed"], line["cost_usd"]), ("ok", 7, 0.01))

    def test_failures_are_retried_and_every_attempt_is_logged(self):
        calls = {"n": 0}

        def flaky():
            calls["n"] += 1
            if calls["n"] < 3:
                raise TimeoutError("simulated timeout")
            return "done"

        self.assertEqual(logged_call(flaky, **self.CALL), "done")
        self.assertEqual([(l["attempt"], l["status"]) for l in self.log_lines()],
                         [(1, "error"), (2, "error"), (3, "ok")])
        self.assertIn("TimeoutError", self.log_lines()[0]["error"])

    def test_gives_up_after_three_attempts(self):
        def broken():
            raise ConnectionError("down")

        with self.assertRaises(RuntimeError):
            logged_call(broken, **self.CALL)
        self.assertEqual(len(self.log_lines()), 3)


class InputHashTests(unittest.TestCase):
    def test_same_inputs_same_hash_regardless_of_key_order(self):
        self.assertEqual(input_hash({"a": 1, "b": 2}), input_hash({"b": 2, "a": 1}))

    def test_changed_input_changes_hash(self):
        self.assertNotEqual(input_hash("prompt", 1), input_hash("prompt", 2))


class CacheTests(TempRepoTestCase):
    def setUp(self):
        super().setUp()
        self.output = self.root / "outputs" / "s01.png"
        self.output.parent.mkdir(parents=True)
        self.output.write_bytes(b"image")

    def test_unknown_item_is_not_fresh(self):
        self.assertFalse(Cache("keyframes").fresh("s01", "hash1"))

    def test_stored_item_is_fresh_in_a_later_run(self):
        Cache("keyframes").store("s01", "hash1", [self.output])
        self.assertTrue(Cache("keyframes").fresh("s01", "hash1"))

    def test_changed_inputs_are_not_fresh(self):
        Cache("keyframes").store("s01", "hash1", [self.output])
        self.assertFalse(Cache("keyframes").fresh("s01", "hash2"))

    def test_changing_one_item_leaves_the_others_fresh(self):
        other = self.root / "outputs" / "s02.png"
        other.write_bytes(b"image")
        cache = Cache("keyframes")
        cache.store("s01", "hash1", [self.output])
        cache.store("s02", "hash1", [other])
        self.assertFalse(Cache("keyframes").fresh("s01", "edited"))
        self.assertTrue(Cache("keyframes").fresh("s02", "hash1"))

    def test_deleted_output_is_not_fresh(self):
        Cache("keyframes").store("s01", "hash1", [self.output])
        self.output.unlink()
        self.assertFalse(Cache("keyframes").fresh("s01", "hash1"))

    def test_manifest_stores_paths_relative_to_the_repo(self):
        Cache("keyframes").store("s01", "hash1", [self.output])
        manifest = json.loads((paths.CACHE_DIR / "keyframes.json").read_text())
        self.assertEqual(manifest["s01"]["outputs"], ["outputs/s01.png"])


if __name__ == "__main__":
    unittest.main()
