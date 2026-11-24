"""Text generation for the agents, through the Gemini API.

One function, generate_json: ask for JSON, check the reply against a JSON Schema and any
extra check the caller supplies, and retry if it fails. A reply that does not fit the
schema is treated like any other failed call: logged, retried, and never saved.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from jsonschema import Draft202012Validator

from core import env, http
from core.runlog import input_hash, logged_call

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
# Tried in order. A model is given three attempts before the next one is used, because the
# free tier answers "503 high demand" for minutes at a time on the newest model.
TEXT_MODELS = ["gemini-3.8-flash", "gemini-3.7-flash", "gemini-3.5-flash"]


class BadReply(Exception):
    """The model answered, but the answer broke the contract."""


def request_key(system: str, prompt: str, temperature: float, seed: int,
                models: list[str] | None = None) -> str:
    """The input hash of a request. Agents use it as their cache key."""
    return input_hash(models or TEXT_MODELS, system, prompt, temperature, seed)


def _reply_text(response: dict) -> str:
    try:
        parts = response["candidates"][0]["content"]["parts"]
    except (KeyError, IndexError):
        raise BadReply(f"no content in reply: {json.dumps(response)[:200]}") from None
    return "".join(p["text"] for p in parts if "text" in p and not p.get("thought"))


def _token_counts(response: dict) -> dict:
    usage = response.get("usageMetadata", {})
    return {
        "tokens_in": usage.get("promptTokenCount"),
        "tokens_out": usage.get("candidatesTokenCount"),
        "tokens_thinking": usage.get("thoughtsTokenCount"),
    }


def generate_json(
    prompt: str,
    schema: dict,
    *,
    stage: str,
    item: str,
    system: str = "",
    models: list[str] | None = None,
    temperature: float = 0.2,
    seed: int = 1,
    check: Callable[[Any], list[str]] | None = None,
) -> tuple[Any, str]:
    """Return (reply, model): the parsed JSON that satisfies `schema` and `check`, and who wrote it.

    models  tried in order; each gets three attempts before the next is used
    check   optional: takes the parsed reply and returns a list of problems (empty if fine)
    """
    models = models or TEXT_MODELS
    api_key = env.require("GEMINI_API_KEY")
    params = {"temperature": temperature, "response_mime_type": "application/json"}
    body: dict = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": temperature, "seed": seed,
                             "responseMimeType": "application/json"},
    }
    if system:
        body["systemInstruction"] = {"parts": [{"text": system}]}

    validator = Draft202012Validator(schema)
    holder: dict = {}

    def call(model: str) -> dict:
        response = http.post_json(API_URL.format(model=model), body, headers={"x-goog-api-key": api_key})
        text = _reply_text(response)
        try:
            parsed = json.loads(text)
        except json.JSONDecodeError as err:
            raise BadReply(f"reply is not JSON: {err}") from None
        problems = [e.message for e in validator.iter_errors(parsed)]
        if not problems and check:
            problems = check(parsed)
        if problems:
            raise BadReply("; ".join(problems)[:400])
        holder["parsed"] = parsed
        return response

    key = request_key(system, prompt, temperature, seed, models)
    for model in models:
        try:
            logged_call(
                lambda: call(model), stage=stage, item=item, model=model, params=params,
                seed=seed, key=key, measure=_token_counts,
            )
        except RuntimeError as err:
            print(f"{err}".splitlines()[0][:200] + " Trying the next model.")
            continue
        return holder["parsed"], model
    raise SystemExit(
        f"{stage}: no model could produce \"{item}\" ({', '.join(models)} all failed). "
        "Every attempt is in runs.jsonl. Run the command again later; finished work is cached."
    )
