#!/bin/bash

# list_comfy_models.sh
# Outputs a JSON list of all valid model files in a ComfyUI models directory.
# Filters out Windows metadata files (e.g., :Zone.Identifier, Thumbs.db, desktop.ini).
# Usage: ./list_comfy_models.sh [path/to/models] > models.json

set -euo pipefail

# Default path assumes your layout; override via first argument
MODELS_DIR="${1:-$HOME/Documents/git/n8n-stuff/models}"

if [[ ! -d "$MODELS_DIR" ]]; then
    echo "Error: Models directory not found: $MODELS_DIR" >&2
    exit 1
fi

echo '{'
echo '  "models": ['

first_model=true

# Loop through each subdirectory (model type)
for model_type in "$MODELS_DIR"/*/; do
    [[ -d "$model_type" ]] || continue
    type_name=$(basename "$model_type")

    # Find all files, excluding Windows junk, and sort
    while IFS= read -r -d '' file; do
        # Get relative path from models root
        rel_path="${file#$MODELS_DIR/}"
        filename=$(basename "$file")

        # Add comma if not first entry
        if [[ "$first_model" == true ]]; then
            first_model=false
        else
            echo ','
        fi

        # Output JSON object with properly escaped strings
        printf '    {\n      "type": %s,\n      "filename": %s,\n      "path": %s\n    }' \
            "$(jq -n --arg v "$type_name" '$v')" \
            "$(jq -n --arg v "$filename" '$v')" \
            "$(jq -n --arg v "$rel_path" '$v')"

    done < <(find "$model_type" -type f \
              ! -name "*:Zone.Identifier" \
              ! -name "Thumbs.db" \
              ! -name "desktop.ini" \
              -print0 | sort -z)

done

echo
echo '  ]'
echo '}'