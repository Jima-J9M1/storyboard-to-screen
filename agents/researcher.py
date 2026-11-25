"""Researcher: collect sourced material about the brief's title.

Reads   films/<slug>/brief.json   title, and the optional list of extra source pages
Writes  films/<slug>/research/source_wikipedia.json   the article text, its revision and licence
        films/<slug>/research/source_web<n>.json      one record per extra page: url, date, fingerprint
        films/<slug>/research/subject.json            what the title is, and the likeness policy
        films/<slug>/research/facts.json              numbered facts, each quoting its source

Step 1 fetches the sources and needs no key.
Step 2 asks a language model to list the facts, then checks every fact's quote against the
text of the source it names. A fact whose quote is not in that source word for word is
rejected, so the model cannot add anything the sources do not say.

Wikipedia text is openly licensed and is committed. The text of other pages belongs to their
publishers, so only a record of each page is committed; the text itself is kept in a
git-ignored folder and fetched again when it is needed.

If the title is a living person, the likeness policy is set to "no_likeness": the film may not
show them, voice them or put invented words in their mouth unless ETHICS.md records consent.

Usage:
    python -m agents.researcher --film gebisa-ejeta            # skips whatever is already up to date
    python -m agents.researcher --film gebisa-ejeta --refresh  # fetch and extract again
"""

from __future__ import annotations

import argparse
import hashlib
import sys
from datetime import datetime, timezone
from pathlib import Path

from core import http, llm, paths
from core.cache import Cache
from core.contracts import ValidationError, load_brief
from core.files import load_json, write_json
from core.runlog import input_hash, logged_call, set_film
from core.webtext import page_text

STAGE = "research"
WIKIPEDIA_API = "https://en.wikipedia.org/w/api.php"
WIKIDATA_ENTITY = "https://www.wikidata.org/wiki/Special:EntityData/{qid}.json"
WIKIPEDIA_LICENCE = "CC BY-SA 4.0"
WEB_LICENCE = "Copyright of the publisher. The text is not redistributed here; short passages are quoted as citations."
HUMAN = "Q5"  # Wikidata: instance of human
P_INSTANCE_OF, P_BORN, P_DIED = "P31", "P569", "P570"
FACTS_PROMPT = Path(__file__).parent / "prompts" / "researcher_facts.md"
FACTS_SEED = 1
FACTS_TEMPERATURE = 0.0
MIN_PAGE_WORDS = 150  # below this a page is a stub, a login wall or a bot check


def _now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def _fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


# ---------- step 1a: Wikipedia and Wikidata ----------

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


def research_wikipedia(title: str, film: paths.Film, cache: Cache, refresh: bool) -> dict:
    source_path = film.research / "source_wikipedia.json"
    subject_path = film.research / "subject.json"
    key = input_hash(title, WIKIPEDIA_API)
    if cache.fresh("wikipedia", key) and not refresh:
        print(f"research: wikipedia is already fetched for \"{title}\"; no fetch made.")
        return load_json(source_path)

    page = fetch_article(title)
    qid = page.get("pageprops", {}).get("wikibase_item")
    entity = fetch_entity(qid) if qid else None
    source = {
        "source_id": "wikipedia",
        "title": page["title"],
        "url": page["canonicalurl"],
        "revision_id": page["lastrevid"],
        "permalink": f"https://en.wikipedia.org/w/index.php?oldid={page['lastrevid']}",
        "licence": WIKIPEDIA_LICENCE,
        "retrieved_at": _now(),
        "text": page["extract"],
    }
    subject = describe_subject(page, entity)
    write_json(source_path, source)
    write_json(subject_path, subject)
    cache.store("wikipedia", key, [source_path, subject_path])
    print(f"research: saved {len(page['extract'].split())} words from wikipedia on \"{page['title']}\".")
    print(f"research: likeness policy is \"{subject['likeness_policy']}\". {subject['policy_reason']}")
    return source


# ---------- step 1b: extra pages listed in the brief ----------

def _text_path(film: paths.Film, source_id: str) -> Path:
    return film.research / ".text" / f"{source_id}.txt"


def fetch_page(url: str, source_id: str) -> tuple[str, str]:
    """Fetch one page and return (title, text). A page with too little prose is a failure."""
    def fetch() -> tuple[str, str]:
        title, text = page_text(http.get_text(url))
        words = len(text.split())
        if words < MIN_PAGE_WORDS:
            raise http.HttpError(f"only {words} words of prose at {url}; the page may block scripts")
        return title, text

    return logged_call(
        fetch, stage=STAGE, kind="fetch", model="web-page", params={"url": url},
        key=input_hash(url), item=source_id,
    )


def research_page(url: str, source_id: str, film: paths.Film, cache: Cache, refresh: bool) -> dict:
    record_path = film.research / f"source_{source_id}.json"
    key = input_hash(url)
    if cache.fresh(source_id, key) and not refresh:
        print(f"research: {source_id} is already fetched; no fetch made.")
        return load_json(record_path)

    title, text = fetch_page(url, source_id)
    record = {
        "source_id": source_id,
        "title": title,
        "url": url,
        "licence": WEB_LICENCE,
        "retrieved_at": _now(),
        "words": len(text.split()),
        "sha256": _fingerprint(text),
    }
    write_json(record_path, record)
    text_path = _text_path(film, source_id)
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text, encoding="utf-8")
    cache.store(source_id, key, [record_path])
    print(f"research: saved a record of {record['words']} words from {source_id} ({url}).")
    return record


def source_text(source: dict, film: paths.Film) -> str:
    """The text of a source. A web page's text is fetched again if it is not on this machine."""
    if "text" in source:
        return source["text"]
    text_path = _text_path(film, source["source_id"])
    if text_path.exists():
        return text_path.read_text(encoding="utf-8")
    _, text = fetch_page(source["url"], source["source_id"])
    if _fingerprint(text) != source["sha256"]:
        print(f"research: warning: {source['source_id']} has changed since it was first fetched.")
    text_path.parent.mkdir(parents=True, exist_ok=True)
    text_path.write_text(text, encoding="utf-8")
    return text


# ---------- step 2: facts ----------

def _squash(text: str) -> str:
    """Collapse runs of whitespace, so a quote still matches across a line break."""
    return " ".join(text.split())


def unsupported_facts(reply: dict, texts: dict[str, str]) -> list[str]:
    """Problems with a fact list: unknown sources, quotes not in their source, ids out of order.

    texts maps each source id to that source's text.
    """
    squashed = {source_id: _squash(text) for source_id, text in texts.items()}
    problems = []
    for n, fact in enumerate(reply["facts"], start=1):
        if fact["id"] != f"f{n:02d}":
            problems.append(f"fact {n} has id {fact['id']}; expected f{n:02d}")
        if fact["source_id"] not in squashed:
            problems.append(f"{fact['id']}: names a source that was not given ({fact['source_id']})")
        elif _squash(fact["quote"]) not in squashed[fact["source_id"]]:
            problems.append(f"{fact['id']}: quote is not in {fact['source_id']} word for word")
    return problems


def extract_facts(title: str, film: paths.Film, sources: list[dict], cache: Cache, refresh: bool) -> None:
    facts_path = film.research / "facts.json"
    system = FACTS_PROMPT.read_text(encoding="utf-8")
    # The key uses each source's fingerprint, so a clean clone can tell the facts are
    # up to date without fetching any page.
    fingerprints = [[s["source_id"], s.get("sha256") or _fingerprint(s["text"])] for s in sources]
    key = input_hash(llm.TEXT_MODELS, system, fingerprints, FACTS_TEMPERATURE, FACTS_SEED)
    if cache.fresh("facts", key) and not refresh:
        print("research: facts are up to date; no model call made.")
        return

    texts = {s["source_id"]: source_text(s, film) for s in sources}
    prompt = f"Subject: {title}\n\n" + "\n\n".join(
        f"=== Source id: {source_id} ===\n{text}" for source_id, text in texts.items()
    )
    reply, model = llm.generate_json(
        prompt, load_json(paths.SCHEMA_DIR / "facts.schema.json"),
        stage=STAGE, item="facts", system=system, key=key,
        temperature=FACTS_TEMPERATURE, seed=FACTS_SEED,
        check=lambda parsed: unsupported_facts(parsed, texts),
    )
    write_json(facts_path, {
        "sources": [{"source_id": s["source_id"], "url": s.get("permalink") or s["url"]} for s in sources],
        "model": model,
        "facts": reply["facts"],
    })
    cache.store("facts", key, [facts_path])
    per_source = {sid: sum(f["source_id"] == sid for f in reply["facts"]) for sid in texts}
    counts = ", ".join(f"{n} from {sid}" for sid, n in per_source.items())
    print(f"research: saved {len(reply['facts'])} facts ({counts}), each quoting its source.")


# ---------- entry point ----------

def run(film_slug: str, refresh: bool = False) -> int:
    film = paths.film(film_slug)
    set_film(film.slug)
    try:
        brief = load_brief(film.brief, require_intent=False)
    except ValidationError as err:
        print(err, file=sys.stderr)
        return 1

    title = brief["title"]
    cache = Cache(film, STAGE)
    sources = [research_wikipedia(title, film, cache, refresh)]
    for n, url in enumerate(brief.get("sources", []), start=1):
        sources.append(research_page(url, f"web{n}", film, cache, refresh))
    extract_facts(title, film, sources, cache, refresh)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--film", required=True, help="the film's folder name under films/")
    parser.add_argument("--refresh", action="store_true", help="fetch and extract again")
    args = parser.parse_args()
    return run(args.film, args.refresh)


if __name__ == "__main__":
    sys.exit(main())
