# Claude Code instructions

The shared rules for every coding agent are in AGENTS.md. Read them first:

@AGENTS.md

## Private files (git-ignored, present only on the director's machine)
- The full assignment brief: `The Heritage Short — Assignment Brief (10 Academy TRP).md` in the repo root.
- Our own stricter rubric: `.private/OUR_RUBRIC.md`.

Re-read the relevant part of the brief before each task, and score against the private rubric before calling a task done.
Never copy either file into a tracked file, and never commit them.

## Checker subagents (`.claude/agents/`)
Run these at the gates. They start with no context, so they do not read our work charitably.

| Agent | Run it |
|---|---|
| `story-editor` | before the radio cut, on any storyboard change |
| `art-director` | after keyframes are generated |
| `grader` | before each user test and before submission |
| `stranger` | before each user test and before submission |

## The director
The director is a learner on this course and will be interviewed about every decision.
Offer two or three options with a recommendation for creative and design choices, and explain why the code is shaped the way it is.
