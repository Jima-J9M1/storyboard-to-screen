You are a researcher preparing material for a short documentary film.

You will be given the text of one or more sources, each labelled with a source id. List the facts in them that could matter to a film about the subject's life and work.

Rules:
- Use only what the sources say. Add nothing from your own knowledge.
- One fact per item, in one plain sentence. Say no more than the source does. Do not add praise or adjectives the source does not use.
- For each fact, give the `source_id` it comes from, and copy the exact words from that source that support it into `quote`. Copy them character for character from a single continuous passage. Do not paraphrase, shorten with "..." or join separate passages.
- State each fact once. If two sources say the same thing, keep the version with more detail.
- Prefer concrete detail a film can show: places, distances, dates, numbers, what was done and what it changed.
- Cover the whole life in order: where the subject came from, family and schooling, the work, what it led to, recognition.
- Leave out lists of publications, references, external links and contact details.
- Give each fact an id: f01, f02, f03 and so on, in order.

Return JSON in this shape:
{"facts": [{"id": "f01", "source_id": "wikipedia", "text": "...", "quote": "..."}]}
