"""The likeness policy decides whether a real person may be shown. No network is used here."""

import unittest

from agents.researcher import describe_subject, unsupported_facts

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
    SOURCE = "She was born in a village.\nShe walked to school\nevery week. Later she studied plants."

    def facts(self, *quotes):
        return {"facts": [{"id": f"f{n:02d}", "text": "A fact about her.", "quote": q}
                          for n, q in enumerate(quotes, start=1)]}

    def test_exact_quotes_pass(self):
        self.assertEqual(unsupported_facts(self.facts("She was born in a village.", "studied plants"), self.SOURCE), [])

    def test_quote_may_span_a_line_break(self):
        self.assertEqual(unsupported_facts(self.facts("She walked to school every week."), self.SOURCE), [])

    def test_invented_quote_is_rejected(self):
        problems = unsupported_facts(self.facts("She was born in a village.", "She won a prize."), self.SOURCE)
        self.assertEqual(problems, ["f02: quote is not in the source word for word"])

    def test_ids_must_run_in_order(self):
        reply = self.facts("She was born in a village.")
        reply["facts"][0]["id"] = "f07"
        self.assertIn("expected f01", unsupported_facts(reply, self.SOURCE)[0])


if __name__ == "__main__":
    unittest.main()
