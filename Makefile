.PHONY: up down logs test lint format clean restart restart-fe restart-be rebuild

# Docker 管理
up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

# 开发工具
test:
	uv run pytest

test-cov:
	uv run pytest --cov=src --cov-report=term-missing

lint:
	uv run ruff check .

format:
	uv run black .

type-check:
	uv run mypy src

# 清理
clean:
	docker-compose down -v
	rm -rf .venv
	rm -rf .pytest_cache
	rm -rf .ruff_cache
	rm -rf .mypy_cache
	find . -type d -name __pycache__ -exec rm -rf {} +

# 重启
restart-fe:
	docker-compose build frontend
	docker-compose up -d --force-recreate frontend

restart-be:
	docker-compose build api worker
	docker-compose up -d --force-recreate api worker

restart:
	docker-compose build api worker frontend
	docker-compose up -d --force-recreate api worker frontend

rebuild:
	docker-compose build --no-cache api worker frontend
	docker-compose up -d --force-recreate api worker frontend

# 帮助
help:
	@echo "可用命令:"
	@echo "  make up        - 启动 Docker 容器"
	@echo "  make down      - 停止 Docker 容器"
	@echo "  make logs      - 查看容器日志"
	@echo "  make test      - 运行测试"
	@echo "  make test-cov  - 运行测试并生成覆盖率报告"
	@echo "  make lint      - 代码检查"
	@echo "  make format    - 代码格式化"
	@echo "  make type-check - 类型检查"
	@echo "  make clean     - 清理环境"
	@echo "  make restart   - 重启全部应用服务(使用缓存加速)"
	@echo "  make restart-fe - 重启前端(使用缓存加速)"
	@echo "  make restart-be - 重启后端+Worker(使用缓存加速)"
	@echo "  make rebuild   - 完全重建全部服务(无缓存,用于依赖变更后)"
