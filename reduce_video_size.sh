#!/bin/bash

if [ -z "$1" ]; then
    echo "Error: Please provide a filename as argument"
    echo "Usage: $0 input_filename [quality_reduction_percent (0-100)]"
    exit 1
fi

INPUT_FILENAME=$1
QUALITY_REDUCTION=${2:-0}

if ! [[ "$QUALITY_REDUCTION" =~ ^[0-9]+$ ]] || [ "$QUALITY_REDUCTION" -lt 0 ] || [ "$QUALITY_REDUCTION" -gt 100 ]; then
    echo "Error: Quality reduction must be a number between 0 and 100"
    exit 1
fi

CQ=$(awk "BEGIN { printf \"%.0f\", ($QUALITY_REDUCTION / 100) * 51 }")

OUTPUT_FILENAME="${INPUT_FILENAME%.*}_reduced.${INPUT_FILENAME##*.}"

if [ ! -f "$INPUT_FILENAME" ]; then
    echo "Error: File $INPUT_FILENAME does not exist"
    exit 1
fi

echo "Reducing video size for file $INPUT_FILENAME with FFMPEG"
echo "Using quality reduction: $QUALITY_REDUCTION% → CQ level: $CQ"

ffmpeg -hwaccel cuda -i "$INPUT_FILENAME" -c:v hevc_nvenc -preset fast -cq $CQ "$OUTPUT_FILENAME"
