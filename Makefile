.PHONY: run install collect enrich index test eval cache
PYTHON ?= python
run:
	$(PYTHON) -m streamlit run app.py
install:
	$(PYTHON) -m pip install -r requirements.txt
collect:
	$(PYTHON) -m data.collect
enrich:
	$(PYTHON) -m data.enrich
index:
	$(PYTHON) -m core.retrieve --build
test:
	$(PYTHON) -m pytest -q
eval:
	$(PYTHON) -m eval.run_eval
cache:
	$(PYTHON) -m eval.build_cache
