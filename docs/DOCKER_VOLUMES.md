# Docker Volume Configuration Guide

## 🐳 Corrected Volume Mapping Strategy

This document explains the **corrected Docker volume configuration** that eliminates the need to copy files between host and containers.

## 📁 Current Volume Mappings

### Core API Service (`core-api`)
```yaml
volumes:
  # Source code - live editing
  - ./core-api/src:/app/src
  
  # Scripts - accessible from host
  - ./core-api/scripts:/app/scripts
  
  # Database migrations - development access
  - ./core-api/alembic:/app/alembic
  - ./core-api/alembic.ini:/app/alembic.ini
  
  # Dependencies - for live updates
  - ./core-api/requirements.txt:/app/requirements.txt
  
  # Persistent storage
  - file_storage:/app/storage
```

### Frontend Service (`frontend`)
```yaml
volumes:
  # Entire frontend directory - complete access
  - ./frontend:/app
  
  # Exclude container-specific directories
  - /app/node_modules    # Prevent host/container conflicts
  - /app/.next          # Exclude build artifacts
```

### Bot Service (`bot-service`)
```yaml
volumes:
  # Source code for development
  - ./services/ui/bot-service/src:/app/src
  - ./services/ui/bot-service/package.json:/app/package.json
```

## ✅ Benefits of This Setup

### 1. **No File Copying Required**
- Edit files on host → Changes immediately available in container
- No need for `docker cp` commands
- No synchronization issues

### 2. **Live Development**
- **Frontend**: Hot reload works automatically
- **Backend**: Code changes reflected immediately
- **Scripts**: Database scripts accessible from host

### 3. **Complete Development Access**
```bash
# All these work directly from host:
vim core-api/src/main.py              # Edit API code
vim frontend/src/components/Chat.tsx   # Edit frontend
vim core-api/scripts/seed_database.py # Edit database scripts
vim core-api/alembic/versions/*.py     # Edit migrations
```

## 🔧 Development Workflow

### Starting Development
```bash
# 1. Start all services
make up

# 2. Check status
make status

# 3. View logs
make logs-api      # API logs
make logs-frontend # Frontend logs
```

### Making Changes

#### Backend Changes
```bash
# Edit any Python file on host
vim core-api/src/api/auth.py

# Changes are immediately available in container
# No restart needed for most changes
```

#### Frontend Changes
```bash
# Edit any React component on host
vim frontend/src/components/DomainWorkspace.tsx

# Hot reload automatically updates browser
# No manual refresh needed
```

#### Database Operations
```bash
# Run migrations directly
make db-migrate

# Reset database
make db-reset

# Seed database
make db-seed

# Access database shell
make db-shell
```

### Debugging and Shell Access
```bash
# Shell into any container
make shell-api      # Core API container
make shell-frontend # Frontend container
make shell-db       # Database container

# Or manually:
docker compose exec core-api /bin/bash
docker compose exec frontend /bin/sh
```

## 📂 Directory Structure Mapping

```
Host                          Container
====                          =========
./core-api/src/          →    /app/src/
./core-api/scripts/      →    /app/scripts/
./core-api/alembic/      →    /app/alembic/
./frontend/              →    /app/
./services/ui/bot-service/src/ → /app/src/
```

## 🚫 What NOT to Do

### ❌ Don't Copy Files
```bash
# DON'T DO THIS - volumes handle it automatically
docker cp file.py container:/app/
docker cp container:/app/file.py ./
```

### ❌ Don't Edit Inside Containers
```bash
# DON'T DO THIS - edit on host instead
docker exec -it container vim /app/file.py
```

### ❌ Don't Restart for Code Changes
```bash
# DON'T DO THIS - hot reload handles it
docker compose restart core-api  # Not needed for code changes
```

## ✅ What TO Do

### ✅ Edit on Host
```bash
# DO THIS - edit directly on host
vim core-api/src/main.py
vim frontend/src/components/Chat.tsx
```

### ✅ Use Make Commands
```bash
# DO THIS - use provided commands
make shell-api     # For debugging
make db-reset      # For database operations
make logs-api      # For monitoring
```

### ✅ Check Container Status
```bash
# DO THIS - monitor health
make status
make health
```

## 🔍 Troubleshooting

### File Changes Not Reflected
```bash
# Check volume mounts
docker compose exec core-api ls -la /app/src/

# Verify file timestamps
docker compose exec core-api stat /app/src/main.py
stat core-api/src/main.py
```

### Permission Issues
```bash
# Check file ownership
ls -la core-api/src/
docker compose exec core-api ls -la /app/src/

# Fix if needed (rare)
sudo chown -R $USER:$USER core-api/
```

### Container Won't Start
```bash
# Check logs
make logs-api

# Rebuild if needed
docker compose build core-api
make up
```

## 🎯 Key Advantages

1. **Seamless Development**: Edit files on host, see changes in container
2. **No Sync Issues**: Direct volume mounts eliminate synchronization problems
3. **Tool Compatibility**: Use your favorite host-based editors and IDEs
4. **Debugging**: Easy access to logs and shell access when needed
5. **Database Management**: Scripts accessible from both host and container

## 📋 Quick Reference

```bash
# Essential commands
make up           # Start everything
make down         # Stop everything
make logs-api     # View API logs
make shell-api    # Debug API
make db-reset     # Reset database
make status       # Check health

# File locations (all editable on host)
core-api/src/           # API source code
frontend/src/           # Frontend source code
core-api/scripts/       # Database scripts
core-api/alembic/       # Database migrations
```

This setup provides a **true development environment** where you work entirely on the host filesystem while containers provide the runtime environment. 