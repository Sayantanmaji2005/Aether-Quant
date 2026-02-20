.PHONY: install lint typecheck test all docker-build docker-run

install:
	pip install -e .[dev]

lint:
	ruff check .

typecheck:
	mypy src

test:
	pytest

all: lint typecheck test

docker-build:
	docker build -t aetherquant:latest .

docker-run:
	docker compose up --build
