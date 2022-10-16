#!/bin/bash

RUNNER="local:docker"

mkdir ../../experiments/results

source ../scripts/exec.sh

echo "[*] Running Experiment"
run_composition ./composition-docker-1-eaves.toml
# Plot in pdf
python3 ../scripts/pdf.py
