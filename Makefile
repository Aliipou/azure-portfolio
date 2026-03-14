.PHONY: run build test lint docker-up docker-down tidy tf-plan tf-apply tf-validate tf-fmt clean

## ── Go ────────────────────────────────────────────────────────────────────────

run:
	go run ./cmd/api

build:
	go build -o bin/api ./cmd/api

test:
	go test ./... -v -race -coverprofile=coverage.out
	go tool cover -func=coverage.out

cover:
	go test ./... -coverprofile=coverage.out
	go tool cover -html=coverage.out -o coverage.html

lint:
	golangci-lint run

tidy:
	go mod tidy

## ── Docker ───────────────────────────────────────────────────────────────────

docker-up:
	docker compose up --build -d

docker-down:
	docker compose down -v

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

## ── Cleanup ──────────────────────────────────────────────────────────────────

clean:
	rm -rf bin/
	rm -f terraform/tfplan.*
