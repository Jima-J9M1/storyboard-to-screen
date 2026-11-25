PY := .venv/bin/python

# The film every command works on. Override it: make research FILM=lalibela
FILM ?= gebisa-ejeta

.PHONY: help setup test new films status validate research story narration radio keyframes video shots music assemble film costs board

help:
	@echo "Every command works on one film, chosen with FILM=<name> (default: $(FILM))."
	@echo
	@echo "make film                THE ONE COMMAND: every stage in order, then the finished film"
	@echo "make setup               create the Python environment"
	@echo "make test                run the test suite (no network, no keys)"
	@echo "make new TITLE=\"...\"     start a new film from a title"
	@echo "make films               list the films in this repo"
	@echo "make status              where the film is, as JSON"
	@echo "make validate            check the film's brief and storyboard against schema/"
	@echo "make research            story half, step 1: collect sourced facts about the title"
	@echo "make story               story half, step 2: draft the storyboard from the facts"
	@echo "make narration           speak every narration line (one file per shot)"
	@echo "make radio               the radio cut: narration over placeholder music, to test the story"
	@echo "make keyframes           one picture per shot, painted against the film's reference sheet"
	@echo "make video               animate the pictures with Wan 2.2 on a Kaggle GPU (takes hours)"
	@echo "make shots               one clip per shot: a camera move over its picture"
	@echo "make music               three score candidates from ACE-Step on a Kaggle GPU (takes minutes)"
	@echo "make assemble            cut the film together, tall and wide"
	@echo "make costs               rewrite COSTS.md from the run log"
	@echo "make board               open the production board at http://127.0.0.1:3000"

# Create the local Python environment. Re-runs only when requirements.txt changes.
.venv: requirements.txt
	python3 -m venv .venv
	.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
	touch .venv

setup: .venv

test: .venv
	$(PY) -m unittest discover -s tests -t .

new: .venv
	@test -n "$(TITLE)" || (echo "Give the film a title: make new TITLE=\"Lalibela\""; exit 1)
	$(PY) -m core.films new --title "$(TITLE)"

films: .venv
	@$(PY) -m core.films list

status: .venv
	@$(PY) -m core.status --film $(FILM)

validate: .venv
	$(PY) -m pipeline.validate --film $(FILM)

research: .venv
	$(PY) -m agents.researcher --film $(FILM)

# Drafts storyboard.json if the film has none. An existing storyboard is never overwritten.
story: .venv
	$(PY) -m agents.story --film $(FILM)

narration: .venv
	$(PY) -m pipeline.narration --film $(FILM)

# Speaks any line that changed, then rebuilds the radio cut.
radio: narration
	$(PY) -m pipeline.radio_cut --film $(FILM)

keyframes: .venv
	$(PY) -m pipeline.keyframes --film $(FILM)

video: .venv
	$(PY) -m pipeline.video --film $(FILM)

shots: .venv
	$(PY) -m pipeline.shots --film $(FILM)

music: .venv
	$(PY) -m pipeline.music --film $(FILM)

assemble: .venv
	$(PY) -m pipeline.assemble --film $(FILM)

# The one command. Every stage runs in order and skips whatever is already up to date,
# so from a clean clone this rebuilds the film from the committed storyboard and outputs.
film: .venv
	$(PY) -m pipeline.validate --film $(FILM)
	$(PY) -m pipeline.narration --film $(FILM)
	$(PY) -m pipeline.keyframes --film $(FILM)
	-$(PY) -m pipeline.video --film $(FILM)   # if the GPU job fails, shots fall back to camera moves
	$(PY) -m pipeline.shots --film $(FILM)
	$(PY) -m pipeline.music --film $(FILM)
	$(PY) -m pipeline.assemble --film $(FILM)

costs: .venv
	$(PY) -m core.costs

# The production board: a local page that shows every film and where each one is.
frontend/node_modules: frontend/package.json
	cd frontend && npm install --no-fund --no-audit
	touch frontend/node_modules

board: .venv frontend/node_modules
	cd frontend && npm run dev
