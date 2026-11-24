"""runs.jsonl: one line per outside call, and the retry wrapper that writes them.

No stage calls a model or fetches data except through logged_call, so the log is complete
by construction: every attempt, failed or not, is on record with its latency and cost.
"""

from __future__ import annotations

import hashlib
import json
import time
from datetime import datetime, timezone
from typing import Any, Callable

from core import paths


def input_hash(*parts: Any) -> str:
    """Stable hash of a stage's inputs. Same inputs, same hash, on any machine."""
    canonical = json.dumps(parts, sort_keys=True, ensure_ascii=False, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()[:16]


def log_run(**fields: Any) -> None:
    """Append one line to runs.jsonl."""
    line = {"ts": datetime.now(timezone.utc).isoformat(timespec="seconds"), **fields}
    with paths.RUNS_PATH.open("a", encoding="utf-8") as f:
        f.write(json.dumps(line, ensure_ascii=False) + "\n")


def logged_call(
    fn: Callable[[], Any],
    *,
    stage: str,
    model: str,
    params: dict,
    key: str,
    seed: int | None = None,
    kind: str = "model",
    cost_usd: float = 0.0,
    item: str | None = None,
    attempts: int = 3,
    base_delay_s: float = 2.0,
    measure: Callable[[Any], dict] | None = None,
) -> Any:
    """Run one outside call, retrying with a doubling delay. Every attempt is logged.

    kind     "model" for a generative model call, "fetch" for a plain data fetch
    key      the input hash of the work, so a log line can be matched to a cache entry
    item     which unit of the stage this is, for example a shot id
    measure  optional: takes the result and returns extra fields to log, such as token counts
    """
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        record = dict(
            stage=stage, kind=kind, item=item, model=model, params=params,
            seed=seed, input_hash=key, attempt=attempt,
        )
        started = time.monotonic()
        try:
            result = fn()
        except Exception as err:  # any failure is logged, retried and finally re-raised
            last_error = err
            log_run(**record, latency_s=round(time.monotonic() - started, 3),
                    cost_usd=0.0, status="error", error=f"{type(err).__name__}: {err}")
            if attempt < attempts:
                time.sleep(base_delay_s * 2 ** (attempt - 1))
            continue
        log_run(**record, latency_s=round(time.monotonic() - started, 3),
                cost_usd=cost_usd, status="ok", **(measure(result) if measure else {}))
        return result
    raise RuntimeError(f"{stage}: {model} failed after {attempts} attempts: {last_error}")
