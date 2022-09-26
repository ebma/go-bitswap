#!/bin/bash

TESTGROUND_BIN="testground"
CMD="run $TESTCASE $INSTANCES $FILE_SIZE $RUN_COUNT $LATENCY $JITTER $PARALLEL_GEN $LEECH_COUNT $BANDWIDTH $INPUT_DATA $DATA_DIR $TCP_ENABLED $MAX_CONNECTION_RATE $SEED_COUNT $EAVESDROPPER_COUNT $TRICKLING_DELAY_MS"
# RUNNER="local:exec"
# BUILDER="exec:go"

echo "Starting test..."

run_bitswap(){
    $TESTGROUND_BIN run single \
        --build-cfg skip_runtime_image=true \
        --plan=trickle-bitswap \
        --testcase=$1 \
        --builder=$BUILDER \
        --runner=$RUNNER --instances=$2 \
        -tp file_size=$3 \
        -tp run_count=$4 \
        -tp latency_ms=$5 \
        -tp jitter_pct=$6 \
        -tp parallel_gen_mb=$7 \
        -tp leech_count=$8 \
        -tp bandwidth_mb=$9 \
        -tp input_data=${10} \
        -tp data_dir=${11} \
        -tp enable_tcp=${12} \
        -tp max_connection_rate=${13} \
        -tp seed_count=${14} \
        -tp eavesdropper_count=${15} \
        -tp trickling_delay_ms=${16}
        # | tail -n 1 | awk -F 'run with ID: ' '{ print $2 }'
}

run() {
    echo "Running test with ($1, $2, $3, $4, $5, $6, $7, $8, $9, ${10}, ${11}, ${12}, ${13}, ${14}, ${15}, ${16}) (TESTCASE, INSTANCES, FILE_SIZE, RUN_COUNT, LATENCY, JITTER, PARALLEL, LEECH, BANDWIDTH, INPUT_DATA, DATA_DIR, TCP_ENABLED, MAX_CONNECTION_RATE, SEED_COUNT, EAVESDROPPER_COUNT, TRICKLING_DELAY_MS)"
    TESTID=`run_bitswap $1 $2 $3 $4 $5 $6 $7 $8 $9 ${10} ${11} ${12} ${13} ${14} ${15} ${16}| tail -n 1 | awk -F 'run is queued with ID:' '{ print $2 }'`
    checkstatus $TESTID
    # `run_bitswap $1 $2 $3 $4 $5 $6 $7 $8 $9 ${10} ${11} ${12} ${13} ${14}| tail -n 1 | awk -F 'run with ID: ' '{ print $2 }'`
    # echo $TESTID
    # echo "Finished test $TESTID"
    $TESTGROUND_BIN collect --runner=$RUNNER $TESTID
    tar xzvf $TESTID.tgz
    rm $TESTID.tgz
    mv $TESTID ./results/
    echo "Collected results"
}

getstatus() {
    STATUS=`testground status --task $1 | tail -n 4 | awk -F 'Status:' '{ print $2 }'`
    echo ${STATUS//[[:blank:]]/}
}

checkstatus(){
    STATUS="none"
    while [ "$STATUS" != "complete" ]
    do
        STATUS=`getstatus $1`
        echo "Getting status: $STATUS"
        sleep 10s
    done
    echo "Task completed"
}

run_composition() {
    echo "Running composition test for $1"
    TESTID=`testground run composition -f $1 | tail -n 1 | awk -F 'run is queued with ID:' '{ print $2 }'`
    checkstatus $TESTID
    $TESTGROUND_BIN collect --runner=$RUNNER $TESTID
    tar xzvf $TESTID.tgz
    rm $TESTID.tgz
    mv $TESTID ./results/
    echo "Collected results"
}

# checkstatus bub74h523089p79be5ng