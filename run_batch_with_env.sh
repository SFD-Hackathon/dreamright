#!/bin/bash
# Load environment variables and run batch generation

# Change to script directory
cd "$(dirname "$0")"

# Load API key from .env
export $(grep -v '^#' .env | xargs)

# Run batch generation
python3 batch_generate.py
