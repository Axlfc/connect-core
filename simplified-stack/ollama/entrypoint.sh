#!/bin/sh
set -e

# Start ollama serve in the background
ollama serve &
pid=$!

# Wait for the server to be ready
echo "Waiting for Ollama server to start..."
while ! ollama list >/dev/null 2>&1; do
    sleep 1
done
echo "Ollama server started."

# Pull models defined in OLLAMA_MODEL_ environment variables
echo "Searching for models to download..."
found_models=false
# Use printenv to get all environment variables, grep for OLLAMA_MODEL_
# and then loop through the results
for var in $(printenv | grep '^OLLAMA_MODEL_'); do
    # Use cut to extract the value after the '='
    model=$(echo "$var" | cut -d= -f2-)
    if [ -n "$model" ]; then
        echo "Pulling model: $model"
        ollama pull "$model"
        found_models=true
    fi
done

if [ "$found_models" = false ]; then
    echo "No models found with OLLAMA_MODEL_ prefix. Skipping automatic download."
fi

echo "Model pulling process complete. Ollama is running."
# Bring the background server process to the foreground
wait $pid
