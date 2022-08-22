#!/bin/bash

RUNNER="local:docker"
BUILDER="docker:go"

echo "Cleaning previous results..."

rm -rf ./results
mkdir ./results

FILE_SIZE=15728640
#FILE_SIZE=15728640,31457280,47185920,57671680
RUN_COUNT=2
INSTANCES=10
LEECH_COUNT=3
PASSIVE_COUNT=0
LATENCY=10
JITTER=10
BANDWIDTH=150
PARALLEL_GEN=100
TESTCASE=bitswap-transfer
#INPUT_DATA=random
#DATA_DIR=./ # To use 'random' the DATA_DIR has to be set to something for the script to work properly
INPUT_DATA=files
DATA_DIR=../plan/test-datasets
TCP_ENABLED=false
MAX_CONNECTION_RATE=100

source ./exec.sh

eval $CMD

docker rm -f testground-redis
