SHELL := /bin/zsh

API_DIR := apps/api
API_ENV := cd $(API_DIR) &&

.PHONY: help api-test api-test-file api-test-k api-lint api-format api-typecheck api-run api-check
help:
	@echo "Available targets:"
	@echo "  make api-test                         Run full API test suite"
	@echo "  make api-test-file TEST=path          Run one API test file"
	@echo "  make api-test-k K=expr                Run API tests filtered by -k expression"
	@echo "  make api-lint                         Run ruff check"
	@echo "  make api-format                       Run ruff format"
	@echo "  make api-typecheck                    Run pyright"
	@echo "  make api-run                          Run API server with reload"
	@echo "  make api-check                        Run lint, typecheck, and tests"

api-test:
	$(API_ENV) if [ -x .venv/bin/pytest ]; then PYTHONPATH=. .venv/bin/pytest -q tests; else PYTHONPATH=. pytest -q tests; fi

api-test-file:
	@test -n "$(TEST)" || (echo "Usage: make api-test-file TEST=tests/test_x.py" && exit 1)
	$(API_ENV) if [ -x .venv/bin/pytest ]; then PYTHONPATH=. .venv/bin/pytest -q $(TEST); else PYTHONPATH=. pytest -q $(TEST); fi

api-test-k:
	@test -n "$(K)" || (echo "Usage: make api-test-k K=pattern" && exit 1)
	$(API_ENV) if [ -x .venv/bin/pytest ]; then PYTHONPATH=. .venv/bin/pytest -q tests -k "$(K)"; else PYTHONPATH=. pytest -q tests -k "$(K)"; fi

api-lint:
	$(API_ENV) if [ -x .venv/bin/ruff ]; then .venv/bin/ruff check .; else ruff check .; fi

api-format:
	$(API_ENV) if [ -x .venv/bin/ruff ]; then .venv/bin/ruff format .; else ruff format .; fi

api-typecheck:
	$(API_ENV) if [ -x .venv/bin/pyright ]; then .venv/bin/pyright app; else pyright app; fi

api-run:
	$(API_ENV) if [ -x .venv/bin/uvicorn ]; then PYTHONPATH=. .venv/bin/uvicorn app.main:app --reload; else PYTHONPATH=. uvicorn app.main:app --reload; fi

api-check: api-lint api-typecheck api-test
