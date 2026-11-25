"""The likeness policy decides whether a real person may be shown. No network is used here."""

import unittest

from agents.researcher import describe_subject, unsupported_facts
from core.webtext import page_text

PAGE = {"title": "Subject", "pageprops": {"wikibase-shortdesc": "a description", "wikibase_item": "Q1"}}


def entity(instance_of: str, born: str | None = None, died: str | None = None) -> dict:
    def claim(value):
        return [{"mainsnak": {"snaktype": "value", "datavalue": {"value": value}}}]

    claims = {"P31": claim({"id": instance_of})}
    if born:
        claims["P569"] = claim({"time": born})
    if died:
        claims["P570"] = claim({"time": died})
    return {"claims": claims}


class LikenessPolicyTests(unittest.TestCase):
    def test_living_person_may_not_be_shown(self):
        subject = describe_subject(PAGE, entity("Q5", born="+1950-00-00T00:00:00Z"))
        self.assertTrue(subject["living"])
        self.assertEqual(subject["born"], 1950)
        self.assertEqual(subject["likeness_policy"], "no_likeness")

    def test_dead_person_needs_the_directors_review(self):
        subject = describe_subject(PAGE, entity("Q5", born="+1844-08-17T00:00:00Z", died="+1913-12-12T00:00:00Z"))
        self.assertFalse(subject["living"])
        self.assertEqual(subject["died"], 1913)
        self.assertEqual(subject["likeness_policy"], "review")

    def test_place_is_unrestricted(self):
        subject = describe_subject(PAGE, entity("Q515"))
        self.assertFalse(subject["is_human"])
        self.assertEqual(subject["likeness_policy"], "unrestricted")

    def test_unknown_subject_needs_the_directors_review(self):
        subject = describe_subject({"title": "Subject"}, None)
        self.assertIsNone(subject["is_human"])
        self.assertEqual(subject["likeness_policy"], "review")


class QuoteCheckTests(unittest.TestCase):
    TEXTS = {
        "wikipedia": "She was born in a village.\nShe walked to school\nevery week.",
        "web1": "Later she studied plants at a university far away.",
    }

    def facts(self, *pairs):
        return {"facts": [{"id": f"f{n:02d}", "source_id": source, "text": "A fact about her.", "quote": quote}
                          for n, (source, quote) in enumerate(pairs, start=1)]}

    def test_exact_quotes_pass(self):
        reply = self.facts(("wikipedia", "She was born in a village."), ("web1", "studied plants"))
        self.assertEqual(unsupported_facts(reply, self.TEXTS), [])

    def test_quote_may_span_a_line_break(self):
        reply = self.facts(("wikipedia", "She walked to school every week."))
        self.assertEqual(unsupported_facts(reply, self.TEXTS), [])

    def test_invented_quote_is_rejected(self):
        reply = self.facts(("wikipedia", "She was born in a village."), ("wikipedia", "She won a prize."))
        self.assertEqual(unsupported_facts(reply, self.TEXTS), ["f02: quote is not in wikipedia word for word"])

    def test_quote_must_be_in_the_source_it_names(self):
        reply = self.facts(("web1", "She was born in a village."))
        self.assertEqual(unsupported_facts(reply, self.TEXTS), ["f01: quote is not in web1 word for word"])

    def test_unknown_source_is_rejected(self):
        reply = self.facts(("web9", "She was born in a village."))
        self.assertIn("names a source that was not given", unsupported_facts(reply, self.TEXTS)[0])

    def test_ids_must_run_in_order(self):
        reply = self.facts(("wikipedia", "She was born in a village."))
        reply["facts"][0]["id"] = "f07"
        self.assertIn("expected f01", unsupported_facts(reply, self.TEXTS)[0])


class PageTextTests(unittest.TestCase):
    HTML = """<html><head><title> A  Page </title><style>p {color: red}</style></head><body>
      <nav><p>Home About Contact and many other links in the menu bar here</p></nav>
      <p>Short caption.</p>
      <p>She walked twenty kilometres to the nearest school <b>every</b> Sunday evening.</p>
      <p><script>var tracking = 'this is a long script that must never be read as prose';</script></p>
      <ul><li>The first hybrid was released in the early 1980s and spread quickly.</li></ul>
    </body></html>"""

    def test_keeps_prose_and_drops_menus_scripts_and_captions(self):
        title, text = page_text(self.HTML)
        self.assertEqual(title, "A Page")
        self.assertEqual(text.splitlines(), [
            "She walked twenty kilometres to the nearest school every Sunday evening.",
            "The first hybrid was released in the early 1980s and spread quickly.",
        ])


if __name__ == "__main__":
    unittest.main()
