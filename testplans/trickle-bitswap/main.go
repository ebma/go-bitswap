package main

import (
	"github.com/testground/sdk-go/run"
)

func main() {
	run.InvokeMap(testcases)
}

var testcases = map[string]interface{}{
	"bitswap-speedtest": run.InitializedTestCaseFn(BitswapSpeedTest),
	"bitswap-transfer":  run.InitializedTestCaseFn(BitswapTransferTest),
}
