#!/bin/bash

RUNNER="local:docker"

mkdir ./results

source ../scripts/exec.sh

echo "[*] Running Experiment ./composition-docker-baseline.toml"
run_composition ./composition-docker-baseline.toml
# Plot in pdf
python3 ../scripts/pdf.py
