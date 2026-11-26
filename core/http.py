"""The one place HTTP requests are made."""

from __future__ import annotations

import json
import uuid
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

# Sent with every request. Deliberately generic: it carries no personal details.
USER_AGENT = "storyboard-to-screen-pipeline/0.1"


# 200 is "here it is". 201 is "created", which is how an API answers a request that made
# something new, such as a voice clip. Treating 201 as a failure threw away ten paid
# recordings (FAILURES.md, F8).
OK_STATUSES = (200, 201)


class HttpError(Exception):
    """A request failed. Carries the status and the start of the server's reply."""


def _read(request: urllib.request.Request, timeout_s: float) -> str:
    try:
        with urllib.request.urlopen(request, timeout=timeout_s) as response:
            status = response.status
            charset = response.headers.get_content_charset() or "utf-8"
            body = response.read().decode(charset, errors="replace")
    except urllib.error.HTTPError as err:
        body = err.read().decode("utf-8", errors="replace")[:300]
        raise HttpError(f"HTTP {err.code} from {request.host}: {body}") from None
    if status not in OK_STATUSES or not body.strip():
        # Some sites answer a script with "202" and an empty page instead of the content.
        raise HttpError(f"HTTP {status} from {request.host} with {len(body)} characters of content")
    return body


def _send(request: urllib.request.Request, timeout_s: float) -> Any:
    return json.loads(_read(request, timeout_s))


def get_json(url: str, params: dict | None = None, timeout_s: float = 30.0) -> Any:
    if params:
        url = f"{url}?{urllib.parse.urlencode(params)}"
    return _send(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout_s)


def get_bytes(url: str, timeout_s: float = 120.0) -> bytes:
    """Fetch a file."""
    request = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(request, timeout=timeout_s) as response:
        return response.read()


def get_text(url: str, timeout_s: float = 30.0) -> str:
    """Fetch a page and return its body as text."""
    return _read(urllib.request.Request(url, headers={"User-Agent": USER_AGENT}), timeout_s)


def post_json(url: str, body: dict, headers: dict | None = None, timeout_s: float = 120.0) -> Any:
    """POST a JSON body. Keys go in headers, never in the URL, so they cannot end up in a log."""
    request = urllib.request.Request(
        url,
        data=json.dumps(body).encode("utf-8"),
        headers={"User-Agent": USER_AGENT, "Content-Type": "application/json", **(headers or {})},
        method="POST",
    )
    return _send(request, timeout_s)


def post_multipart(url: str, fields: dict[str, str], files: dict[str, tuple[str, bytes, str]] | None = None,
                   headers: dict | None = None, timeout_s: float = 180.0) -> Any:
    """POST a form with optional files and return the JSON reply.

    files maps a field name to (file name, content, content type).
    """
    boundary = uuid.uuid4().hex
    parts: list[bytes] = []
    for name, value in fields.items():
        parts.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n'.encode("utf-8"))
    for name, (filename, content, content_type) in (files or {}).items():
        parts.append(
            f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"; filename="{filename}"\r\n'
            f"Content-Type: {content_type}\r\n\r\n".encode("utf-8") + content + b"\r\n"
        )
    parts.append(f"--{boundary}--\r\n".encode("utf-8"))
    request = urllib.request.Request(
        url, data=b"".join(parts), method="POST",
        headers={"User-Agent": USER_AGENT, "Content-Type": f"multipart/form-data; boundary={boundary}", **(headers or {})},
    )
    return _send(request, timeout_s)
