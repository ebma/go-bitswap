#!/bin/bash

RUNNER="local:docker"

mkdir ./results

source ../scripts/exec.sh

echo "[*] Running Experiment for file ./composition-docker-$1-eaves.toml"
run_composition ./composition-docker-"$1"-eaves.toml
# Plot in pdf
python3 ../scripts/pdf.py
