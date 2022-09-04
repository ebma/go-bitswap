#!/bin/bash

echo "Cleaning previous results..."
RUNNER="local:docker"

rm -rf ./results
mkdir ./results

source ../scripts/exec.sh

echo "[*] Running Experiment"
run_composition ./composition-docker.toml
# Plot in pdf
python3 ../scripts/pdf.py
# Check adversary predictions
python3 ../scripts/first-timestamp-estimator.py -rdir=../experiments/results

#echo "Cleaning previous results..."
#rm -rf ./results
#mkdir ./results
#
#echo "[*] Running baseline"
#run_composition ./baseline-docker.toml
## Plot in pdf
#python3 ../scripts/pdf.py baseline
## Check adversary predictions
#python3 ../scripts/first-timestamp-estimator.py -rdir=../experiments/results
