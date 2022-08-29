package main

import (
	"github.com/ipfs/testground/plans/trickle-bitswap/test"
	"github.com/testground/sdk-go/run"
)

func main() {
	run.InvokeMap(testcases)
}

var testcases = map[string]interface{}{
	"speedtest": run.InitializedTestCaseFn(test.BitswapSpeedTest),
	"transfer":  run.InitializedTestCaseFn(test.BitswapTransferTest),
}
