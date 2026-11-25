# Ethics: consent, labelling and licences

This covers the film submitted for the assignment, `films/gebisa-ejeta`.

## Who appears, and consent

**No real person appears in the film, and no real person's voice is used.** No consent record was therefore needed, and none exists.

| Question | Answer | Where it is enforced |
|---|---|---|
| Is the subject a real, living person? | Yes. Gebisa Ejeta, born 1950. The Researcher found this from Wikidata and set the film's likeness policy to `no_likeness`. | `films/gebisa-ejeta/research/subject.json` |
| Is his face or likeness shown? | No. The pictures show feet on a path, hands, plants, soil, seed, fields and a medal. One picture shows an unnamed man from behind. | Picture prompts in `storyboard.json`; `visuals_problems` in `agents/story.py` rejects any picture prompt that names him |
| Is his voice used or imitated? | No. The narrator is a stock text-to-speech voice, "Sulafat", from Gemini. It was not made from any recording of a person. | `voice` in `storyboard.json` |
| Are words put in his mouth? | No. The narration speaks about him in the third person and contains no quotation. | `script_problems` in `agents/story.py` rejects quotation marks |
| Are other real people shown or voiced? | No. The narration names one other real person, President Biden, as the giver of an award. He is not shown or voiced. | `storyboard.json`, shot s10 |
| Does the film use private or family information? | No. Every fact comes from the three published pages listed below. Nothing private was sent to any service. | `films/gebisa-ejeta/research/` |

He has not been contacted and has not approved the film. It makes only claims that the sources below make.

## Sources for every claim

The narration may only use facts from `films/gebisa-ejeta/research/facts.json`. Each fact there quotes its source word for word, and code checked each quote against the source text.

| Source | Page | Licence |
|---|---|---|
| wikipedia | "Gebisa Ejeta", English Wikipedia, at the revision recorded in `source_wikipedia.json` | CC BY-SA 4.0. The article text is stored in this repo under that licence. |
| web1 | Purdue University news release, 14 October 2009: https://www.purdue.edu/uns/x/2009b/091014EjetaPrize.html | Copyright Purdue University. The text is not stored here; short passages are quoted as citations. |
| web2 | Purdue University news release, 11 June 2009: https://www.purdue.edu/uns/x/2009a/090611EjetaFoodprize.html | Copyright Purdue University. Same treatment. |

Each shot in `storyboard.json` lists the ids of the facts its line relies on, in `fact_ids`.

The narration was drafted by a language model from those facts and has not been reviewed by a subject expert. The Purdue pages are the university writing about its own professor, so they are not an independent source.

## Models and the licence of what they made

| Used for | Model | Runs on | Licence of the model | What that means for the output | How we know |
|---|---|---|---|---|---|
| Pictures | FLUX.2 klein 4B | Cloudflare Workers AI | Apache 2.0 | Pictures may be used, including commercially | The assignment brief states the licence; the 9B version is non-commercial and is not used |
| Voice | Gemini 3.8 Flash TTS, 3.8 Flash-Lite TTS, 3.1 Flash TTS preview | Gemini API | Proprietary; used under the Gemini API terms | Not checked in detail by us | Not verified: the terms still need to be read |
| Facts, script, picture prompts, music brief | Gemini 3.5 Flash | Gemini API | Proprietary; used under the Gemini API terms | Not checked in detail by us | Not verified, as above |
| Checking the narration audio | Gemini 3.5 Flash (transcription) | Gemini API | as above | Produces text used only as a check | |
| Score | ACE-Step 1.5 turbo | Kaggle GPU | MIT, code and weights | The model card says generated music may be used commercially | The project's repository and model card, read on 25 November 2026 |
| Moving shots | Wan 2.2 TI2V-5B | Kaggle GPU | Apache 2.0 | The model card says its makers claim no rights over generated content; the user is responsible for how it is used | The model card and repository, read on 25 November 2026 |
| Camera moves, mixing, export | FFmpeg | this machine | LGPL/GPL | No claim on the output | |
| Subtitles and end card | Pillow, with its built-in font | this machine | MIT-CMU (Pillow) | No claim on the output | |

Free endpoints may use what is sent to them to improve their models. Only published facts and the film's own prompts were sent.

## Labelling

| Measure | Status |
|---|---|
| End card | Every export ends with a 2.5-second card reading "This film was made with AI." The storyboard schema rejects an end card that does not mention AI. |
| Platform label | When the film is posted, the platform's "AI-generated" or "altered content" label is to be switched on. Not yet done: the film has not been posted. |
| Watermarks and provenance data | Nothing in the pipeline removes or alters a watermark or provenance metadata on purpose. Audio and pictures are re-encoded when the film is assembled, which is ordinary editing; we have not tested whether an embedded watermark survives it. |
| Post text | The post will say in words that the pictures, voice and music were generated. |

## Style

Picture prompts describe qualities ("oil painting style with textured canvas grain, warm amber palette") and name no artist, studio or film. The Storyboard artist's instructions forbid naming one.

## Open items

- Read the Gemini API terms on ownership and permitted use of generated audio and text, and record the result above.
- Switch on the platform's AI label when posting, and record where and when.
