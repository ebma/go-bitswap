#!/bin/bash

RUNNER="local:exec"
BUILDER="exec:go"

echo "Cleaning previous results..."

rm -rf ./results
mkdir ./results

FILE_SIZE=15728640
#FILE_SIZE=15728640,31457280,47185920,57671680
RUN_COUNT=5
INSTANCES=10
SEED_COUNT=3
LEECH_COUNT=1
EAVESDROPPER_COUNT=1
LATENCY=10
JITTER=10
BANDWIDTH=1500
PARALLEL_GEN=1000
TESTCASE=transfer
INPUT_DATA=files # 'random' does not work locally due to permissions of /tmp directory
DATA_DIR=./test-datasets # This directory is relative to where the testground daemon is started (?)
TCP_ENABLED=false
MAX_CONNECTION_RATE=100

source ./exec.sh

eval $CMD

docker rm -f testground-redis
