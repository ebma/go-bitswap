#!/bin/bash

RUNNER="local:docker"
BUILDER="docker:go"

echo "Cleaning previous results..."

rm -rf ./results
mkdir ./results

FILE_SIZE=15728640
#FILE_SIZE=15728640,31457280,47185920,57671680
RUN_COUNT=100
# Somehow works if LEECH_COUNT is set to INSTANCES-1 and the test doesn't hang (??)
INSTANCES=20
LEECH_COUNT=1
SEED_COUNT=1
EAVESDROPPER_COUNT=1
TRICKLING_DELAY_MS="0,50,100,150,200"
LATENCY=50
JITTER=00
BANDWIDTH=100
PARALLEL_GEN=100
TESTCASE=transfer
INPUT_DATA=files
DATA_DIR=../plan/test-datasets
TCP_ENABLED=true
MAX_CONNECTION_RATE=100

source ./exec.sh

eval $CMD

docker rm -f testground-redis
