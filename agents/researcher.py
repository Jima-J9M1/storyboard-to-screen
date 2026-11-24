"""Researcher: collect sourced material about the brief's title.

Reads   brief.json (title only; audience and feeling are not needed yet)
Writes  research/<slug>/source_wikipedia.json   the article text, its revision and licence
        research/<slug>/subject.json            what the title is, and the likeness policy
        research/<slug>/facts.json              numbered facts, each quoting the source

Step 1 fetches the source and needs no key. Step 2 asks a language model to list the facts,
then checks every fact's quote against the source text: a fact whose quote is not in the
source word for word is rejected, so the model cannot add anything the source does not say.

If the title is a living person, the likeness policy is set to "no_likeness": the film may not
show them, voice them or put invented words in their mouth unless ETHICS.md records consent.

Usage:
    python -m agents.researcher            # skips the fetch if the title was already researched
    python -m agents.researcher --refresh  # fetch again
"""

from __future__ import annotations

import argparse
import sys
from datetime import datetime, timezone
from pathlib import Path

from core import http, llm, paths
from core.cache import Cache
from core.contracts import ValidationError, load_brief
from core.files import load_json, slugify, write_json
from core.runlog import input_hash, logged_call

STAGE = "research"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
WIKIPEDIA_LICENCE = "CC BY-SA 4.0"
HUMAN = "Q5"  # Wikidata: instance of human
P_INSTANCE_OF, P_BORN, P_DIED = "P31", "P569", "P570"
FACTS_PROMPT = Path(__file__).parent / "prompts" / "researcher_facts.md"
FACTS_SEED = 1
FACTS_TEMPERATURE = 0.0


def fetch_article(title: str) -> dict:
    params = {
        "action": "query", "format": "json", "formatversion": "2", "redirects": "1",
        "prop": "extracts|pageprops|info", "explaintext": "1", "inprop": "url", "titles": title,
    }
    data = logged_call(
        lambda: http.get_json(WIKIPEDIA_API, params),
        stage=STAGE, kind="fetch", model="wikipedia-api", params=params,
        key=input_hash(title), item="article",
    )
    page = data["query"]["pages"][0]
    if page.get("missing") or not page.get("extract"):
        raise SystemExit(
            f"research: Wikipedia has no article titled \"{title}\". "
            "Change the title in brief.json to match an article name."
        )
    return page


def fetch_entity(qid: str) -> dict:
    data = logged_call(
        lambda: http.get_json(WIKIDATA_ENTITY.format(qid=qid)),
        stage=STAGE, kind="fetch", model="wikidata-entity", params={"qid": qid},
        key=input_hash(qid), item="subject",
    )
    return data["entities"][qid]


def _claim_values(entity: dict, prop: str) -> list:
    values = []
    for claim in entity.get("claims", {}).get(prop, []):
        snak = claim.get("mainsnak", {})
        if snak.get("snaktype") == "value":
            values.append(snak["datavalue"]["value"])
    return values


def _year(time_value: dict) -> int | None:
    # Wikidata time looks like "+1950-00-00T00:00:00Z"
    try:
        return int(time_value["time"][1:5])
    except (KeyError, ValueError, TypeError):
        return None


def describe_subject(page: dict, entity: dict | None) -> dict:
    """Say what the title is and decide the likeness policy from it."""
    props = page.get("pageprops", {})
    subject = {
        "title": page["title"],
        "description": props.get("wikibase-shortdesc"),
        "wikidata_id": props.get("wikibase_item"),
        "is_human": None, "born": None, "died": None, "living": None,
    }
    if entity is not None:
        kinds = [v.get("id") for v in _claim_values(entity, P_INSTANCE_OF)]
        born = [_year(v) for v in _claim_values(entity, P_BORN)]
        died = [_year(v) for v in _claim_values(entity, P_DIED)]
        subject["is_human"] = HUMAN in kinds
        subject["born"] = born[0] if born else None
        subject["died"] = died[0] if died else None
        subject["living"] = subject["is_human"] and not died

    if subject["living"]:
        policy, reason = "no_likeness", (
            "Wikidata lists the subject as a human with no date of death. Without a consent record "
            "in ETHICS.md the film must not show them, voice them or give them invented quotes."
        )
    elif subject["is_human"]:
        policy, reason = "review", (
            "The subject is a real person who has died. The director decides how they are depicted "
            "and records the decision in ETHICS.md."
        )
    elif subject["is_human"] is None:
        policy, reason = "review", (
            "Could not tell from Wikidata whether the subject is a real person. The director must check."
        )
    else:
        policy, reason = "unrestricted", (
            "The subject is not a person. Any real people in the story still need the same check."
        )
    subject["likeness_policy"] = policy
    subject["policy_reason"] = reason
    return subject


def _squash(text: str) -> str:
    """Collapse runs of whitespace, so a quote still matches across a line break."""
    return " ".join(text.split())


def unsupported_facts(reply: dict, source_text: str) -> list[str]:
    """Problems with a fact list: quotes that are not in the source, and ids out of order."""
    source = _squash(source_text)
    problems = []
    for n, fact in enumerate(reply["facts"], start=1):
        if fact["id"] != f"f{n:02d}":
            problems.append(f"fact {n} has id {fact['id']}; expected f{n:02d}")
        if _squash(fact["quote"]) not in source:
            problems.append(f"{fact['id']}: quote is not in the source word for word")
    return problems


def extract_facts(slug: str, source: dict, refresh: bool) -> Path:
    """Step 2: list the facts in the source, each with the words that support it."""
    facts_path = paths.RESEARCH_DIR / slug / "facts.json"
    system = FACTS_PROMPT.read_text(encoding="utf-8")
    prompt = f"Subject: {source['title']}\n\nSource text:\n{source['text']}"
    key = llm.request_key(system, prompt, FACTS_TEMPERATURE, FACTS_SEED)

    cache = Cache(STAGE)
    item = f"{slug}:facts"
    if cache.fresh(item, key) and not refresh:
        print("research: facts are up to date; no model call made.")
        return facts_path

    reply, model = llm.generate_json(
        prompt, load_json(paths.SCHEMA_DIR / "facts.schema.json"),
        stage=STAGE, item="facts", system=system,
        temperature=FACTS_TEMPERATURE, seed=FACTS_SEED,
        check=lambda parsed: unsupported_facts(parsed, source["text"]),
    )
    write_json(facts_path, {
        "source_id": source["source_id"],
        "source_permalink": source["permalink"],
        "model": model,
        "facts": reply["facts"],
    })
    cache.store(item, key, [facts_path])
    print(f"research: saved {len(reply['facts'])} facts, each quoting the source, to research/{slug}/facts.json")
    return facts_path


def run(brief_path: Path | None = None, refresh: bool = False) -> int:
    try:
        brief = load_brief(brief_path, require_intent=False)
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1

    title = brief["title"]
    slug = slugify(title)
    out_dir = paths.RESEARCH_DIR / slug
    source_path = out_dir / "source_wikipedia.json"
    subject_path = out_dir / "subject.json"

    cache = Cache(STAGE)
    key = input_hash(title, WIKIPEDIA_API)
    if cache.fresh(slug, key) and not refresh:
        print(f"research: \"{title}\" is already fetched; no fetch made. Use --refresh to fetch again.")
    else:
        page = fetch_article(title)
        qid = page.get("pageprops", {}).get("wikibase_item")
        entity = fetch_entity(qid) if qid else None

        write_json(source_path, {
            "source_id": "wikipedia",
            "title": page["title"],
            "url": page["canonicalurl"],
            "revision_id": page["lastrevid"],
            "permalink": f"https://en.wikipedia.org/w/index.php?oldid={page['lastrevid']}",
            "licence": WIKIPEDIA_LICENCE,
            "retrieved_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
            "text": page["extract"],
        })
        subject = describe_subject(page, entity)
        write_json(subject_path, subject)
        cache.store(slug, key, [source_path, subject_path])
        print(f"research: saved {len(page['extract'].split())} words on \"{page['title']}\" to research/{slug}/")
        print(f"research: likeness policy is \"{subject['likeness_policy']}\". {subject['policy_reason']}")

    extract_facts(slug, load_json(source_path), refresh)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--brief", type=Path, default=None, help="path to a brief file (default: brief.json)")
    parser.add_argument("--refresh", action="store_true", help="fetch again even if already researched")
    args = parser.parse_args()
    return run(args.brief, args.refresh)


if __name__ == "__main__":
    sys.exit(main())
