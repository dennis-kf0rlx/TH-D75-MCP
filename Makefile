PYTHON ?= python3
VENV ?= .venv

.PHONY: venv check run-settings run-monitor clean

venv: $(VENV)/bin/python

$(VENV)/bin/python:
	$(PYTHON) -m venv $(VENV)
	$(VENV)/bin/pip install -r requirements.txt

check: venv
	$(VENV)/bin/python -m py_compile \
	  settings-ui/server.py settings-ui/generate_catalog.py \
	  d75mon/backend/d75mon.py d75mon/tests/test_cat.py
	$(VENV)/bin/python -m unittest discover -s d75mon/tests

run-settings: venv
	$(VENV)/bin/python settings-ui/server.py

run-monitor: venv
	$(VENV)/bin/python d75mon/backend/d75mon.py --config d75mon/config.json

clean:
	rm -rf $(VENV) settings-ui/__pycache__ d75mon/__pycache__
