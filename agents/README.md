# The crew

These agents are the story half of the system. They turn a film's `brief.json` into its `storyboard.json`.
Each one is run for a named film: `python -m agents.researcher --film gebisa-ejeta`.
The film half (`pipeline/`) then renders the storyboard with no agent involved.

## Rules every agent follows
- It reads the film's `brief.json`, `research/` and current storyboard, and writes only the fields it owns.
- Every model call goes through `core.llm.generate_json`, so it is retried, falls back to the next model, and is logged to `runs.jsonl`.
- Its instructions are a text file in `agents/prompts/`, so a prompt change is visible in a diff.
- Its output is validated against `schema/` before it is saved.
- Its work is cached by input hash, so the same brief gives the same storyboard without a new call.
- It proposes; the director approves. Nothing an agent writes is final until the gate is passed.

## Who owns what

| Agent | Module | Owns | Status |
|---|---|---|---|
| Researcher | `agents/researcher.py` | the film's `research/`: sources, subject, likeness policy, facts | Built |
| Screenwriter | `agents/story.py`, `prompts/screenwriter.md` | each shot's `narration`, `subtitle_en`, `fact_ids`; durations follow from the word count | Built |
| Storyboard artist | `agents/story.py`, `prompts/storyboard_artist.md` | `style_block`, `world_block`, `reference_sheet`, and each shot's `size`, `image_prompt`, `motion_prompt`, `reason` | Built |
| Composer | `agents/story.py`, `prompts/composer.md` | `music` | Built |
| Translator | `agents/story.py`, `prompts/translator.md` | each shot's `narration` in every language other than English | Built |

| Reviser | `agents/reviser.py`, `prompts/reviser.md` | whichever single field the director's note is about: one shot's picture, line or motion, or the film's score brief, look or world | Built |

Order: Researcher → Screenwriter → Storyboard artist → Composer → Translator. The Reviser runs afterwards, whenever the director gives a note.

## Directing with a note
The director looks at what a stage made and writes what is wrong and how to fix it. The Reviser rewrites the one field that produced it, under the same rules the first draft was held to, and the stage remakes that one item. Each note is appended to `films/<name>/direction.jsonl` with the text before and after.

```
python -m agents.reviser --film gebisa-ejeta --target picture --shot s08 --note "There are three hands. Show only two."
python -m agents.reviser --film gebisa-ejeta --target picture --shot s08 --reroll
```

The film's rules outrank a note. Asked for boots on a runner the film's world block says is always barefoot, the Reviser kept the feet out of the picture and said why.

The director owns `storyboard.json`. The agents write it only when the film has none; after that a new draft goes to `storyboard.draft.json` and never overwrites the director's edits.

## Not to be confused with
`.claude/agents/` holds the checkers (`grader`, `stranger`, `story-editor`, `art-director`).
Those are Claude Code subagents used while building. They review work and are never part of a run.
Claude Code only loads them from that folder, which is why they are not here.
