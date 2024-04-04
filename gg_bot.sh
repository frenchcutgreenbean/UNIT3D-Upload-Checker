#!/bin/bash

# Check if the input file path is provided as an argument
if [ $# -ne 1 ]; then
    echo "Usage: $0 <input_file>"
    exit 1
fi

input_file="$1"

# Check if the input file exists
if [ ! -f "$input_file" ]; then
    echo "Error: Input file not found"
    exit 1
fi

# Loop through each line in the file
while IFS= read -r line; do
    # Run the Python script with the command from the current line
    $line
done < "$input_file"