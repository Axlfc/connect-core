#!/bin/bash

# Comprueba si se ha pasado un nombre de archivo
if [ -z "$1" ]; then
    echo "Uso: $0 <archivo.env>"
    exit 1
fi

INPUT_FILE="$1"
OUTPUT_FILE="${INPUT_FILE}.uninitialized" # Nombre del archivo de salida

# Comprueba si el archivo existe
if [ ! -f "$INPUT_FILE" ]; then
    echo "Error: El archivo '$INPUT_FILE' no existe."
    exit 1
fi

# El comando principal que realiza la transformación
# NOTA: Utiliza sed para buscar la variable, el '=', y cualquier cosa detrás, 
# y lo reemplaza solo por la variable y el '='.
# Se ignora la transformación en líneas que empiezan por '#' (comentarios)
sed '/^[[:space:]]*#/!s/^\([[:alnum:]_]*\)=.*/\1=/' "$INPUT_FILE" > "$OUTPUT_FILE"

echo "✅ Variables desinicializadas guardadas en: $OUTPUT_FILE"
echo "Contenido del archivo de salida:"
echo "-----------------------------------"
cat "$OUTPUT_FILE"
echo "-----------------------------------"
