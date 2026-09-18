.DEFAULT_GOAL := help

.PHONY: help install lint format typecheck test check run clean

help: ## Показать список команд
	@grep -E '^[a-z]+:.*## ' $(MAKEFILE_LIST) | awk -F ':.*## ' '{printf "  %-12s %s\n", $$1, $$2}'

install: ## Установить зависимости и pre-commit хуки
	uv sync
	test -f .env || cp .env.example .env
	uv run pre-commit install

lint: ## Проверить код ruff (без изменений)
	uv run ruff check .
	uv run ruff format --check .

format: ## Отформатировать код и исправить автофиксы ruff
	uv run ruff format .
	uv run ruff check --fix .

typecheck: ## Проверить типы mypy
	uv run mypy

test: ## Запустить тесты
	uv run pytest -v

check: lint typecheck test ## Все проверки: lint, typecheck, test

run: ## Запустить замер: make run URL=https://... [ARGS="-n 5"]
	uv run speedmeter $(URL) $(ARGS)

clean: ## Удалить кэши инструментов
	rm -rf .ruff_cache .mypy_cache .pytest_cache
	find . -name __pycache__ -type d -not -path './.venv/*' -exec rm -rf {} +
