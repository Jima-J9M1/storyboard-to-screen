import json
import tempfile
import unittest
from pathlib import Path

from core.contracts import ValidationError, film_duration_s, load_brief, load_storyboard
from tests import fixtures


class ContractTestCase(unittest.TestCase):
    def setUp(self):
        self._tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self._tmp.cleanup)
        self.tmp = Path(self._tmp.name)

    def write(self, name: str, data: dict) -> Path:
        path = self.tmp / name
        path.write_text(json.dumps(data), encoding="utf-8")
        return path

    def problems(self, loader, data: dict, **kwargs) -> str:
        with self.assertRaises(ValidationError) as caught:
            loader(self.write("input.json", data), **kwargs)
        return "\n".join(caught.exception.problems)


class StoryboardTests(ContractTestCase):
    def test_valid_storyboard_loads(self):
        board = load_storyboard(self.write("sb.json", fixtures.storyboard()))
        self.assertEqual(film_duration_s(board), 66)

    def test_missing_file_is_reported(self):
        with self.assertRaises(ValidationError):
            load_storyboard(self.tmp / "absent.json")

    def test_fewer_than_8_shots_is_rejected(self):
        self.assertIn("needs at least 8", self.problems(load_storyboard, fixtures.storyboard(shots=5)))

    def test_more_than_12_shots_is_rejected(self):
        board = fixtures.storyboard(shots=13)
        for s in board["shots"]:
            s["duration_s"] = 5
        self.assertIn("needs at most 12", self.problems(load_storyboard, board))

    def test_shot_without_reason_is_rejected(self):
        board = fixtures.storyboard()
        del board["shots"][0]["reason"]
        self.assertIn("'reason' is a required property", self.problems(load_storyboard, board))

    def test_end_card_must_mention_ai(self):
        board = fixtures.storyboard()
        board["end_card"]["text"] = "The end"
        self.assertIn("end_card/text", self.problems(load_storyboard, board))

    def test_film_longer_than_90_seconds_is_rejected(self):
        board = fixtures.storyboard(shots=12)
        for s in board["shots"]:
            s["duration_s"] = 8  # 96 s + 3 s end card
        self.assertIn("must be 60-90 s", self.problems(load_storyboard, board))

    def test_film_shorter_than_60_seconds_is_rejected(self):
        board = fixtures.storyboard(shots=8)
        for s in board["shots"]:
            s["duration_s"] = 5  # 40 s + 3 s end card
        self.assertIn("must be 60-90 s", self.problems(load_storyboard, board))

    def test_duplicate_shot_id_is_rejected(self):
        board = fixtures.storyboard()
        board["shots"][1]["id"] = board["shots"][0]["id"]
        self.assertIn("used more than once", self.problems(load_storyboard, board))

    def test_every_language_needs_a_narration_line(self):
        board = fixtures.storyboard()
        board["languages"] = ["en", "am"]
        self.assertIn("missing language(s) am", self.problems(load_storyboard, board))

    def test_narrated_shot_needs_an_english_subtitle(self):
        board = fixtures.storyboard()
        board["shots"][0]["subtitle_en"] = ""
        self.assertIn("no English subtitle", self.problems(load_storyboard, board))

    def test_unknown_field_is_rejected(self):
        board = fixtures.storyboard()
        board["shots"][0]["prompt"] = "typo for image_prompt"
        self.assertIn("Additional properties", self.problems(load_storyboard, board))


class BriefTests(ContractTestCase):
    def test_valid_brief_loads(self):
        self.assertEqual(load_brief(self.write("b.json", fixtures.brief()))["title"], "Test subject")

    def test_empty_intent_blocks_generation(self):
        brief = fixtures.brief() | {"audience": "", "feeling": ""}
        found = self.problems(load_brief, brief)
        self.assertIn("audience: must be written by the director", found)
        self.assertIn("feeling: must be written by the director", found)

    def test_empty_intent_is_allowed_for_research(self):
        brief = fixtures.brief() | {"audience": "", "feeling": ""}
        self.assertEqual(load_brief(self.write("b.json", brief), require_intent=False)["title"], "Test subject")

    def test_extra_sources_must_be_https_links(self):
        ok = fixtures.brief() | {"sources": ["https://example.org/page"]}
        self.assertEqual(len(load_brief(self.write("b.json", ok))["sources"]), 1)
        self.assertIn("sources/0", self.problems(load_brief, fixtures.brief() | {"sources": ["example.org"]}))

    def test_bad_language_code_is_rejected(self):
        brief = fixtures.brief() | {"languages": ["English"]}
        self.assertIn("languages/0", self.problems(load_brief, brief))


if __name__ == "__main__":
    unittest.main()
