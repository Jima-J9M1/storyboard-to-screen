"""Builders for valid test data. Each test changes one thing and checks the result."""

from __future__ import annotations


def shot(n: int, duration_s: float = 7) -> dict:
    return {
        "id": f"s{n:02d}",
        "duration_s": duration_s,
        "size": "wide",
        "image_prompt": "a wide field of sorghum at dawn, low golden light",
        "use_reference": False,
        "motion_mode": "ken_burns",
        "motion_prompt": "slow push in, fixed horizon",
        "narration": {"en": "A line of narration."},
        "subtitle_en": "A line of narration.",
        "reason": "Shows the audience where the story begins.",
        "fact_ids": [],
        "seed": 1,
    }


def storyboard(shots: int = 9) -> dict:
    """A valid storyboard: 9 shots of 7 s plus a 3 s end card is 66 s."""
    return {
        "title": "Test film",
        "languages": ["en"],
        "voice": {"name": "Sulafat", "style": "calm, warm, unhurried"},
        "style_block": "warm, grainy, hand-painted look with soft morning light",
        "world_block": "Rural highland Ethiopia in the 1950s. Every person is Ethiopian, with deep brown skin, in white cotton shawls.",
        "reference_sheet": {"prompt": "style sheet of fields, hands and seed, warm grain", "seed": 1},
        "music": {
            "caption": "gentle acoustic texture, warm and unhurried, instrumental",
            "bpm": 70,
            "key": "D minor",
            "seeds": [1, 2, 3],
            "cues": [{"at_s": 0, "note": "texture enters"}],
        },
        "end_card": {"text": "This film was made with AI.", "duration_s": 3},
        "shots": [shot(n) for n in range(1, shots + 1)],
    }


def brief() -> dict:
    return {
        "title": "Test subject",
        "audience": "Young people at home, watching on a phone.",
        "feeling": "Pride that patient work can feed a country.",
        "languages": ["en"],
    }
