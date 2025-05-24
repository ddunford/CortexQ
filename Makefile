.PHONY: setup install test dev clean build start stop logs help start-file-service start-vector-service test-vector

# Default target
help:
	@echo "Available commands:"
	@echo "  setup           - Set up development environment"
	@echo "  install         - Install Python dependencies"
	@echo "  dev             - Start development environment"
	@echo "  build           - Build all Docker services"
	@echo "  start           - Start all services"
	@echo "  stop            - Stop all services"
	@echo "  test            - Run tests"
	@echo "  start-file-service   - Start file service in development mode"
	@echo "  start-vector-service - Start vector service in development mode"
	@echo "  test-vector     - Test vector service functionality"
	@echo "  logs            - Show logs from all services"
	@echo "  clean           - Clean up development environment"

setup:
	@echo "🚀 Setting up development environment..."
	python3 -m venv venv
	./venv/bin/pip install --upgrade pip
	./venv/bin/pip install -r requirements.txt
	./venv/bin/pip install numpy faiss-cpu pgvector pydantic-settings
	cp .env.example .env
	@echo "✅ Setup complete! Edit .env file with your configuration."

install:
	@echo "📦 Installing dependencies..."
	./venv/bin/pip install -r requirements.txt

dev:
	@echo "🔧 Starting development environment..."
	docker compose up -d postgres redis
	@echo "✅ Database services started. Run 'make start-file-service' and 'make start-vector-service' to start services."

build:
	@echo "🏗️ Building Docker services..."
	docker compose build

start:
	@echo "🚀 Starting all services..."
	docker compose up -d

stop:
	@echo "🛑 Stopping all services..."
	docker compose down

start-file-service:
	@echo "🚀 Starting file service in development mode..."
	cd services/ingestion/file-service && ../../../venv/bin/python src/main.py

start-vector-service:
	@echo "🚀 Starting vector service in development mode..."
	cd services/search/vector-service && ../../../venv/bin/python src/main.py

test-vector:
	@echo "🧪 Testing vector service functionality..."
	@echo "1. Testing health endpoint..."
	curl -s http://localhost:8002/health | python -m json.tool
	@echo "\n2. Testing embedding generation..."
	curl -s -X POST http://localhost:8002/embed \
		-H "Content-Type: application/json" \
		-d '{"text": "This is a test document for embedding generation", "source_type": "test"}' | python -m json.tool
	@echo "\n3. Testing search functionality..."
	curl -s -X POST http://localhost:8002/search \
		-H "Content-Type: application/json" \
		-d '{"query": "test document", "top_k": 5}' | python -m json.tool

test:
	@echo "🧪 Running tests..."
	./venv/bin/pytest tests/ -v

test-unit:
	@echo "🧪 Running unit tests..."
	./venv/bin/pytest tests/unit/ -v

test-integration:
	@echo "🧪 Running integration tests..."
	./venv/bin/pytest tests/integration/ -v

logs:
	@echo "📋 Showing logs..."
	docker compose logs -f

clean:
	@echo "🧹 Cleaning up..."
	docker compose down -v
	docker system prune -f
	rm -rf venv/
	@echo "✅ Cleanup complete!"

init-db:
	@echo "🗄️ Initializing database..."
	docker compose exec postgres psql -U admin -d rag_searcher -f /docker-entrypoint-initdb.d/init_db.sql

format:
	@echo "🎨 Formatting code..."
	./venv/bin/black services/
	./venv/bin/flake8 services/

pre-commit-setup:
	@echo "🔗 Setting up pre-commit hooks..."
	./venv/bin/pre-commit install 