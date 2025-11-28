#!/bin/bash
# Run batch generation while keeping the system awake

echo "Starting batch generation with caffeinate..."
echo "System will stay awake until completion."
echo "Logs: batch_generate.log and batch_output.log"
echo ""

caffeinate -i python3 batch_generate.py 2>&1 | tee batch_output.log

echo ""
echo "Batch generation complete. System sleep restored."
