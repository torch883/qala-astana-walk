.PHONY: run legacy install collect warm enrich index test eval cache
PYTHON ?= python
run:
	$(PYTHON) -m uvicorn api:app --host 127.0.0.1 --port 8000 --no-access-log
legacy:
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
warm:
	$(PYTHON) -m data.collect_warm
