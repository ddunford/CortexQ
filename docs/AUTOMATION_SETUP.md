# Automated Ollama Model Setup

This document explains the multiple automation features implemented to ensure Ollama AI models are automatically available when you start the system.

## 🤖 Automation Features

### 1. **Docker Compose Init Container** 
Automatically pulls models when services start:

```yaml
# In docker-compose.yml
ollama-init:
  image: ollama/ollama:latest
  depends_on:
    ollama:
      condition: service_healthy
  command: >
    sh -c "
      echo 'Waiting for Ollama to be ready...' &&
      until curl -s http://ollama:11434/api/tags > /dev/null 2>&1; do
        sleep 5
      done &&
      if [ $$(curl -s http://ollama:11434/api/tags | grep -c '\"models\":\\[\\]') -eq 1 ]; then
        ollama pull llama3.2:1b &&
        echo 'Model pulled successfully!'
      fi
    "
```

### 2. **Intelligent LLM Service**
The LLM service automatically detects and manages models:

```python
# In core-api/src/llm_service.py
class LLMService:
    def __init__(self):
        self.preferred_models = [
            "llama3.2:1b",      # Lightweight, fast
            "llama3.1:8b",      # More capable
            "llama2:7b",        # Fallback
        ]
        self._initialize_model()  # Auto-detect best available
    
    def _initialize_model(self):
        available_models = self._get_available_models()
        
        if not available_models:
            # Auto-pull default model if none exist
            self._auto_pull_model("llama3.2:1b")
        
        # Select best available model from preferences
        self.model = self._select_best_model(available_models)
```

### 3. **Makefile Commands**
Easy commands for model management:

```bash
# Complete startup with AI models
make up-full

# Initialize models manually
make init-ollama

# List available models
make ollama-models

# Pull specific models
make ollama-pull MODEL=llama3.2:1b
```

### 4. **Initialization Script**
Robust shell script with error handling:

```bash
# scripts/init-ollama.sh
#!/bin/bash
# - Waits for Ollama to be ready
# - Checks if models exist
# - Pulls lightweight model if needed
# - Provides detailed logging
```

## 🚀 Usage Scenarios

### Scenario 1: Fresh Installation
```bash
git clone <repo>
cd rag_chat
make up-full
```
**Result**: Complete system ready with AI models in ~2-5 minutes

### Scenario 2: Development Restart
```bash
make restart
```
**Result**: Services restart, models already available (no re-download)

### Scenario 3: Model Management
```bash
# Check what's available
make ollama-models

# Add more capable model
make ollama-pull MODEL=llama3.1:8b

# System automatically uses best available model
```

### Scenario 4: Production Deployment
- **Docker Compose**: Init container ensures models are ready
- **LLM Service**: Falls back gracefully if models fail
- **Health Checks**: Verify all components before marking ready

## 🔧 Configuration Options

### Model Preferences
Edit `core-api/src/llm_service.py`:
```python
self.preferred_models = [
    "your-preferred-model",
    "fallback-model-1", 
    "fallback-model-2",
]
```

### Default Model
Edit `scripts/init-ollama.sh`:
```bash
MODEL_NAME="your-default-model"
```

### Timeouts and Retries
```bash
# In init-ollama.sh
MAX_RETRIES=30        # How long to wait for Ollama
RETRY_DELAY=5         # Seconds between checks

# In llm_service.py  
timeout=300           # 5 minutes for model download
```

## 🐛 Troubleshooting

### Models Not Loading
```bash
# Check Ollama status
docker compose ps ollama
docker compose logs ollama

# Manual model pull
docker compose exec ollama ollama pull llama3.2:1b

# Check available models
make ollama-models
```

### Service Not Starting
```bash
# Check all service health
make health

# View detailed logs
make logs-api

# Reset everything
make clean && make up-full
```

### Chat Not Working
```bash
# Test the pipeline
python3 test_chat.py

# Check logs for LLM errors
docker compose logs core-api | grep -i "llm\|model"
```

## 📊 Model Comparison

| Model | Size | RAM Needed | Speed | Quality | Use Case |
|-------|------|------------|-------|---------|----------|
| llama3.2:1b | ~1GB | 2GB | Fast | Good | Development, demos |
| llama3.1:8b | ~4.7GB | 8GB | Medium | Excellent | Production |
| llama2:7b | ~3.8GB | 6GB | Medium | Good | Fallback |
| codellama:7b | ~3.8GB | 6GB | Medium | Code-focused | Developer tools |

## 🔒 Security Considerations

### Model Downloads
- Models downloaded from Ollama's official registry
- Init scripts include checksum verification
- Timeout limits prevent hanging downloads

### Resource Limits
- Docker containers have memory limits
- Download timeouts prevent infinite waits
- Health checks ensure system stability

### Production Hardening
```yaml
# Recommended docker-compose.yml additions
ollama:
  deploy:
    resources:
      limits:
        memory: 8G
        cpus: '4'
      reservations:
        memory: 2G
```

## 🎯 Performance Optimization

### Fast Startup
1. **Volume Persistence**: Models persist between restarts
2. **Conditional Pulling**: Only download if missing
3. **Parallel Initialization**: Services start while models load
4. **Health Checks**: Don't mark ready until models loaded

### Memory Management
```bash
# Monitor resource usage
docker stats ollama
docker stats core-api

# Optimize model selection
make ollama-pull MODEL=llama3.2:1b  # Lightweight option
```

This automation ensures a smooth experience where users can start the system and immediately have a fully functional AI-powered RAG chat system without manual intervention. 