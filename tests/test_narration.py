"""Checks on the narration that stand in for ears. No model is called here."""

import tempfile
import unittest
from pathlib import Path

from core import audio
from pipeline.narration import heard_problem

LINE = "In 1994, eight tons of his resistant seeds were distributed to twelve African nations."


class HeardTests(unittest.TestCase):
    def test_a_faithful_transcript_passes(self):
        self.assertIsNone(heard_problem(LINE, "In 1994, 8 tons of his resistant seeds were distributed to 12 African nations."))

    def test_a_spoken_instruction_is_caught(self):
        heard = "Say in a calm, warm, unhurried voice. In 1994, 8 tons of his resistant seeds were distributed to 12 African nations."
        self.assertIn("says 7 more words than its line", heard_problem(LINE, heard))

    def test_a_cut_off_line_is_caught(self):
        self.assertIn("fewer words", heard_problem(LINE, "In 1994, eight tons of his resistant seeds"))

    def test_an_unchecked_file_is_reported_as_unchecked(self):
        self.assertIn("not checked", heard_problem(LINE, ""))


class TrackTests(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.dir = Path(tmp.name)

    def clip(self, name: str, seconds: float, sample: bytes) -> Path:
        path = self.dir / name
        audio.write_pcm(path, sample * int(seconds * audio.SAMPLE_RATE))
        return path

    def test_duration_is_read_from_the_file(self):
        self.assertEqual(audio.duration_s(self.clip("a.wav", 1.5, b"\x01\x00")), 1.5)

    def test_clips_are_placed_at_their_start_times(self):
        a, b = self.clip("a.wav", 1, b"\x01\x00"), self.clip("b.wav", 1, b"\x02\x00")
        track = audio.lay_out([(0, a), (2, b)], 4)
        second = audio.SAMPLE_RATE * audio.SAMPLE_BYTES
        self.assertEqual(len(track), 4 * second)
        self.assertEqual((track[0:2], track[second:second + 2], track[2 * second:2 * second + 2], track[3 * second:3 * second + 2]),
                         (b"\x01\x00", b"\x00\x00", b"\x02\x00", b"\x00\x00"))

    def test_a_clip_that_runs_past_the_end_lengthens_the_track(self):
        track = audio.lay_out([(1, self.clip("a.wav", 2, b"\x01\x00"))], 2)
        self.assertEqual(len(track), 3 * audio.SAMPLE_RATE * audio.SAMPLE_BYTES)


if __name__ == "__main__":
    unittest.main()
