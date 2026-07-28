# Arcadia auth & profile service.
#
#   make install   create .venv and install everything
#   make test      run the tests
#   make docker    build the image
#
# The image is built here, not in the infra repository: how a service is built is that
# service's business.

SERVICE  := auth-profile-service
IMAGE    := arcadia/$(SERVICE)
VERSION  ?= local
VENV     := .venv
PY       := $(VENV)/bin/python

.DEFAULT_GOAL := help
.PHONY: help install test run docker clean

help: ## Show this help
	@grep -hE '^[a-zA-Z0-9_-]+:.*?## ' $(MAKEFILE_LIST) \
		| awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-10s\033[0m %s\n", $$1, $$2}'

install: ## Create the virtualenv and install dependencies
	python3 -m venv $(VENV)
	$(PY) -m pip install --quiet --upgrade pip
	$(PY) -m pip install --quiet -r requirements.txt
	@echo "installed"

test: ## Run the tests (no database, broker or cache needed)
	$(PY) -m pytest -q

run: ## Run locally against the infra stack
	$(VENV)/bin/uvicorn app.main:app --reload --port 8085

docker: ## Build the image
	docker build --build-arg VERSION=$(VERSION) -t $(IMAGE):$(VERSION) .
	@echo "built $(IMAGE):$(VERSION)"

clean: ## Remove the virtualenv and caches
	rm -rf $(VENV) .pytest_cache .ruff_cache
	find . -type d -name __pycache__ -prune -exec rm -rf {} +
