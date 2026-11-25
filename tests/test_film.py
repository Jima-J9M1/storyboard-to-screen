"""The parts of the film half that can be checked without FFmpeg or a model."""

import unittest

from core import titles
from pipeline.shots import choose_move


class MoveTests(unittest.TestCase):
    def test_each_kind_of_prompt_gets_its_move(self):
        for prompt, move in {
            "slow push in": "push in",
            "slow pull back": "pull back",
            "slow pan left to right, fixed horizon": "pan left to right",
            "slow pan right to left": "pan right to left",
            "slow tilt up": "tilt up",
            "slow tilt down": "tilt down",
        }.items():
            self.assertEqual(choose_move("ken_burns", prompt)[0], move, prompt)

    def test_an_unrecognised_prompt_gets_a_gentle_push_in(self):
        self.assertEqual(choose_move("ken_burns", "drift like a leaf")[0], "push in")

    def test_a_still_shot_does_not_move(self):
        name, (zoom, x, y) = choose_move("still", "slow push in")
        self.assertEqual((name, zoom), ("still", "1"))

    def test_a_video_shot_falls_back_to_a_camera_move(self):
        self.assertEqual(choose_move("video", "slow tilt up")[0], "tilt up")


class SubtitleTests(unittest.TestCase):
    LINE = "Why would a young boy walk twenty kilometres across Ethiopia every Sunday evening just to attend primary school?"

    def test_a_card_never_has_more_than_two_lines(self):
        for width in (30, 42):
            cards = titles.subtitle_cards(self.LINE, width)
            self.assertTrue(all(card.count("\n") <= 1 for card in cards))
            self.assertTrue(all(len(line) <= width for card in cards for line in card.split("\n")))

    def test_no_word_is_lost_or_reordered(self):
        cards = titles.subtitle_cards(self.LINE, 30)
        self.assertEqual(" ".join(" ".join(cards).split()), self.LINE)

    def test_cards_share_the_spoken_time_without_gaps(self):
        cards = titles.subtitle_cards(self.LINE, 30)
        times = titles.card_times(cards, 10.0, 8.0)
        self.assertEqual(times[0][0], 10.0)
        self.assertAlmostEqual(times[-1][1], 18.0, places=2)
        for (_, off), (on, _) in zip(times, times[1:]):
            self.assertEqual(off, on)


if __name__ == "__main__":
    unittest.main()
