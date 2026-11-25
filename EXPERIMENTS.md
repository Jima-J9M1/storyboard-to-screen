# Experiments

Each entry: the hypothesis, what was changed, the result, and the decision. Evidence is in `runs.jsonl` and the files named.

## E1. Does a second source give the story enough concrete detail?

**Date:** 24 November 2026

**Hypothesis.** The Wikipedia article alone is too thin for a 60–90 second film. Adding the university's own news releases will give facts a film can show: names, dates and numbers.

**Change.** Added two Purdue University news pages to `sources` in the film's `brief.json`. The Researcher was extended to read extra pages and to record which source each fact quotes.

**Result.**

| | Wikipedia only | Wikipedia + 2 Purdue pages |
|---|---|---|
| Facts | 13 | 19 |
| Facts about the striga discovery | 1 | 4 |
| Facts that contain a number (a date, a distance, a quantity) | 6 | 11 |
| Model that answered | gemini-3.5-flash | gemini-3.5-flash |

New facts include the name of the hybrid (Hageen Dura-1), yields up to 150 percent higher, about 1 million acres grown in Sudan each year, and eight tons of seed sent to twelve African nations in 1994.
All 19 quotes passed the word-for-word check against the source they name.

**Decision.** Keep both extra sources. The Screenwriter will work from the 19-fact list.

**Limits of this comparison.** Two things changed between the runs, not one: the sources, and the prompt, which gained a line asking for concrete detail. So the rise from 6 to 11 facts with a number cannot be credited to the sources alone. The four striga facts all quote the Purdue pages, so those do come from the new sources.

**Evidence.** The 13-fact list is in git at commit `c6936ee`, file `research/gebisa-ejeta/facts.json` (its path before films got their own folders). The 19-fact list is `films/gebisa-ejeta/research/facts.json`. `runs.jsonl`, stage `research`, items `web1`, `web2` and `facts`.

## E2. How should the narrator's style be given to the voice model?

**Date:** 25 November 2026

**Hypothesis.** A short style instruction ("calm, warm, unhurried") will set the tone of the voice without changing what is said.

**Change.** One line, one voice (Sulafat), one model (`gemini-3.8-flash-lite-tts`). Only the way the style is given changed. Each result was measured, and transcribed by `gemini-3.5-flash` to see what a listener hears.

The line, 14 words: "In 1994, eight tons of his resistant seeds were distributed to twelve African nations."

| Variant | How the style was given | Length | Words a second | What was heard |
|---|---|---|---|---|
| A | `Say in a calm, warm, unhurried voice: <line>` | 12.60 s | 1.11 | the instruction, then the line |
| B | `Say in a calm, warm voice: <line>` | 10.12 s | 1.38 | not transcribed |
| C | `Say in a warm and clear voice, at a natural documentary pace: <line>` | 12.44 s | 1.13 | not transcribed |
| D | no style, the line only | 6.88 s | 2.03 | not transcribed |
| E | style as a system instruction | failed | | HTTP 400: developer instruction is not enabled for this model |
| F | `[calm, warm, unhurried] <line>` | 7.88 s | 1.78 | the line only |
| G | no style, the line only (repeat of D) | 6.96 s | 2.01 | the line only |

**Result.** The hypothesis was wrong for the sentence form. In variant A the model read the instruction aloud: the transcript begins "Say in a calm, warm, unhurried voice." The extra 5.6 seconds over variant D is the instruction being spoken, not a slower pace. Variants B and C are also several seconds longer than D, which fits the same cause, but they were not transcribed.
In square brackets (F) the style is not spoken, and the line is 0.9 s longer than with no style (G), so the style does slow the voice a little.

**Decision.** The voice stage sends `[style] line`. It now transcribes every file it makes and compares the transcript with the line, so a spoken instruction or a cut-off line is reported automatically.

**Limits.** One line and one take per variant. The transcriber wrote "resistance" for "resistant" in F, so a transcript is a check on length and content, not proof of every word.

**Evidence.** `runs.jsonl`, stage `experiment`, items `E2-A` to `E2-G` and `E2-transcript`. The check is `heard_problem` in `pipeline/narration.py`.

## E3. Is 2.3 words a second the right planning figure for this narrator?

**Date:** 25 November 2026

**Hypothesis.** The assignment's tip says spoken narration runs at 2 to 2.5 words a second, so the Screenwriter planned shot lengths at 2.3.

**Change.** Spoke all ten lines of the first draft (158 words) with the film's voice and style, and measured every file.

**Result.** 86.8 seconds of speech: 1.82 words a second, slower than planned. 9 of the ten lines did not fit their shots. Laid end to end with a 0.4 s gap, the film needs 94.5 seconds against the 82 planned, which is over the 90-second limit.

**Decision.** The Screenwriter now plans at 1.95 words a second, the rate of the first full recording, and its word limit dropped from 130-190 to 110-155. The first draft has to be cut by about fifteen words. That is the director's edit.

**Limits.** The 1.95 figure came from a recording in which two lines were spoken by a stand-in voice (FAILURES.md, F5). With all ten lines in the film's voice the rate is 1.82, so the planning figure is slightly generous and should be lowered if the next draft still overruns.

**What it shows.** The suggested practice "time the narration first" was right. Had pictures been generated for the 82-second plan, every shot length would have been wrong.

**Evidence.** `films/gebisa-ejeta/outputs/narration/timings.json`. `runs.jsonl`, stage `narration`.

## E4. Does guiding every picture with the reference sheet keep the look consistent?

**Date:** 25 November 2026

**Hypothesis.** The suggested practice is to make a reference sheet first and generate every keyframe against it. Passing the sheet to the picture model as a guide image should give ten different scenes in one style.

**Change.** Model `flux-2-klein-4b`, each shot's own seed, the same style block on every prompt. Shots s01 (bare feet on a path) and s06 (a field of sorghum) were each generated three ways, changing only how the reference sheet was used.

| Variant | Reference sheet | Prompt wording | s01 result | s06 result |
|---|---|---|---|---|
| A | guide image | "same style as the reference, but a new scene; do not copy its composition" | a copy of the sheet: field and glass flasks, no feet | a copy of the sheet, flasks included |
| B | guide image | "a completely different scene; take only palette and brush texture" | the sheet's field with a walking figure added, drawn without a head | a copy of the sheet with a bluer sky |
| C | not passed | style block only | feet on a dirt path, as asked | a field of grain, as asked |

**Result.** For wide landscape shots the guide image overrode the prompt, and stronger wording (B) did not stop it. With no guide image (C) both pictures showed what was asked, and their palette, light and brushwork still matched the other shots, because the style block carries the look.
The six close and medium shots, generated with the guide image (variant A wording), each showed their own scene. So the copying is specific to prompts that, like the sheet, describe a wide landscape.

**Decision.** Each shot now has a `use_reference` field in the storyboard. The Storyboard artist's draft sets it to false for wide shots and true for the rest, and the director can change it per shot. Four wide shots were regenerated; the other seven pictures were reused from cache.

**What it shows.** The suggested practice helped for close and medium shots and hurt for wide ones. Applied to every shot, as suggested, it produced two unusable pictures out of ten.

**Limits.** Judged by eye from a contact sheet, by the agent that built the stage, with one seed per variant. Consistency was not measured with a number.

**Evidence.** `runs.jsonl`, stage `experiment`, items `E4-s01-B`, `E4-s01-C`, `E4-s06-B`, `E4-s06-C`; stage `keyframes` for variant A and the final pictures. The pictures are in `films/gebisa-ejeta/outputs/keyframes/`.

## E5. Can ACE-Step 1.5 run without its planner model on a free T4?

**Date:** 25 November 2026

**Hypothesis.** ACE-Step 1.5 has two parts: a language-model "planner" that decides tempo, key and structure, and the audio model. Our storyboard already states the tempo and key, so the planner should not be needed. Skipping it should save GPU memory and time on a 15 GB Tesla T4. The documentation does not say whether the audio model runs without it.

**Change.** The Kaggle job created the planner object but never loaded a model into it, and set `thinking=False`. It was written to load the smallest planner (0.6B) and retry if generation refused to run.

**Result.** Generation ran without the planner on the first try; the retry was never used. Three 90-second instrumental candidates at 8 steps:

| Seed | Time to generate |
|---|---|
| 1 | 11.3 s |
| 2 | 8.0 s |
| 3 | 8.1 s |

Loading the audio model took 41.5 s, and the whole job 176 s, of which 75 s was building the Python environment.

**Decision.** Keep the planner unloaded. Three candidates cost under three GPU minutes; the cost of the music stage is the wait in Kaggle's queue (48 minutes on the first attempt), not the generation.

**Limits.** This shows the model runs and how long it takes. Whether the candidates follow the requested 78 bpm and A major, or are any good, has not been measured: that needs ears. No run with the planner was made, so its effect on quality is unknown.

**Evidence.** `films/gebisa-ejeta/outputs/music/job_report.json`. `runs.jsonl`, stage `music`.

## E6. Do the pictures need to be told who the people are and where the story happens?

**Date:** 25 November 2026

**Why.** The director looked at the first set of pictures and saw that the people did not look Ethiopian: light-skinned hands, a man in a T-shirt and jeans, grain that looked like wheat. The film is about an Ethiopian scientist and is made for Ethiopian viewers.

**Hypothesis.** The picture model fills in people, dress, buildings and crops from its own defaults unless it is told. A "world block" in the storyboard, saying who the people are and what their world looks like, added to every picture prompt, will fix this.

**Change.** Same model, seeds, style block and picture descriptions. Only the world block was added, in two wordings.

| Version | How the world block was worded | Result across the ten shots |
|---|---|---|
| Before | none | Light or tan hands in four shots; modern Western clothes in one; wheat-like grain; no Ethiopian buildings |
| v1 | A plain description: "Every person is Black, Ethiopian ... Villagers wear white cotton shawls ... Homes are round thatched huts ..." | People, dress, huts and sorghum all looked right. But groups of villagers and huts appeared in nearly every picture, including the laboratory beaker shot, the cracked dry soil, the roots and the medal. The shots stopped showing their own subjects. |
| v2 | Conditional rules: "Any person is ...", "Any village home is ...", "Any sorghum has ...", with the instruction to show only what the shot describes | Each shot showed its own subject again, with deep brown skin, white gabi shawls, tukul huts and reddish-brown sorghum heads wherever those appeared. |

Three shots still needed their own descriptions reworded after v2: the feet were drawn sole-up on the ground, the pencil shot showed faces, and the medal sat among huts. With clearer descriptions (a boy walking away seen from behind; hands only, no faces; indoors in a hall) all three came out as asked.

**Decision.** `world_block` is now a required field of the storyboard, written as conditional rules. The Storyboard artist drafts it from the researched facts, and its instructions explain why it must be conditional. The picture stage wraps it in "show only what is described".

**What it shows.** A description is read by the picture model as a list of things to paint. To change how things look without changing what is shown, it has to be phrased as a rule.

**Limits.** Judged by eye from contact sheets by the agent that built the stage; one seed per shot. Whether the dress and buildings are right for 1950s Oromia in detail needs someone who knows, and the director is the first check.

**Evidence.** `films/gebisa-ejeta/outputs/keyframes/contact_sheet_before_world_block.jpg`, `contact_sheet_world_block_v1.jpg` and `contact_sheet.jpg`. `runs.jsonl`, stage `keyframes`, 25 November.

## E7. Can a stranger rebuild the film from a clean clone, with no keys?

**Date:** 25 November 2026

**Hypothesis.** Because the pictures, narration and score are committed together with a record of the inputs each was made from, a fresh clone should rebuild the film with one command, without any API key and without calling a model.

**Change.** Cloned the public repository into an empty folder. Confirmed there was no `.env`. Removed every API key from the environment and ran `make film`.

**Result.**

| Check | Result |
|---|---|
| Command finished | Yes, in 61.7 seconds, including creating the Python environment |
| Narration | 0 lines spoken, 10 reused |
| Pictures | 0 made, 11 reused |
| Score | no job sent; 3 candidates reused |
| Clips | 20 rebuilt locally by FFmpeg |
| Film | recognised as up to date: the rebuilt clips were byte-for-byte what the committed film was cut from |
| Lines in `runs.jsonl` | 165 before, 165 after: no outside call was made |
| Files changed in the clone | none |

**Decision.** Keep committing the generated pictures, audio and cache manifests. The hours-long video job was taken out of `make film` after this test showed it would otherwise be attempted on every clean run; it stays a separate command.

**Limits.** Run on the same machine that built the film, so the same FFmpeg and Python versions. A different FFmpeg may encode the clips differently; the film would then be re-cut, which takes a few more minutes but still needs no key. The production board was not part of this test.

**Evidence.** The commands are in the README. The run log's line count is the check anyone can repeat.

## E8. Does the pipeline work in Amharic, and where do the models fail?

**Date:** 25 November 2026

**Hypothesis.** The same pipeline can make a film narrated in Amharic with English subtitles: a Translator agent turns the English script into Amharic, the Gemini voice model speaks it, and the transcript check that guards the English narration will guard the Amharic one too.

**Change.** A second film, `films/abebe-bikila`, with `"languages": ["am"]` in its brief. Nothing else about the pipeline was changed for it except what the language required: a Translator agent, and a word counter that recognises Ge'ez letters.

**Result.**

| Step | What happened |
|---|---|
| Translation | Ten English lines came back as ten Amharic lines in Ge'ez script on the first attempt, with years written out as words as instructed. One word in shot s05 looks like a misspelling to a non-speaker; unverified. |
| Voice | Eight of ten lines recorded before the daily quota ran out (FAILURES.md, F7). |
| Speed | 1.57 words a second, against 1.91 for the English film. Amharic words are longer, so the English planning figure does not carry over. |
| Timing | The storyboard's shot lengths, estimated from the English lines, are too short for three of the eight recorded lines. Shot s04 was planned at 8.5 s and takes 11.3 s. |
| Transcript check | It flagged two of eight lines, both wrongly: the transcriber wrote years and dates as digits ("1964") where the line has them as words, so the word counts differ. |
| Transcript agreement | Comparing words, not counts: in one line 11 of 12 words matched, but in three lines only about half did. For example the line begins "አንድ ወጣት በሮም" and the transcript begins "አንድ ሁለቱ ባዶም". |

**What this does and does not show.** The pipeline runs in Amharic end to end as far as the voice. But the automatic check that made the English narration trustworthy does not work here. When the transcript disagrees with the line, there is no way to tell from text alone whether the voice mispronounced the line or the transcriber misheard correct speech. Both models are weaker in Amharic than in English, and the check assumes at least one of them is reliable.

**Decision.** For Amharic, a person who speaks the language must listen to every line; the transcript check is kept only as a warning for missing or extra speech. Shot lengths are always set from the recorded audio (`--fit`), never from the English estimate. The planning rate for Amharic is 1.57 words a second.

**Limits.** Eight lines, one voice, one transcriber. No Amharic speaker has yet listened, so the quality of the narration itself is unknown. That listening is the missing half of this experiment.

**Evidence.** `films/abebe-bikila/outputs/narration/timings.json` holds, for each line, its length, the model that spoke it and the transcript. `films/abebe-bikila/storyboard.json` holds the lines. `runs.jsonl`, stages `story` and `narration`, film `abebe-bikila`.

## E9. Gemini or Addis AI for Amharic narration?

**Date:** 25 November 2026

**Hypothesis.** Addis AI is built for Ethiopian languages and should narrate Amharic better than a general model. Its site says so; that is the company's claim, not evidence.

**Change.** The same Amharic lines of the Abebe Bikila film were spoken by both. Gemini: voice "Sulafat", style "calm, warm, unhurried", free tier. Addis AI: voice "am-yohanes-calm" ("Low-key reflective tone"), paid by the minute. Nothing else differed.

**Result so far: what can be measured.**

| | Gemini | Addis AI |
|---|---|---|
| Lines recorded | 8 of 10 (daily quota ran out) | 10 of 10 |
| Time for the 8 lines both recorded | 65.7 s | 61.4 s |
| Speed on those lines | 1.57 words a second | 1.68 words a second |
| Models used | three, as each hit its limit | one |
| Cost | none | 6.22 birr for ten lines (74.6 s of audio) |
| Calls refused | 95 voice calls refused that day across both films | none |

| Shot | Words | Gemini (s) | Addis AI (s) |
|---|---|---|---|
| s01 | 10 | 5.48 | 4.98 |
| s02 | 12 | 7.23 | 7.04 |
| s03 | 9 | 7.66 | 6.83 |
| s04 | 17 | 11.29 | 10.7 |
| s05 | 13 | 9.02 | 7.84 |
| s06 | 16 | 8.13 | 8.31 |
| s07 | 9 | 7.34 | 7.81 |
| s08 | 17 | 9.54 | 7.93 |

**What has not been measured: which one sounds right.** That is the question that matters, and no number here answers it. The machine transcript cannot judge Amharic (E8); on shot s10 it returned text in the wrong script altogether. Both sets of recordings are kept under `films/abebe-bikila/outputs/voice_compare/` and play side by side on the production board's Voice stage, so the director and Amharic-speaking viewers can choose.

**Decision for now.** The film uses the Addis AI voice, for a practical reason and not a quality one: it could record all ten lines, with one voice, on the day. The choice will be revisited after people have listened.

**To finish this experiment.** Play both sets to at least five Amharic speakers without saying which is which, and record which they prefer and where either mispronounces a name, a place or a number.

**Evidence.** `films/abebe-bikila/outputs/voice_compare/gemini/timings.json` and `addis/timings.json`. `runs.jsonl`, stage `narration`, film `abebe-bikila`: the Addis AI lines record the birr charged for each.

## E10. Can a free 15 GB GPU turn the pictures into real video?

**Date:** 25 November 2026

**Why.** The first viewers of the rough cut said it was not real video: nothing in the pictures moved. The film was using slow camera moves over stills, the fallback the assignment allows.

**Hypothesis.** Wan 2.2 TI2V-5B can animate the pictures on Kaggle's free Tesla T4, although its documentation asks for a 24 GB GPU, if the resolution is lowered to 480p and the model's two large parts are never on the GPU together.

**Change.** Two runs of the same job on the same ten pictures, motion prompts and seeds: 480 x 832, 81 frames, 25 steps. Only the way the model was placed in memory changed.

| Run | How the model was placed on the GPU | Result |
|---|---|---|
| 1 | The library's standard memory saver, which swaps whole parts in and out | Out of memory on the first clip, at 81, 49 and 33 frames. Peak 15.46 GB. The job ended after 6 minutes. |
| 2 | The text encoder goes on alone, encodes all ten prompts (peak 13.43 GB), and is deleted. Only then the video model and decoder go on (12.86 GB before generating). | 11 clips made. Peak 14.93 GB while generating. |

**Measurements from run 2.**

| | |
|---|---|
| Time per clip | 12.6 minutes, the same for every clip |
| Clip | 81 frames at 24 frames a second: 3.4 seconds |
| GPU session | 145 minutes: 5 minutes loading the model, then 11 clips |
| Clips made | all 10 tall clips and 1 wide clip, before the time budget stopped it |
| Change between a clip's first and last frame (0 = a still picture, 255 = everything changed) | from 3.4 (the man standing in the field) to 32.0 (seed pouring from hands) |

Frames taken from four clips showed the motion that was asked for: feet stepping forward, seed pouring, a fire flickering, sorghum swaying. The painted style of the pictures was kept.

**Decision.** Generated video is now the normal path for a shot marked `video`, with the camera move as the fallback. Because a clip takes 12.6 minutes, the tall and the wide clips are sent as two jobs at once.

**Limits.** The clips were checked by looking at three frames each and by the frame-difference number; nobody has watched them play. Two shots barely moved (3.4 and 3.9), so "generated" does not always mean "moving". The peak of 14.93 GB leaves almost no room on a 15.36 GB card, so a larger frame or more frames would not fit. These clips were made from the first set of pictures, before the people were repainted (E6), so the job was run again for the film.

**The run for the film.** The job was then run on the repainted pictures as two jobs at once, one per shape. Both made all ten clips with no retries: the tall job in 130 minutes (12.4 minutes a clip), the wide job in 144 minutes (13.7 minutes a clip). The change between first and last frame ranged from 4.8 (the dry soil) to 35.0 (the harvest bundle). All ten shots of the film now use generated video in both shapes; none fell back to a camera move.

**Evidence.** `films/gebisa-ejeta/outputs/video/job_report-9x16.json` and `job_report-16x9.json` for the film's clips. `films/gebisa-ejeta/outputs/video_first_run/job_report.json` has the settings, time and peak memory for every clip of the first full run. `films/gebisa-ejeta/outputs/video/job_reports.json` keeps the failed run as well. `runs.jsonl`, stage `video`.
