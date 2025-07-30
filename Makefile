# Makefile for building Sphinx docs and Python package

.PHONY: all docs build clean

# Build everything: docs + package
all: docs build

# Build Sphinx documentation
docs:
	sphinx-build -b html doc/ doc/_build/html

# Build the Python package (wheel and source)
build:
	python -m build

# Push package to pypi.org
release: build
	twine upload dist/*

# Clean build artifacts
clean:
	rm -rf build/ dist/ *.egg-info doc/_build

ruff:
	ruff check orangecontrib/timeseries_patched/widgets/*.py

ruff-fix:
	ruff check --fix orangecontrib/timeseries_patched/widgets/*.py

pylint:
	pylint orangecontrib/timeseries_patched/widgets/*.py
