# Makefile - Sistema RAG Cativa Textil
# Comandos comuns para desenvolvimento e testes

.PHONY: help install test test-unit test-cov clean lint format docs

# Default target
help:
	@echo "Comandos disponiveis:"
	@echo "  make install      - Instala dependencias"
	@echo "  make test         - Executa todos os testes"
	@echo "  make test-unit    - Executa apenas testes unitarios"
	@echo "  make test-cov     - Executa testes com relatorio de cobertura"
	@echo "  make clean        - Remove arquivos temporarios"
	@echo "  make docs         - Gera documentacao dos schemas"
	@echo "  make metrics      - Exibe metricas do sistema"

# Install dependencies
install:
	pip install -r requirements.txt
	@echo "Dependencias instaladas com sucesso"

# Run all tests
test:
	pytest

# Run only unit tests (fast)
test-unit:
	pytest -m unit

# Run tests with coverage report
test-cov:
	pytest --cov=src --cov-report=html --cov-report=term
	@echo "Relatorio de cobertura gerado em htmlcov/index.html"

# Clean temporary files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type f -name ".coverage" -delete
	@echo "Arquivos temporarios removidos"

# Generate schema documentation
docs:
	python -m src.schemas.data_models
	@echo "Schemas gerados em docs/schemas.json"

# Display metrics
metrics:
	python -c "from src.monitoring.metrics import print_metrics_summary; print_metrics_summary()"
