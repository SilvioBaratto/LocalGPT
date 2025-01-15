#!/bin/bash

# Check if both model names were provided as arguments
# if [ -z "$1" ] || [ -z "$2" ]; then
#   echo "Usage: $0 <MODEL_NAME> <EMBEDDING_MODEL_NAME>"
#   exit 1
# fi

# # Assign the provided arguments to variables
# MODEL_NAME=$1
# EMBEDDING_MODEL_NAME=$2

# Start Ollama in the background.
/bin/ollama serve &
# Record Process ID.
pid=$!

# Pause for Ollama to start.
sleep 5

echo "🔴 Retrieve $EMBEDDING_MODEL_NAME embedding model..."
ollama pull "$EMBEDDING_MODEL_NAME"
echo "🟢 Done!"

# Wait for Ollama process to finish.
wait $pid
ollama run "$EMBEDDING_MODEL_NAME"