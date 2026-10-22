# Quantitative Trading Tool - Makefile
# Cross-platform build commands

.PHONY: help install test app db init-db clean lint format

# Default target
help:
	@echo ""
	@echo "Quantitative Trading Tool - Available Commands"
	@echo "==============================================="
	@echo ""
	@echo "  make install     Install Python dependencies"
	@echo "  make app         Start Streamlit web application"
	@echo "  make test        Run all unit tests"
	@echo "  make test-cov    Run tests with coverage report"
	@echo "  make db          Start PostgreSQL database (Docker)"
	@echo "  make db-stop     Stop PostgreSQL database"
	@echo "  make init-db     Initialize database tables"
	@echo "  make lint        Run code linting"
	@echo "  make format      Format code with black"
	@echo "  make clean       Clean up cache files"
	@echo ""

# Installation
install:
	pip install -r requirements.txt

install-dev:
	pip install -r requirements.txt
	pip install pytest-cov black flake8 mypy

# Application
app:
	streamlit run app.py

# Testing
test:
	pytest tests/ -v

test-cov:
	pytest tests/ --cov=core --cov=strategies --cov-report=html --cov-report=term
	@echo "Coverage report generated in htmlcov/"

test-risk:
	pytest tests/test_risk.py -v

test-optimizer:
	pytest tests/test_optimizer.py -v

test-backtester:
	pytest tests/test_backtester.py -v

test-strategies:
	pytest tests/test_strategies.py -v

# Database
db:
	docker-compose up -d
	@echo ""
	@echo "Database started. Access pgAdmin at http://localhost:5050"
	@echo "  Email: admin@admin.com"
	@echo "  Password: admin"

db-stop:
	docker-compose down

db-logs:
	docker-compose logs -f postgres

init-db:
	python scripts/init_database.py

# Code quality
lint:
	flake8 core/ strategies/ --max-line-length=100 --ignore=E501,W503

format:
	black core/ strategies/ pages/ tests/ examples/ --line-length=100

type-check:
	mypy core/ strategies/ --ignore-missing-imports

# Cleanup
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "htmlcov" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name ".coverage" -delete 2>/dev/null || true

# Examples
example-basic:
	python examples/basic_usage.py

example-backtest:
	python examples/backtest_example.py

example-optimization:
	python examples/optimization_example.py

example-risk:
	python examples/risk_analysis_example.py

example-pairs:
	python examples/pairs_trading_example.py

# Scripts
download:
	@echo "Usage: make download SYMBOLS=AAPL,MSFT START=2023-01-01 END=2023-12-31"
	python scripts/download_data.py --symbols $(SYMBOLS) --start $(START) --end $(END)

backtest:
	@echo "Usage: make backtest STRATEGY=mean_reversion SYMBOLS=AAPL"
	python scripts/run_backtest.py --strategy $(STRATEGY) --symbols $(SYMBOLS)
