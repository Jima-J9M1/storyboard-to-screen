PY := .venv/bin/python

.PHONY: help setup test validate research

help:
	@echo "make setup     create the Python environment"
	@echo "make test      run the test suite (no network, no keys)"
	@echo "make validate  check brief.json and storyboard.json against schema/"
	@echo "make research  story half, step 1: collect sourced material on the brief's title"

# Create the local Python environment. Re-runs only when requirements.txt changes.
.venv: requirements.txt
	python3 -m venv .venv
	.venv/bin/pip install --quiet --disable-pip-version-check -r requirements.txt
	touch .venv

setup: .venv

test: .venv
	$(PY) -m unittest discover -s tests -t .

validate: .venv
	$(PY) -m pipeline.validate

research: .venv
	$(PY) -m agents.researcher
