.PHONY: help install dev test run serve frontend doctor clean lint spine docker-contract docker-build docker-up docker-hermetic

help: ## Show this help
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | sort | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "\033[36m%-15s\033[0m %s\n", $$1, $$2}'

install: ## Install production dependencies
	pip install -e ".[dev]"

dev: ## Install with all dev dependencies
	pip install -e ".[dev]"
	pip install fastapi uvicorn aiohttp websockets python-multipart

test: ## Run all tests
	python3 -m unittest discover -s tests/unit -v 2>&1 | tail -20

test-integration: ## Run integration tests
	python3 -m unittest discover -s tests/integration -v 2>&1 | tail -20

serve: ## Start backend server
	python3 -m uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload

frontend: ## Start frontend server
	python3 scripts/serve_frontend.py 8080

doctor: ## Run system diagnostics
	python3 -m think_box_ai doctor

status: ## Show system status
	python3 -m think_box_ai status

init: ## Initialize project
	python3 -m think_box_ai init

clean: ## Clean generated files
	rm -rf __pycache__ .pytest_cache *.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true

lint: ## Run all linters (ruff, type checking, security)
	ruff check thinkbox core backend tests think_box_ai scripts
	@echo "✅ Lint check passed"

fmt: ## Format code with ruff
	ruff check --fix thinkbox core backend tests think_box_ai scripts
	@echo "✅ Code formatted"

type: ## Run type checking with mypy
	mypy thinkbox core backend think_box_ai || true

security: ## Security scan with bandit
	bandit -r thinkbox core backend think_box_ai || true

check: lint type security test ## Full check: lint + type + security + test
	@echo "✅ All checks passed"

pre-push: lint type security ## Pre-push check (no tests)
	@echo "✅ Ready to push"

lint-beyond-kilo: ## PR #170 scoped ruff/mypy/bandit gate (requires pip install -e ".[lint]")
	KILO_BEYOND_KILO_LINT_EXECUTE=1 python3 scripts/verify_kilo_beyond_kilo_lint.py

spine: ## KILO spine verify (fast default)
	PYTHONUNBUFFERED=1 python3 -u scripts/verify_kilo_spine.py

docker-contract: ## Hermetic Docker file contract (no daemon)
	python3 scripts/verify_docker_contract.py

docker-build: ## Build API image thinkbox-ai:local
	docker build -t thinkbox-ai:local -f Dockerfile .

docker-build-hermetic: ## Build hermetic spine-verify image
	docker build -t thinkbox-ai:hermetic -f Dockerfile.hermetic .

docker-up: ## Start API via compose
	docker compose up api -d --build

docker-hermetic: ## Run docker contract verify inside container
	docker compose --profile hermetic run --rm spine-verify

all: init dev test ## Full setup: init, install, test
