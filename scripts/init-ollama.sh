#!/bin/bash

# Ollama Model Initialization Script
# This script automatically pulls required models for the RAG system

set -e

echo "🚀 Starting Ollama model initialization..."

# Configuration
OLLAMA_URL="http://localhost:11434"
MODEL_NAME="llama3.2:1b"
MAX_RETRIES=30
RETRY_DELAY=5

# Function to check if Ollama is ready
check_ollama_ready() {
    curl -s "${OLLAMA_URL}/api/tags" > /dev/null 2>&1
}

# Function to check if model exists
check_model_exists() {
    local models=$(curl -s "${OLLAMA_URL}/api/tags" | grep -o '"models":\[[^]]*\]')
    echo "$models" | grep -q "$MODEL_NAME"
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

# Check if model already exists
if check_model_exists; then
    echo "✅ Model $MODEL_NAME already exists, skipping pull."
else
    echo "📥 Model $MODEL_NAME not found, pulling..."
    if docker compose exec ollama ollama pull "$MODEL_NAME"; then
        echo "✅ Successfully pulled model $MODEL_NAME"
    else
        echo "❌ Failed to pull model $MODEL_NAME"
        exit 1
    fi
fi

echo "🎉 Ollama initialization complete!"
echo "💡 Available models:"
curl -s "${OLLAMA_URL}/api/tags" | jq -r '.models[].name' 2>/dev/null || echo "jq not available, using raw output:"
curl -s "${OLLAMA_URL}/api/tags" 