"""Shared plumbing used by both halves of the system.

paths      where everything lives
files      JSON reading and writing
contracts  validation of brief.json and storyboard.json
runlog     runs.jsonl logging and retried calls
cache      skip work whose inputs have not changed
http       the one place HTTP requests are made
"""
