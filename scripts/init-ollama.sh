#!/bin/bash

# Ollama Model Initialization Script
# This script automatically pulls required models for the RAG system

set -e

echo "🚀 Starting Ollama model initialization..."

# Configuration
OLLAMA_URL="http://localhost:11434"
PRIMARY_MODEL="llama3.1:8b"     # More capable model for better responses
FALLBACK_MODEL="llama3.2:1b"    # Lightweight fallback
MAX_RETRIES=30
RETRY_DELAY=5

# Function to check if Ollama is ready
check_ollama_ready() {
    curl -s "${OLLAMA_URL}/api/tags" > /dev/null 2>&1
}

# Function to check if model exists
check_model_exists() {
    local model_name=$1
    local models=$(curl -s "${OLLAMA_URL}/api/tags" | grep -o '"models":\[[^]]*\]')
    echo "$models" | grep -q "$model_name"
}

# Function to pull model with error handling
pull_model() {
    local model_name=$1
    echo "📥 Pulling model: $model_name..."
    if docker compose exec ollama ollama pull "$model_name"; then
        echo "✅ Successfully pulled model $model_name"
        return 0
    else
        echo "❌ Failed to pull model $model_name"
        return 1
    fi
}

# Wait for Ollama to be ready
echo "⏳ Waiting for Ollama to be ready..."
retry_count=0
while ! check_ollama_ready; do
    if [ $retry_count -ge $MAX_RETRIES ]; then
        echo "❌ Ollama failed to start after $MAX_RETRIES attempts"
        exit 1
    fi
    
    echo "Ollama not ready, waiting ${RETRY_DELAY} seconds... (attempt $((retry_count + 1))/$MAX_RETRIES)"
    sleep $RETRY_DELAY
    retry_count=$((retry_count + 1))
done

echo "✅ Ollama is ready!"

# Check for and pull models
models_pulled=0

# Try to pull primary model (more capable)
if check_model_exists "$PRIMARY_MODEL"; then
    echo "✅ Primary model $PRIMARY_MODEL already exists"
    models_pulled=$((models_pulled + 1))
else
    echo "📥 Primary model $PRIMARY_MODEL not found, attempting to pull..."
    if pull_model "$PRIMARY_MODEL"; then
        models_pulled=$((models_pulled + 1))
    else
        echo "⚠️ Failed to pull primary model, will try fallback model"
    fi
fi

# Try to pull fallback model if primary failed or as backup
if check_model_exists "$FALLBACK_MODEL"; then
    echo "✅ Fallback model $FALLBACK_MODEL already exists"
    models_pulled=$((models_pulled + 1))
else
    echo "📥 Fallback model $FALLBACK_MODEL not found, attempting to pull..."
    if pull_model "$FALLBACK_MODEL"; then
        models_pulled=$((models_pulled + 1))
    else
        echo "❌ Failed to pull fallback model"
    fi
fi

# Check results
if [ $models_pulled -eq 0 ]; then
    echo "❌ No models were successfully pulled!"
    exit 1
else
    echo "🎉 Ollama initialization complete! ($models_pulled model(s) available)"
fi

echo "💡 Available models:"
curl -s "${OLLAMA_URL}/api/tags" | jq -r '.models[].name' 2>/dev/null || echo "jq not available, using raw output:"
curl -s "${OLLAMA_URL}/api/tags" 