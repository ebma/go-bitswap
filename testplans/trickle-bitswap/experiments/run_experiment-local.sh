#!/bin/bash

echo "Cleaning previous results..."
RUNNER="local:exec"

rm -rf ./results
mkdir ./results

source ../scripts/exec.sh

echo "[*] Running Experiment"
run_composition ./composition-local.toml
# Plot in pdf
python3 ../scripts/pdf.py "RFC102"


echo "Cleaning previous results..."
rm -rf ./results
mkdir ./results

echo "[*] Running baseline"
run_composition ./baseline-local.toml
# Plot in pdf
python3 ../testbed/testbed/scripts/pdf.py "RFC102" baseline