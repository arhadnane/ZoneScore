# URBISQC — bare-metal orchestration (no Docker).
# Windows note: use Git Bash / WSL for `make`, or call the equivalent commands directly.

VENV      := .venv
ifeq ($(OS),Windows_NT)
PYTHON    := $(VENV)/Scripts/python.exe
else
PYTHON    := $(VENV)/bin/python
endif
PORT      ?= 8000

.PHONY: all venv install etl test run dev clean lint format

all: install test run

venv:
	python -m venv $(VENV)

install: venv
	$(PYTHON) -m pip install --upgrade pip
	$(PYTHON) -m pip install -r backend/requirements.txt

lint:
	$(PYTHON) -m ruff check backend

format:
	$(PYTHON) -m ruff format backend

etl:
	cd backend && ../$(PYTHON) -m app.etl.pipeline

etl-offline:
	cd backend && URBIS_OFFLINE=1 ../$(PYTHON) -m app.etl.pipeline

test:
	cd backend && ../$(PYTHON) -m pytest

run:
	cd backend && ../$(PYTHON) -m uvicorn app.main:app --host 127.0.0.1 --port $(PORT)

dev:
	cd backend && ../$(PYTHON) -m uvicorn app.main:app --host 127.0.0.1 --port $(PORT) --reload

clean:
	rm -f data/processed/zones_res*.parquet data/processed/urbisqc.duckdb
