"""The one place HTTP requests are made."""

from __future__ import annotations

import json
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Sent with every request. Deliberately generic: it carries no personal details.
USER_AGENT = "heritage-short-pipeline/0.1"


class HttpError(Exception):
    """A request failed. Carries the status and the start of the server's reply."""


def _send(request: urllib.request.Request, timeout_s: float) -> Any:
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            return json.loads(response.read().decode("utf-8"))
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")[:300]
        raise HttpError(f"HTTP {err.code} from {request.host}: {body}") from None


def get_json(url: str, params: dict | None = None, timeout_s: float = 30.0) -> Any:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return _send(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout_s)


def post_json(url: str, body: dict, headers: dict | None = None, timeout_s: float = 120.0) -> Any:
    """POST a JSON body. Keys go in headers, never in the URL, so they cannot end up in a log."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    return _send(request, timeout_s)
