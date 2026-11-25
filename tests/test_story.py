"""The checks that stand between an agent's reply and the storyboard. No model is called here."""

import unittest

from agents.story import (
    assemble, film_length_s, music_problems, script_problems, shot_duration_s, visuals_problems,
)
from core.contracts import _schema_problems, _storyboard_rule_problems

FACTS = {"f01", "f02", "f03"}
LINE = "She walked twenty kilometres to the nearest school every single Sunday evening of her childhood."  # 15 words


def script(shots: int = 10, line: str = LINE) -> dict:
    return {"shots": [{"beat": "a moment", "narration": line, "fact_ids": ["f01"]} for _ in range(shots)]}


def visuals(shots: int = 10) -> dict:
    sizes = ["wide", "medium", "close"]
    return {
        "style_block": "warm hand-painted look, soft morning light, grainy paper texture",
        "world_block": "Rural highland Ethiopia in the 1950s. Every person is Ethiopian, with deep brown skin.",
        "reference_sheet_prompt": "a reference sheet of highland fields, tall grain and worn hands",
        "shots": [{"size": sizes[n % 3], "image_prompt": "a dirt road through tall grain at dawn",
                   "motion_prompt": "slow push in", "reason": "Shows where the story begins."}
                  for n in range(shots)],
    }


MUSIC = {"caption": "gentle acoustic texture, warm and unhurried, instrumental", "bpm": 72, "key": "D major",
         "cues": [{"at_s": 0, "note": "enters"}, {"at_s": 30, "note": "lifts"}, {"at_s": 60, "note": "returns"}]}
SHORT = "She walked twenty kilometres to the nearest school every single Sunday."  # 11 words
BRIEF = {"title": "Test Subject", "audience": "a", "feeling": "b", "languages": ["en"]}


class TimingTests(unittest.TestCase):
    def test_duration_follows_the_word_count(self):
        self.assertEqual(shot_duration_s(LINE), 8.5)            # 15 words / 1.95 + 0.8 = 8.49, rounded up to a half
        self.assertEqual(shot_duration_s("Two words."), 3.0)    # never shorter than 3 s
        self.assertEqual(shot_duration_s("word " * 60), 12.0)   # never longer than 12 s

    def test_film_length_includes_the_end_card(self):
        self.assertEqual(film_length_s([LINE] * 10), 88.0)


class ScriptCheckTests(unittest.TestCase):
    def test_good_script_passes(self):
        self.assertEqual(script_problems(script(), FACTS), [])

    def test_unknown_fact_is_rejected(self):
        reply = script()
        reply["shots"][2]["fact_ids"] = ["f99"]
        self.assertIn("shot 3 cites facts that do not exist: f99", script_problems(reply, FACTS))

    def test_quoting_someone_is_rejected(self):
        reply = script()
        reply["shots"][0]["narration"] = 'He said "I will feed them" and walked on down the long dry road.'
        self.assertIn("quotation marks", script_problems(reply, FACTS)[0])

    def test_too_many_words_is_rejected(self):
        problems = script_problems(script(shots=12, line=LINE + " And she kept on walking."), FACTS)
        self.assertTrue(any("words; it must be 110-155" in p for p in problems))
        self.assertTrue(any("must be 60-90 s" in p for p in problems))

    def test_a_script_that_cites_nothing_is_rejected(self):
        reply = script()
        for shot in reply["shots"]:
            shot["fact_ids"] = []
        self.assertIn("no shot cites a fact", script_problems(reply, FACTS))


class VisualsCheckTests(unittest.TestCase):
    def test_good_visuals_pass(self):
        self.assertEqual(visuals_problems(visuals(), 10, "Test Subject", "no_likeness"), [])

    def test_one_picture_per_shot(self):
        self.assertIn("9 pictures for 10 shots", visuals_problems(visuals(9), 10, "Test Subject", "review")[0])

    def test_shot_sizes_must_vary(self):
        reply = visuals()
        for shot in reply["shots"]:
            shot["size"] = "wide"
        problems = visuals_problems(reply, 10, "Test Subject", "review")
        self.assertIn("only 0 medium shot(s); use each size at least twice", problems)

    def test_a_person_who_may_not_be_shown_is_never_named_in_a_picture(self):
        reply = visuals()
        reply["shots"][4]["image_prompt"] = "portrait of Test Subject smiling in a laboratory"
        self.assertEqual(visuals_problems(reply, 10, "Test Subject", "no_likeness"),
                         ["shot 5 image_prompt names the subject, who may not be shown"])
        self.assertEqual(visuals_problems(reply, 10, "Test Subject", "unrestricted"), [])


class MusicCheckTests(unittest.TestCase):
    def test_good_music_passes(self):
        self.assertEqual(music_problems(MUSIC, [0, 30, 60], 78), [])

    def test_score_must_be_instrumental_and_fit_the_film(self):
        reply = MUSIC | {"caption": "a soaring pop song with vocals and drums",
                         "cues": [{"at_s": 5, "note": "enters"}, {"at_s": 90, "note": "ends"}]}
        problems = music_problems(reply, [0], 78)
        self.assertEqual(len(problems), 3)


class AssembleTests(unittest.TestCase):
    def test_assembled_storyboard_satisfies_the_contract(self):
        board = assemble(BRIEF, script(), visuals(), MUSIC)
        self.assertEqual(_schema_problems(board, "storyboard.schema.json"), [])
        self.assertEqual(_storyboard_rule_problems(board), [])
        self.assertEqual([s["id"] for s in board["shots"]][:2], ["s01", "s02"])
        self.assertTrue(all(s["motion_mode"] == "ken_burns" for s in board["shots"]))
        self.assertEqual(len({s["seed"] for s in board["shots"]}), 10)


if __name__ == "__main__":
    unittest.main()
