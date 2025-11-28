#!/bin/bash
# Load environment variables and run batch generation

# Load API key from .env
export $(grep -v '^#' .env | xargs)

# Run batch generation
python3 batch_generate.py
