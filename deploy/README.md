# Running the system on a server

The board and the pipeline run together in one container, built from the `Dockerfile` in the repo root. It is set up for a free Hugging Face Docker Space, and works on any host that runs a container and serves port 7860.

## Send it
```
.venv/bin/pip install huggingface_hub
.venv/bin/python -m deploy.space
```
This sends the committed files only. It needs `HF_TOKEN` in `.env`.

## What a visitor can do
| Server setting | Result |
|---|---|
| No secrets set | The board shows every film and each stage's outputs. Nothing can be changed. |
| `BOARD_PASSWORD` set | A change (new film, a director's note, running a stage) asks for the password. |
| The pipeline's keys set too | Those changes can call the models. |

Set these on the Space's Settings page, under "Variables and secrets", as secrets: `BOARD_PASSWORD`, and the key names listed in `.env.example` (plus `ADDIS_API_KEY` for an Amharic voice from Addis AI).

## Limits of the free tier
- The disk is reset on every restart. Films in the repo come back; a film made on the server is lost unless it is downloaded or the Space has persistent storage.
- The server has no GPU. Generated video and the score still run on Kaggle, started from a terminal.
- The Space sleeps when nobody visits, and takes about a minute to wake.
