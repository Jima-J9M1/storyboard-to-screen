# The whole system on one small server: the pipeline (Python, FFmpeg) and the board (Next.js).
# Written for a free Hugging Face Docker Space, which serves port 7860 and runs as user 1000.
#
# Keys are not in this image. Set them as secrets on the server (see deploy/README.md).
# Without keys the board shows every film but cannot make anything; without BOARD_PASSWORD
# it refuses every change.

FROM node:22-bookworm-slim AS node

FROM python:3.13-slim-bookworm
RUN apt-get update && apt-get install -y --no-install-recommends ffmpeg make && rm -rf /var/lib/apt/lists/*
COPY --from=node /usr/local/bin/node /usr/local/bin/node
COPY --from=node /usr/local/lib/node_modules /usr/local/lib/node_modules
RUN ln -s ../lib/node_modules/npm/bin/npm-cli.js /usr/local/bin/npm \
 && ln -s ../lib/node_modules/npm/bin/npx-cli.js /usr/local/bin/npx

RUN useradd --create-home --uid 1000 board
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY --chown=board:board . .
USER board
ENV BOARD_PUBLIC=1 BOARD_PYTHON=/usr/local/bin/python NEXT_TELEMETRY_DISABLED=1 HOME=/home/board

# The moving shots are not stored in git: FFmpeg rebuilds them from the committed pictures and
# clips. This makes no model call. A film that fails here still shows its other stages.
RUN for film in $(python -m core.films list); do python -m pipeline.shots --film "$film" || true; done

RUN cd frontend && npm ci --no-fund --no-audit && npx next build

EXPOSE 7860
WORKDIR /app/frontend
CMD ["npx", "next", "start", "--hostname", "0.0.0.0", "--port", "7860"]
