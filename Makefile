# Единая точка входа в проект. Список целей: make help
# Windows: установите make (choco install make) или выполняйте команды из целей вручную.
.DEFAULT_GOAL := help
PYTHON ?= python

.PHONY: help install precommit run analyze dashboard lint format test check clean

# ---------- Установка ----------
install: ## Установить зависимости (pip install -r requirements.txt)
	$(PYTHON) -m pip install -r requirements.txt

precommit: ## Установить git-хуки pre-commit
	pre-commit install

# ---------- Запуск ----------
run: ## Запустить сервер телеметрии (uvicorn, --reload)
	uvicorn server.app:app --reload

analyze: ## Обработать собранные события (analysis/analyze.py)
	$(PYTHON) analysis/analyze.py

dashboard: ## Открыть дашборд Streamlit
	streamlit run dashboard/app.py

# ---------- Проверка ----------
lint: ## Проверить код линтером ruff
	ruff check .

format: ## Отформатировать код и применить автоисправления ruff
	ruff format . && ruff check --fix .

test: ## Запустить тесты pytest
	pytest

check: lint test ## Линтер + тесты (то же, что CI)

# ---------- Обслуживание ----------
clean: ## Удалить кеши Python, pytest, ruff и egg-info
	find . -type d \( -name __pycache__ -o -name .pytest_cache -o -name .ruff_cache -o -name '*.egg-info' \) -prune -exec rm -rf {} +

help: ## Показать список целей
	@grep -hE '^[a-zA-Z0-9_-]+:.*## ' $(MAKEFILE_LIST) \
	  | awk 'BEGIN {FS = ":.*## "}; {printf "  \033[36m%-16s\033[0m %s\n", $$1, $$2}'

