# Report: The Heritage Short

Repository: https://github.com/Jima-J9M1/storyboard-to-screen

Status of this report: a draft written on 25 November 2026 from the evidence in the repository. Two sections are marked as waiting on the director, because they record what people said and only the director can supply that.

## 1. What I set out to make, and for whom

A 60–90 second film about Gebisa Ejeta, the Ethiopian plant scientist who bred sorghum that survives drought and the parasitic weed striga.

- **Audience:** Ethiopian students and young graduates aged 16–25, watching on a phone on TikTok or Telegram.
- **Feeling at the end:** pride and possibility. Someone who started where I started changed how a continent eats.

Both were written into `DESIGN.md` and committed before anything was generated (commit `ee0d9f7`).

I also set out to build something more general than one film. The repository is a system that takes a title and produces a film: agents research the title and draft a storyboard, a person directs the storyboard, and code renders it. A second film, about Abebe Bikila and narrated in Amharic, was started through the same system to test that claim.

Gebisa Ejeta is a living person, so the film never shows his face, never imitates his voice and gives him no words. The Researcher works this out from Wikidata and the rule is enforced in code (`ETHICS.md`).

## 2. What I learned from my audience

**Waiting on the director.** The two user tests the assignment asks for (three people each, on the radio cut and on the near-final cut) are not yet recorded in `DESIGN.md`. This section must not be written from imagination.

What the repository can already show is two pieces of feedback and what each changed:

| What was said | By whom | What changed because of it |
|---|---|---|
| "This is not real video. There is no movement." | First viewers of the rough cut (names to be added) | The film used camera moves over still pictures, which the assignment allows as a fallback. A new stage was built to animate the pictures with Wan 2.2 on a Kaggle GPU (`pipeline/video.py`). Its first run failed for lack of GPU memory; the second made eleven clips, 12.6 minutes each, with the feet stepping, the seed pouring and the sorghum swaying (experiment E10, failure F9). |
| The people in the pictures do not look Ethiopian. | The director | The storyboard gained a `world_block` that says who the people are and what their world looks like. All ten pictures were repainted (experiment E6, commit `7296e5a`). |

## 3. The hardest problem, and how I solved it

**The agent that built the pipeline cannot hear or watch what it makes.**

Every check on the film had to be turned into something measurable in text. That mattered most with the narration:

1. The first recording of ten lines took 122 seconds, where the plan allowed about 70. It looked like slow speech.
2. Measuring the silence in each file ruled out padding. Speaking one line four ways, changing only the style instruction, showed the line took 6.9 seconds with no instruction and 12.6 with one.
3. Having a second model transcribe the audio gave the answer: the narrator was reading its own stage direction aloud. Every line began "Say in a calm, warm, unhurried voice."
4. Writing the style in square brackets fixed it. The same check then caught a second fault that sounded fine on paper: two of the ten lines had been spoken by a different voice, because a fallback had been used silently when the free tier refused calls.

The voice stage now transcribes every file it makes and compares it with its line, and it never substitutes a narrator (`FAILURES.md` F4 and F5; `EXPERIMENTS.md` E2).

The solution has a limit, and the second film found it. In Amharic the transcript and the script agree on only about half the words in some lines, and there is no way to tell from text whether the voice or the transcriber is wrong (E8). For Amharic a person has to listen.

## 4. Suggested practices, tested

**One that beat my instinct: time the narration before making pictures.**
The Screenwriter planned shot lengths at 2.3 words a second, the middle of the range the assignment quotes. The recorded narration ran at 1.82. Seven of ten lines did not fit their shots, and the film needed 94.5 seconds against a 90-second limit. Had pictures and clips been made to the planned lengths, every one would have been wrong. Because the narration came first, the fix was to trim silence and set each shot's length from its recorded line, which brought the film to 89.5 seconds without cutting a word (E3; `films/gebisa-ejeta/outputs/narration/timings.json`).

**One that did not: generate every keyframe against the reference sheet.**
With the reference sheet passed to the picture model as a guide image, the two wide landscape shots came back as copies of the sheet, glass flasks included, instead of bare feet on a path and a field of sorghum. Stronger wording did not stop it. With no guide image the same shots showed what was asked, and the style block alone kept the look consistent. Each shot now has a `use_reference` setting, off for wide shots and on for close and medium ones (E4). Applied to every shot, as suggested, the practice produced two unusable pictures out of ten.

## 5. Work beyond the floor

**A tool for others, not one film.** Films live in their own folders, every command takes a film's name, and a new film starts from a title (`make new`). A production board (Next.js) shows every film and, for each stage, exactly what that stage made. A clean clone with no API keys rebuilt the film in 62 seconds with zero model calls: the run log had 165 lines before and after (E7).

**A second language, and where the models fail.** The Abebe Bikila film was scripted in English, translated to Amharic by a Translator agent, and voiced by the same model. What this showed (E8):
- Amharic is spoken at 1.57 words a second against 1.91 for English, so timing cannot be carried over from the English script.
- The automatic check on the narration does not work in Amharic, as described above.
- The free voice quota is about three dozen lines a day. It ran out with two of ten Amharic lines left, so that film is unfinished (F7).

**A picture model's defaults.** Left alone, the model painted light-skinned hands, Western clothes and wheat. Told plainly who the people were, it put villagers into every picture, including a laboratory shot. Told as conditional rules ("any person is…"), it got both right (E6). The insight is that a picture model reads a description as a list of things to paint.

## 6. What it cost

Nothing was paid. `COSTS.md` is generated from the run log.

| | |
|---|---|
| Attempts at outside calls | 313, of which 147 succeeded |
| Refused for quota or rate limit | 108 |
| Refused because a model was overloaded | 43 |
| GPU time for three score candidates | 2.9 minutes on a Tesla T4 |
| Wait in Kaggle's queue for that GPU | 48 minutes |

More than half of all attempts failed, almost all because a free tier said no. The retry, fallback and cache code is what turned that into a finished film. List-price equivalents have not been worked out.

## 7. What I would build next

1. **A human sign-off for narration in each language**, recorded in the storyboard, since the automatic check cannot be trusted outside English.
2. **A quota budget.** The voice limit was discovered by running into it. The pipeline should count calls against a daily budget and say before it starts whether a film will fit.
3. **Generated video as the normal path**, once it is known how long a clip takes on a free GPU.
4. **Editing the storyboard on the board**, so directing does not mean editing a JSON file.
5. **Narration in Afaan Oromo**, the language of the region Gebisa Ejeta comes from.

## What is not done

- The two user tests are not recorded.
- The public post and the walkthrough video are not made.
- The second film has eight of its ten narration lines.
- No list prices are in `COSTS.md`.
- The Amharic narration has not been heard by an Amharic speaker.
