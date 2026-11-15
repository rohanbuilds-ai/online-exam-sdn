#!/usr/bin/env bash
# ==============================================================================
# Run Complete Test and Benchmark Suite
# ==============================================================================
set -e
cd "$(dirname "$0")/.."

echo "=== [1/2] Running Unit and Concurrency Integration Test Suite ==="
python3 -m unittest discover -s tests -v

echo "=== [2/2] Running Benchmark Experiments and Generating Visual Plots ==="
python3 experiments/run_experiments.py

echo "=== All Tests and Experiments Finished Successfully! ==="
