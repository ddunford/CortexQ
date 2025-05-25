.PHONY: help setup build up down restart logs clean status shell-api shell-frontend shell-db

# Default target
help:
	@echo "🐳 Docker Development Commands"
	@echo "================================"
	@echo "setup          - Initial project setup"
	@echo "build          - Build all Docker images"
	@echo "up             - Start all services"
	@echo "down           - Stop all services"
	@echo "restart        - Restart all services"
	@echo "logs           - View all service logs"
	@echo "logs-api       - View core-api logs"
	@echo "logs-frontend  - View frontend logs"
	@echo "status         - Show service status"
	@echo "clean          - Clean up containers and volumes"
	@echo ""
	@echo "🔧 Development Commands"
	@echo "======================="
	@echo "shell-api      - Shell into core-api container"
	@echo "shell-frontend - Shell into frontend container"
	@echo "shell-db       - Shell into postgres container"
	@echo ""
	@echo "🗄️ Database Commands"
	@echo "==================="
	@echo "db-reset       - Reset database with migrations"
	@echo "db-seed        - Seed database with initial data"
	@echo "db-migrate     - Run database migrations"
	@echo "db-shell       - Connect to database shell"

# Project setup
setup:
	@echo "🚀 Setting up development environment..."
	@cp -n .env.example .env 2>/dev/null || echo "📝 .env already exists"
	@echo "✅ Setup complete! Run 'make up' to start services"

# Build all images
build:
	@echo "🔨 Building Docker images..."
	docker compose build

# Start all services
up:
	@echo "🚀 Starting all services..."
	docker compose up -d
	@echo "✅ Services started!"
	@echo "🌐 Frontend: http://localhost:3000"
	@echo "🔧 API: http://localhost:8001"
	@echo "📊 Health: http://localhost:8001/health"

# Stop all services
down:
	@echo "🛑 Stopping all services..."
	docker compose down

# Restart all services
restart: down up

# View logs
logs:
	docker compose logs -f

logs-api:
	docker compose logs -f core-api

logs-frontend:
	docker compose logs -f frontend

# Service status
status:
	@echo "📊 Service Status:"
	@docker compose ps
	@echo ""
	@echo "💾 Volume Usage:"
	@docker system df

# Clean up
clean:
	@echo "🧹 Cleaning up Docker resources..."
	docker compose down -v
	docker system prune -f
	@echo "✅ Cleanup complete!"

# Development shells
shell-api:
	@echo "🐚 Opening shell in core-api container..."
	docker compose exec core-api /bin/bash

shell-frontend:
	@echo "🐚 Opening shell in frontend container..."
	docker compose exec frontend /bin/sh

shell-db:
	@echo "🐚 Opening shell in postgres container..."
	docker compose exec postgres psql -U admin -d rag_searcher

# Database commands
db-reset:
	@echo "🗄️ Resetting database..."
	docker compose exec core-api python scripts/reset_database.py

db-seed:
	@echo "🌱 Seeding database..."
	docker compose exec core-api python scripts/seed_database.py

db-migrate:
	@echo "📈 Running migrations..."
	docker compose exec core-api alembic upgrade head

db-shell:
	@echo "🗄️ Connecting to database..."
	docker compose exec postgres psql -U admin -d rag_searcher

# Development workflow
dev: up
	@echo "🔥 Development environment ready!"
	@echo "📝 Edit files on host - changes will be reflected in containers"
	@echo "🔄 Hot reload enabled for frontend and API"

# Health check
health:
	@echo "🏥 Checking service health..."
	@curl -s http://localhost:8001/health | jq . || echo "❌ API not responding"
	@curl -s http://localhost:3000 > /dev/null && echo "✅ Frontend responding" || echo "❌ Frontend not responding" 