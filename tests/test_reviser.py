"""The Reviser's rules, checked without calling a model."""

import unittest

from agents.reviser import CannotDirect, apply, current_text, problems_with
from tests import fixtures


class CurrentTextTests(unittest.TestCase):
    def setUp(self):
        self.board = fixtures.storyboard()

    def test_each_target_reads_its_own_field(self):
        shot = self.board["shots"][2]
        self.assertEqual(current_text(self.board, "picture", "s03"), shot["image_prompt"])
        self.assertEqual(current_text(self.board, "line", "s03"), shot["subtitle_en"])
        self.assertEqual(current_text(self.board, "motion", "s03"), shot["motion_prompt"])
        self.assertEqual(current_text(self.board, "score", None), self.board["music"]["caption"])
        self.assertEqual(current_text(self.board, "look", None), self.board["style_block"])
        self.assertEqual(current_text(self.board, "world", None), self.board["world_block"])

    def test_an_unknown_shot_is_refused_in_plain_words(self):
        with self.assertRaises(CannotDirect) as caught:
            current_text(self.board, "picture", "s77")
        self.assertIn("no shot called", str(caught.exception))


class RuleTests(unittest.TestCase):
    def test_a_note_cannot_get_a_protected_person_named_in_a_picture(self):
        for policy in ("no_likeness", "review"):
            self.assertEqual(problems_with("A portrait of Test Subject smiling.", "picture", "Test Subject", policy),
                             ["it names the film's subject, who may not be shown"])
        self.assertEqual(problems_with("A portrait of Test Subject smiling.", "picture", "Test Subject", "unrestricted"), [])

    def test_a_revised_line_still_obeys_the_narration_rules(self):
        self.assertIn("quotation marks", problems_with('He said "I will" and walked on down the long road.', "line", "T", "review")[0])
        self.assertIn("words", problems_with("Too short.", "line", "T", "review")[0])
        self.assertEqual(problems_with("She walked twenty kilometres to school every Sunday evening.", "line", "T", "review"), [])

    def test_a_revised_score_stays_instrumental(self):
        self.assertEqual(problems_with("A slow krar piece with a singer.", "score", "T", "review"),
                         ["the score brief must say the score is instrumental"])


class ApplyTests(unittest.TestCase):
    def setUp(self):
        self.board = fixtures.storyboard()

    def test_a_picture_note_changes_one_shot_only(self):
        before = [s["image_prompt"] for s in self.board["shots"]]
        apply(self.board, {"target": "picture", "shot": "s04", "after": "Two hands holding a clay cup of coffee."})
        after = [s["image_prompt"] for s in self.board["shots"]]
        self.assertEqual(after[3], "Two hands holding a clay cup of coffee.")
        self.assertEqual(after[:3] + after[4:], before[:3] + before[4:])

    def test_an_english_line_note_changes_the_narration_and_the_subtitle_together(self):
        apply(self.board, {"target": "line", "shot": "s01", "after": "She walked to school every week."})
        shot = self.board["shots"][0]
        self.assertEqual((shot["narration"]["en"], shot["subtitle_en"]), ("She walked to school every week.",) * 2)

    def test_changing_the_score_brief_clears_the_old_choice(self):
        self.board["music"]["chosen_seed"] = 2
        apply(self.board, {"target": "score", "shot": None, "after": "Slow instrumental krar and washint."})
        self.assertNotIn("chosen_seed", self.board["music"])
        self.assertEqual(self.board["music"]["caption"], "Slow instrumental krar and washint.")


if __name__ == "__main__":
    unittest.main()
