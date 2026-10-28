.PHONY: help install install-dev sample sync run stop warm eval test lint clean

PY := $(if $(wildcard .venv/bin/python),.venv/bin/python,python3)

help:
	@echo "make install      create .venv and install dependencies"
	@echo "make install-dev  also install pytest and ruff"
	@echo "make sample       build a demo index from sample_data/docs into data/index"
	@echo "make sync         crawl KB_ROOT_URL (from .env) and rebuild the index"
	@echo "make run / stop   start / stop the API and the UI"
	@echo "make warm         pre-fill the response cache with the suggested questions"
	@echo "make eval         run the evaluation questions against the API"
	@echo "make test / lint  run tests / ruff"

.venv/bin/python:
	python3 -m venv .venv

install: .venv/bin/python
	.venv/bin/pip install --upgrade pip
	.venv/bin/pip install -r requirements.txt
	@test -f .env || cp .env.example .env

install-dev: install
	.venv/bin/pip install -r requirements-dev.txt

sample:
	$(PY) scripts/build_sample_corpus.py --docs-dir sample_data/docs --out data/sample/articles.jsonl
	$(PY) indexer/build_index.py --articles data/sample/articles.jsonl --out-dir data/index

sync:
	./scripts/sync_kb.sh

run:
	./start.sh

stop:
	./stop.sh

warm:
	$(PY) scripts/warm_cache.py

eval:
	$(PY) eval/run_eval.py

test:
	$(PY) -m pytest

lint:
	$(PY) -m ruff check .

clean:
	rm -rf .pytest_cache .ruff_cache logs/*.pid
	find . -name __pycache__ -not -path "./.venv/*" -type d -prune -exec rm -rf {} +
