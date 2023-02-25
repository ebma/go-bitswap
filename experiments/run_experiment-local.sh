#!/bin/bash

RUNNER="local:exec"

mkdir ./results

source ../scripts/exec.sh

echo "[*] Running Experiment"
run_composition ./composition-local.toml
# Plot in pdf
python3 ../scripts/pdf.py
