PYTHON ?= python
OUT ?= out/fixture-release
.PHONY: help install check test smoke release-fixture clean
help:
	@printf '%s\n' 'install check test smoke release-fixture clean'
install:
	$(PYTHON) -m pip install --no-build-isolation -e '.[test]'
check:
	$(PYTHON) -m compileall -q aligner
	$(PYTHON) -m json.tool aligner/mappings/registry.json >/dev/null
	$(PYTHON) -m json.tool aligner/compatibility.json >/dev/null
	$(PYTHON) -m aligner.cli --help >/dev/null
test:
	$(PYTHON) -m pytest -q
smoke:
	@tmp=$$(mktemp -d); trap 'rm -rf "$$tmp"' EXIT; $(PYTHON) -m aligner.cli --direction eph-to-censo --entity hogar --input fixtures/eph/hogar.csv --region fixtures/regions.csv --source-vintage fixture-v1 --output-dir $$tmp/eph; $(PYTHON) -m aligner.integration $$tmp/eph/manifest.json --expected-vintage fixture-v1; $(PYTHON) -m aligner.cli --direction censo-to-eph --entity hogar --input fixtures/censo/hogar.csv --region fixtures/regions.csv --source-vintage fixture-v1 --output-dir $$tmp/censo; $(PYTHON) -m aligner.integration $$tmp/censo/manifest.json --expected-vintage fixture-v1
release-fixture:
	rm -rf $(OUT)
	$(PYTHON) -m aligner.cli --direction eph-to-censo --entity hogar --input fixtures/eph/hogar.csv --region fixtures/regions.csv --source-vintage fixture-v1 --release-id fixture-v1 --output-dir $(OUT)/eph-to-censo
	$(PYTHON) -m aligner.cli --direction censo-to-eph --entity hogar --input fixtures/censo/hogar.csv --region fixtures/regions.csv --source-vintage fixture-v1 --release-id fixture-v1 --output-dir $(OUT)/censo-to-eph
	$(PYTHON) -m aligner.integration $(OUT)/eph-to-censo/manifest.json --expected-vintage fixture-v1
	$(PYTHON) -m aligner.integration $(OUT)/censo-to-eph/manifest.json --expected-vintage fixture-v1
clean:
	rm -rf out
