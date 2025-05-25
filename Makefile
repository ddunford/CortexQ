.PHONY: help setup build up down logs clean restart status health frontend backend services

# Default target
help:
	@echo "🚀 Enterprise RAG System - Docker Management"
	@echo ""
	@echo "Available commands:"
	@echo "  setup     - Initial setup and environment preparation"
	@echo "  build     - Build all Docker images"
	@echo "  up        - Start all services"
	@echo "  down      - Stop all services"
	@echo "  restart   - Restart all services"
	@echo "  logs      - Show logs for all services"
	@echo "  status    - Show status of all services"
	@echo "  health    - Check health of all services"
	@echo "  clean     - Clean up containers, images, and volumes"
	@echo ""
	@echo "Individual services:"
	@echo "  frontend  - Start only frontend (Next.js)"
	@echo "  backend   - Start only backend services"
	@echo "  services  - Start only microservices"
	@echo ""
	@echo "Development:"
	@echo "  dev       - Start in development mode with hot reload"
	@echo "  test      - Run tests"
	@echo "  lint      - Run linting"

# Initial setup
setup:
	@echo "🔧 Setting up Enterprise RAG System..."
	@cp .env.example .env
	@echo "✅ Environment file created"
	@docker network create rag-network 2>/dev/null || true
	@echo "✅ Docker network created"
	@echo "🎯 Setup complete! Run 'make up' to start the system"

# Build all images
build:
	@echo "🏗️  Building all Docker images..."
	@docker compose build --parallel
	@echo "✅ All images built successfully"

# Start all services
up:
	@echo "🚀 Starting Enterprise RAG System..."
	@docker compose up -d
	@echo "✅ All services started"
	@echo ""
	@echo "🌐 Access points:"
	@echo "  Frontend:     http://localhost:3000"
	@echo "  API:          http://localhost:8001"
	@echo "  Bot Service:  http://localhost:8012"
	@echo "  Nginx:        http://localhost:80"
	@echo "  Ollama:       http://localhost:11434"
	@echo ""
	@echo "📊 Run 'make status' to check service health"

# Stop all services
down:
	@echo "🛑 Stopping all services..."
	@docker compose down
	@echo "✅ All services stopped"

# Restart all services
restart:
	@echo "🔄 Restarting all services..."
	@docker compose restart
	@echo "✅ All services restarted"

# Show logs
logs:
	@echo "📋 Showing logs for all services..."
	@docker compose logs -f --tail=100

# Show service status
status:
	@echo "📊 Service Status:"
	@echo "===================="
	@docker compose ps
	@echo ""
	@echo "🔍 Docker Stats:"
	@docker stats --no-stream --format "table {{.Container}}\t{{.CPUPerc}}\t{{.MemUsage}}\t{{.NetIO}}"

# Health check all services
health:
	@echo "🏥 Health Check Results:"
	@echo "========================"
	@echo -n "Frontend:     "; curl -s -o /dev/null -w "%{http_code}" http://localhost:3000 || echo "DOWN"
	@echo -n "Core API:     "; curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health || echo "DOWN"
	@echo -n "Bot Service:  "; curl -s -o /dev/null -w "%{http_code}" http://localhost:8012/health || echo "DOWN"
	@echo -n "Ollama:       "; curl -s -o /dev/null -w "%{http_code}" http://localhost:11434/api/tags || echo "DOWN"
	@echo -n "Nginx:        "; curl -s -o /dev/null -w "%{http_code}" http://localhost:80/health || echo "DOWN"
	@echo -n "PostgreSQL:   "; docker compose exec postgres pg_isready -U admin -d rag_searcher > /dev/null 2>&1 && echo "200" || echo "DOWN"
	@echo -n "Redis:        "; docker compose exec redis redis-cli ping > /dev/null 2>&1 && echo "200" || echo "DOWN"

# Clean up everything
clean:
	@echo "🧹 Cleaning up Docker resources..."
	@docker compose down -v --remove-orphans
	@docker system prune -f
	@docker volume prune -f
	@echo "✅ Cleanup complete"

# Development mode with hot reload
dev:
	@echo "🔧 Starting in development mode..."
	@docker compose -f docker compose.yml -f docker compose.dev.yml up -d
	@echo "✅ Development environment started"

# Start only frontend
frontend:
	@echo "🎨 Starting frontend only..."
	@docker compose up -d postgres redis core-api frontend
	@echo "✅ Frontend stack started"

# Start only backend services
backend:
	@echo "⚙️  Starting backend services..."
	@docker compose up -d postgres redis core-api ollama
	@echo "✅ Backend services started"

# Start only microservices
services:
	@echo "🔧 Starting microservices..."
	@docker compose up -d bot-service
	@echo "✅ Microservices started"

# Initialize Ollama models
init-ollama:
	@echo "🤖 Initializing Ollama models..."
	@docker compose exec ollama ollama pull llama2
	@docker compose exec ollama ollama pull nomic-embed-text
	@echo "✅ Ollama models initialized"

# Run tests
test:
	@echo "🧪 Running tests..."
	@docker compose exec core-api python -m pytest tests/ -v
	@echo "✅ Tests completed"

# Run linting
lint:
	@echo "🔍 Running linting..."
	@docker compose exec core-api python -m flake8 src/
	@docker compose exec frontend npm run lint
	@echo "✅ Linting completed"

# Database operations
db-migrate:
	@echo "📊 Running database migrations..."
	@docker compose exec core-api alembic upgrade head
	@echo "✅ Database migrations completed"

db-migrate-create:
	@echo "📝 Creating new migration..."
	@docker compose exec core-api alembic revision --autogenerate -m "$(MSG)"
	@echo "✅ Migration created"

db-migrate-status:
	@echo "📋 Migration status..."
	@docker compose exec core-api alembic current
	@docker compose exec core-api alembic history

db-migrate-downgrade:
	@echo "⬇️  Rolling back migration..."
	@docker compose exec core-api alembic downgrade -1
	@echo "✅ Migration rolled back"

db-reset:
	@echo "🗄️  Resetting database..."
	@docker compose down postgres
	@docker volume rm rag_chat_postgres_data
	@docker compose up -d postgres
	@echo "✅ Database reset completed"

# Backup operations
backup:
	@echo "💾 Creating backup..."
	@mkdir -p backups
	@docker compose exec postgres pg_dump -U admin rag_searcher > backups/backup_$(shell date +%Y%m%d_%H%M%S).sql
	@echo "✅ Backup created in backups/ directory"

# Monitor logs for specific service
logs-frontend:
	@docker compose logs -f frontend

logs-api:
	@docker compose logs -f core-api

logs-bot:
	@docker compose logs -f bot-service

logs-ollama:
	@docker compose logs -f ollama

# Quick commands
quick-start: setup build up init-ollama
	@echo "🎉 Enterprise RAG System is ready!"
	@echo "Visit http://localhost:3000 to access the professional frontend"

quick-stop: down clean
	@echo "🛑 System stopped and cleaned" 