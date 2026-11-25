"""Films are separate from each other, and the status report tells the truth about each one."""

import json
import tempfile
import unittest
from pathlib import Path
from unittest import mock

from core import films, paths
from core.status import film_state, repo_state
from tests import fixtures

REAL_SCHEMA_DIR = paths.SCHEMA_DIR


class TempRepoTestCase(unittest.TestCase):
    def setUp(self):
        tmp = tempfile.TemporaryDirectory()
        self.addCleanup(tmp.cleanup)
        self.root = Path(tmp.name).resolve()
        for name, value in {
            "ROOT": self.root,
            "SCHEMA_DIR": REAL_SCHEMA_DIR,
            "RUNS_PATH": self.root / "runs.jsonl",
            "FILMS_DIR": self.root / "films",
        }.items():
            patcher = mock.patch.object(paths, name, value)
            patcher.start()
            self.addCleanup(patcher.stop)

    def write(self, relative: str, data) -> None:
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")

    def stage(self, state: dict, stage_id: str) -> dict:
        return next(s for s in state["stages"] if s["id"] == stage_id)


class FilmTests(TempRepoTestCase):
    def test_new_film_gets_a_folder_named_from_its_title(self):
        slug = films.create("  Lalibela   Churches ")
        self.assertEqual(slug, "lalibela-churches")
        brief = json.loads((self.root / "films/lalibela-churches/brief.json").read_text())
        self.assertEqual((brief["title"], brief["languages"]), ("Lalibela Churches", ["en"]))
        self.assertEqual(paths.film_slugs(), ["lalibela-churches"])

    def test_a_film_can_be_started_before_its_audience_is_decided(self):
        films.create("Lalibela")
        intent = self.stage(film_state("lalibela"), "intent")
        self.assertEqual((intent["status"], intent["current"]), ("blocked", True))
        self.assertIn("audience", intent["problems"][0])

    def test_creating_the_same_film_twice_is_refused(self):
        films.create("Lalibela")
        with self.assertRaises(films.FilmExists):
            films.create("lalibela")

    def test_bad_language_is_refused_and_nothing_is_written(self):
        with self.assertRaises(Exception):
            films.create("Lalibela", languages=["English"])
        self.assertEqual(paths.film_slugs(), [])

    def test_a_film_name_cannot_point_outside_the_films_folder(self):
        for bad in ("../secrets", "a/b", "", "UPPER", ".env"):
            with self.assertRaises(SystemExit):
                paths.film(bad)


class StatusTests(TempRepoTestCase):
    def test_empty_repo_has_no_films_and_no_paperwork(self):
        state = repo_state()
        self.assertEqual(state["films"], [])
        self.assertTrue(all(not doc["exists"] for doc in state["docs"]))

    def test_every_stage_explains_itself(self):
        self.write("films/film-a/brief.json", fixtures.brief())
        for stage in film_state("film-a")["stages"]:
            self.assertIn(stage["who"], ("you", "agent", "code"))
            for field in ("who_label", "what", "your_part"):
                self.assertTrue(stage[field].strip(), f"{stage['id']} has no {field}")

    def test_unknown_film_is_an_error(self):
        with self.assertRaises(SystemExit):
            film_state("no-such-film")

    def test_progress_moves_to_the_first_unfinished_stage(self):
        self.write("films/test-subject/brief.json", fixtures.brief())
        self.write("films/test-subject/research/facts.json", {"model": "m", "facts": [
            {"id": "f01", "source_id": "wikipedia", "text": "A fact.", "quote": "A quote."}]})
        self.write("films/test-subject/research/source_web1.json",
                   {"source_id": "web1", "title": "W", "url": "https://example.org/w", "words": 200})
        self.write("films/test-subject/research/source_wikipedia.json",
                   {"source_id": "wikipedia", "title": "T", "url": "https://example.org", "text": "one two three"})
        state = film_state("test-subject")
        self.assertEqual(self.stage(state, "intent")["status"], "done")
        self.assertEqual(self.stage(state, "research")["status"], "done")
        self.assertTrue(self.stage(state, "script")["current"])
        self.assertEqual([(s["source_id"], s["words"]) for s in state["research"]["sources"]],
                         [("wikipedia", 3), ("web1", 200)])

    def test_valid_storyboard_marks_the_script_done(self):
        self.write("films/test-subject/brief.json", fixtures.brief())
        self.write("films/test-subject/storyboard.json", fixtures.storyboard())
        state = film_state("test-subject")
        self.assertTrue(self.stage(state, "script")["done"])
        self.assertEqual(len(state["storyboard"]["shots"]), 9)

    def test_outputs_are_listed_only_when_they_exist(self):
        self.write("films/test-subject/brief.json", fixtures.brief())
        self.write("films/test-subject/storyboard.json", fixtures.storyboard())
        empty = film_state("test-subject")["outputs"]
        self.assertIsNone(empty["shots"]["s01"]["picture"])
        self.assertEqual((empty["shots"]["s01"]["narration"], empty["music"]["candidates"], empty["film"]["shapes"]), ({}, [], {}))

        self.write("films/test-subject/outputs/keyframes/s01.jpg", "picture")
        self.write("films/test-subject/outputs/narration/s01.en.wav", "sound")
        self.write("films/test-subject/outputs/narration/timings.json", [
            {"shot": "s01", "language": "en", "spoken_s": 6.2, "fits": True, "model": "voice-model",
             "heard": "A line of narration.", "matches_line": True}])
        self.write("films/test-subject/outputs/music/candidate_2.m4a", "score")
        self.write("films/test-subject/outputs/film/film_9x16.mp4", "film")
        self.write("films/test-subject/outputs/film/report.json", {"placeholder_music": True, "music": "placeholder", "films": {
            "9x16": {"file": "film_9x16.mp4", "duration_s": 66.0, "loudness_lufs": -14.1, "true_peak_db": -1.3, "subtitle_cards": 12},
            "16x9": {"file": "film_16x9.mp4", "duration_s": 66.0, "loudness_lufs": -14.1, "true_peak_db": -1.3, "subtitle_cards": 11}}})
        outputs = film_state("test-subject")["outputs"]
        shot = outputs["shots"]["s01"]
        self.assertEqual(shot["picture"]["path"], "keyframes/s01.jpg")
        self.assertEqual((shot["narration"]["en"]["spoken_s"], shot["narration"]["en"]["model"]), (6.2, "voice-model"))
        self.assertEqual([c["seed"] for c in outputs["music"]["candidates"]], [2])
        self.assertEqual(list(outputs["film"]["shapes"]), ["9x16"])          # the wide file was never written
        self.assertEqual(outputs["film"]["shapes"]["9x16"]["duration_s"], 66.0)
        self.assertTrue(outputs["film"]["placeholder_music"])

    def test_broken_storyboard_is_reported_not_shown(self):
        self.write("films/test-subject/brief.json", fixtures.brief())
        self.write("films/test-subject/storyboard.json", fixtures.storyboard(shots=5))
        state = film_state("test-subject")
        self.assertIsNone(state["storyboard"])
        self.assertIn("needs at least 8", self.stage(state, "script")["problems"][0])

    def test_each_film_sees_only_its_own_runs(self):
        def line(film, status, attempt):
            return {"ts": "2026-11-24T18:00:00+00:00", "film": film, "stage": "research", "kind": "model",
                    "item": "facts", "model": "model-a", "attempt": attempt, "status": status,
                    "latency_s": 2.0, "cost_usd": 0.0,
                    "error": "HttpError: HTTP 503\nmore detail" if status == "error" else None}
        lines = [line("film-a", "error", 1), line("film-a", "error", 2), line("film-a", "ok", 3), line("film-b", "ok", 1)]
        self.write("runs.jsonl", "\n".join(json.dumps(l) for l in lines) + "\n")
        self.write("films/film-a/brief.json", fixtures.brief())
        self.write("films/film-b/brief.json", fixtures.brief())

        runs = film_state("film-a")["runs"]
        self.assertEqual((runs["attempts"], runs["ok"], runs["failed"], runs["model_calls"]), (3, 1, 2, 1))
        self.assertEqual(runs["models"][0], {"model": "model-a", "kind": "model", "ok": 1, "failed": 2, "median_latency_s": 2.0})
        self.assertEqual(runs["recent"][0]["status"], "ok")                  # newest first
        self.assertEqual(runs["recent"][1]["error"], "HttpError: HTTP 503")  # first line only
        self.assertEqual(film_state("film-b")["runs"]["attempts"], 1)

    def test_repo_report_lists_every_film_and_counts_log_entries(self):
        self.write("films/film-a/brief.json", fixtures.brief())
        self.write("films/film-b/brief.json", fixtures.brief() | {"audience": ""})
        self.write("EXPERIMENTS.md", "# Experiments\n\n## E1. First\n\ntext\n\n## E2. Second\n")
        state = repo_state()
        self.assertEqual([(f["slug"], f["done"], f["current"]["name"]) for f in state["films"]],
                         [("film-a", 1, "Research"), ("film-b", 0, "Intent")])
        self.assertEqual(state["experiments"]["titles"], ["E1. First", "E2. Second"])
        self.assertTrue(next(d for d in state["docs"] if d["name"] == "EXPERIMENTS.md")["exists"])


if __name__ == "__main__":
    unittest.main()
