.PHONY: dev test lint migrate tf-plan tf-apply tf-validate build clean

## ── Local Development ────────────────────────────────────────────────────────

dev:
	docker-compose up --build

dev-bg:
	docker-compose up --build -d

down:
	docker-compose down -v

## ── Database ─────────────────────────────────────────────────────────────────

migrate:
	docker-compose run --rm api alembic upgrade head

migrate-create:
	docker-compose run --rm api alembic revision --autogenerate -m "$(MSG)"

migrate-down:
	docker-compose run --rm api alembic downgrade -1

## ── Testing ──────────────────────────────────────────────────────────────────

test:
	docker-compose run --rm api pytest api/tests/ --cov=src --cov-report=term-missing --cov-report=xml -v

test-worker:
	docker-compose run --rm worker pytest worker/tests/ --cov=src --cov-report=term-missing -v

test-all: test test-worker

## ── Linting ──────────────────────────────────────────────────────────────────

lint:
	ruff check api/src/ worker/src/ --fix
	ruff format api/src/ worker/src/
	mypy api/src/ worker/src/ --strict --ignore-missing-imports

lint-check:
	ruff check api/src/ worker/src/
	ruff format api/src/ worker/src/ --check
	mypy api/src/ worker/src/ --strict --ignore-missing-imports

## ── Docker ───────────────────────────────────────────────────────────────────

build:
	docker build -t calibration-api:local ./api
	docker build -t calibration-worker:local ./worker

## ── Terraform ────────────────────────────────────────────────────────────────

tf-init:
	cd terraform && terraform init -var-file=environments/dev.tfvars

tf-validate:
	cd terraform && terraform fmt -check -recursive && terraform validate

tf-plan:
	cd terraform && terraform plan -var-file=environments/dev.tfvars -out=tfplan.dev

tf-apply:
	cd terraform && terraform apply tfplan.dev

tf-plan-prod:
	cd terraform && terraform plan -var-file=environments/prod.tfvars -out=tfplan.prod

tf-fmt:
	cd terraform && terraform fmt -recursive

## ── Security ─────────────────────────────────────────────────────────────────

sec-scan:
	trivy fs . --severity HIGH,CRITICAL
	pip-audit -r api/pyproject.toml

## ── Cleanup ──────────────────────────────────────────────────────────────────

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name .pytest_cache -exec rm -rf {} + 2>/dev/null || true
	find . -name "*.pyc" -delete
	rm -f terraform/tfplan.*
