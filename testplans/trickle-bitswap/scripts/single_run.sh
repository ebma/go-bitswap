#!/bin/bash

#RUNNER="local:docker"
#BUILDER="docker:go"
# RUNNER="cluster:k8s"
# BUILDER="docker:go"
RUNNER="local:exec"
BUILDER="exec:go"

echo "Cleaning previous results..."

rm -rf ./results
mkdir ./results

FILE_SIZE=15728640
# FILE_SIZE=15728640,31457280,47185920,57671680
RUN_COUNT=2
INSTANCES=5
LEECH_COUNT=3
PASSIVE_COUNT=0
LATENCY=10
JITTER=10
BANDWIDTH=150
PARALLEL_GEN=100
TESTCASE=bitswap-transfer
INPUT_DATA=files
#DATA_DIR=../extra/test-datasets # This would be for the docker:go runner
DATA_DIR=/home/marcel/Documents/Studies/thesis/trickle-bitswap/go-bitswap/testplans/trickle-bitswap/test-datasets # This is for the local runner
TCP_ENABLED=false
MAX_CONNECTION_RATE=100

source ./exec.sh

eval $CMD

docker rm -f testground-redis
