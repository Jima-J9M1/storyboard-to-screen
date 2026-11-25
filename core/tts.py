"""Speech for the narration, from one of two providers, with a local stand-in for rough cuts.

    gemini  Gemini text-to-speech. Free tier, about three dozen lines a day. Takes a style.
    addis   Addis AI "Addis Voices 2". Built for Amharic, Afaan Oromo and Tigrinya. Paid by
            the minute of audio (5 birr a minute when this was written). Ignores the style.

The storyboard's `voice` says which provider and which voice a film uses.


With Gemini, speak() tries each voice model in turn, waiting and retrying when one says it is being
called too often. The caller is told which model spoke, and that is saved with the audio.

A film must have one narrator, so a different voice is never substituted silently. Only when
the caller asks for a rough cut does speak() fall back to the Mac's built-in `say` voice.

Whatever the source returns, the result is written as the same kind of file:
24 kHz, mono, 16-bit WAV. Every later stage can rely on that.
"""

from __future__ import annotations

import base64
import shutil
import subprocess
import tempfile
from pathlib import Path

from core import env, http
from core.llm import API_URL, worth_retrying
from core.runlog import logged_call

# Tried in order. The two newest answer in a few seconds; the older ones are slower.
VOICE_MODELS = ["gemini-3.8-flash-tts", "gemini-3.8-flash-lite-tts", "gemini-3.1-flash-tts-preview"]
TRANSCRIBERS = ["gemini-3.5-flash", "gemini-3.5-flash-lite", "gemini-3.8-flash"]
LOCAL_VOICE = "macos-say"
# The free tier allows only a few voice calls a minute. A refused call is tried again after
# these waits, which is long enough for the per-minute limit to clear.
RATE_LIMIT_WAIT_S = 20.0

ADDIS_URL = "https://api.addisassistant.com/api/v1/voice/generations"
ADDIS_ETB_PER_MINUTE = 5.0     # the price the API reported on 25 November 2026
ADDIS_USD_PER_MINUTE = 0.032   # the same price as listed in US dollars on the provider's pricing page


# Models that refused every attempt with "quota exceeded" during this run. A daily quota does
# not come back in a minute, so they are skipped for the remaining lines instead of being
# waited on again for each one.
_spent: set[str] = set()


class VoiceUnavailable(Exception):
    """No voice model could speak a line. Finished lines stay cached; run again later."""
SAMPLE_RATE = 24000


def _to_wav(raw: bytes, mime: str, out: Path) -> None:
    """Convert whatever audio came back into 24 kHz mono 16-bit WAV."""
    out.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(suffix=".bin") as tmp:
        tmp.write(raw)
        tmp.flush()
        # Raw PCM ("audio/L16;rate=24000") has no header, so ffmpeg must be told its shape.
        headerless = any(mark in mime.lower() for mark in ("l16", "pcm"))
        shape = ["-f", "s16le", "-ar", "24000", "-ac", "1"] if headerless else []
        subprocess.run(
            ["ffmpeg", "-y", "-loglevel", "error", *shape, "-i", tmp.name,
             "-ar", str(SAMPLE_RATE), "-ac", "1", "-c:a", "pcm_s16le", str(out)],
            check=True, capture_output=True,
        )


def _gemini(model: str, text: str, voice: str, style: str, api_key: str) -> tuple[bytes, str, dict]:
    body = {
        # The style goes in square brackets. Written as a sentence ("Say in a calm voice: ...")
        # these models read the instruction aloud. See EXPERIMENTS.md, E2.
        "contents": [{"parts": [{"text": f"[{style}] {text}"}]}],
        "generationConfig": {
            "responseModalities": ["AUDIO"],
            "speechConfig": {"voiceConfig": {"prebuiltVoiceConfig": {"voiceName": voice}}},
        },
    }
    response = http.post_json(API_URL.format(model=model), body, headers={"x-goog-api-key": api_key})
    try:
        part = response["candidates"][0]["content"]["parts"][0]["inlineData"]
    except (KeyError, IndexError):
        raise RuntimeError(f"no audio in the reply from {model}") from None
    return base64.b64decode(part["data"]), part["mimeType"], response.get("usageMetadata", {})


def _addis(text: str, voice: str, language: str, request_id: str, api_key: str) -> tuple[bytes, dict]:
    """One line from Addis AI. The request id makes a retry return the same clip instead of charging twice."""
    reply = http.post_json(
        ADDIS_URL,
        {"text": text, "voice_id": voice, "language": language, "output_format": "wav_44100",
         "client_request_id": request_id},
        headers={"x-api-key": api_key},
    )
    data = reply.get("data") or {}
    inline = data.get("audio") or ""
    if inline.startswith("data:") and "base64," in inline:
        raw = base64.b64decode(inline.split("base64,", 1)[1])
    elif data.get("audio_url"):
        raw = http.get_bytes(data["audio_url"])
    else:
        raise RuntimeError(f"no audio in the reply from Addis AI: {str(reply)[:200]}")
    return raw, data


def speak_addis(text: str, out: Path, *, voice: str, language: str, stage: str, item: str, key: str) -> str:
    api_key = env.require("ADDIS_API_KEY")
    model = f"addis-voices-2:{voice}"

    def call() -> dict:
        raw, data = _addis(text, voice, language, f"heritage-{key}", api_key)
        _to_wav(raw, "audio/wav", out)
        return data

    def measure(data: dict) -> dict:
        seconds = data.get("duration_seconds") or 0
        usage = data.get("usage") or {}
        return {"cost_usd": round(seconds / 60 * ADDIS_USD_PER_MINUTE, 5),
                "cost_etb": usage.get("credits_used"), "balance_etb": usage.get("credits_remaining"),
                "billed_seconds": seconds}

    try:
        logged_call(call, stage=stage, item=item, model=model, key=key,
                    params={"voice": voice, "language": language, "chars": len(text)}, measure=measure)
    except RuntimeError as err:
        raise VoiceUnavailable(f"Addis AI could not speak {item}: {str(err).splitlines()[0][:200]}") from None
    return model


def transcribe(path: Path, *, stage: str, item: str) -> str:
    """Return the words a listener hears in an audio file, written down by a language model.

    No agent can listen, so this is how the pipeline checks that a narration file says its
    line and nothing else.
    """
    api_key = env.require("GEMINI_API_KEY")
    body = {
        "contents": [{"parts": [
            {"text": "Transcribe this audio exactly, word for word. Return only the transcript."},
            {"inlineData": {"mimeType": "audio/wav", "data": base64.b64encode(path.read_bytes()).decode()}},
        ]}],
        "generationConfig": {"temperature": 0},
    }
    for model in TRANSCRIBERS:
        try:
            response = logged_call(
                lambda model=model: http.post_json(API_URL.format(model=model), body, headers={"x-goog-api-key": api_key}),
                stage=stage, item=item, model=model, params={"task": "transcribe"}, key=item, retry_if=worth_retrying,
            )
            parts = response["candidates"][0]["content"]["parts"]
            return "".join(part.get("text", "") for part in parts).strip()
        except (RuntimeError, KeyError, IndexError) as err:
            print(f"{str(err).splitlines()[0][:160]} Trying the next transcriber.")
    return ""


def _say(text: str, out: Path) -> None:
    with tempfile.NamedTemporaryFile(suffix=".aiff") as tmp:
        subprocess.run(["say", "-o", tmp.name, text], check=True, capture_output=True)
        _to_wav(Path(tmp.name).read_bytes(), "audio/aiff", out)


def speak(text: str, out: Path, *, voice: str, style: str, stage: str, item: str, key: str,
          allow_local: bool = False, provider: str = "gemini", language: str = "en") -> str:
    """Write `text` as speech to `out` and return the name of the model that spoke it.

    allow_local  for a rough cut only: use the Mac's own voice if every model fails
    provider     "gemini" or "addis"
    """
    if provider == "addis":
        return speak_addis(text, out, voice=voice, language=language, stage=stage, item=item, key=key)
    api_key = env.require("GEMINI_API_KEY")
    params = {"voice": voice, "style": style, "chars": len(text)}

    for model in VOICE_MODELS:
        if model in _spent:
            continue
        def call(model=model):
            raw, mime, usage = _gemini(model, text, voice, style, api_key)
            _to_wav(raw, mime, out)
            return usage
        try:
            logged_call(
                call, stage=stage, item=item, model=model, params=params, key=key,
                base_delay_s=RATE_LIMIT_WAIT_S,
                measure=lambda usage: {"tokens_in": usage.get("promptTokenCount"),
                                       "tokens_out": usage.get("candidatesTokenCount")},
            )
            return model
        except RuntimeError as err:
            if "HTTP 429" in str(err):
                _spent.add(model)
            print(f"{str(err).splitlines()[0][:160]} Trying the next voice.")

    if allow_local and shutil.which("say"):
        logged_call(lambda: _say(text, out), stage=stage, item=item, model=LOCAL_VOICE,
                    params={"chars": len(text)}, key=key, attempts=1)
        return LOCAL_VOICE
    raise VoiceUnavailable(f"no voice model could speak {item} ({', '.join(VOICE_MODELS)} all failed)")
