package utils

import (
	"context"
	"github.com/ipfs/go-datastore"
	dht "github.com/libp2p/go-libp2p-kad-dht"
	"github.com/libp2p/go-libp2p-kad-dht/dual"
	record "github.com/libp2p/go-libp2p-record"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/peer"
	"github.com/libp2p/go-libp2p/core/routing"
	"strings"
	"time"

	"github.com/testground/sdk-go/network"
	"github.com/testground/sdk-go/runtime"
	"github.com/testground/sdk-go/sync"
)

// SetupNetwork instructs the sidecar (if enabled) to setup the network for this
// test case.
func SetupNetwork(
	ctx context.Context,
	runenv *runtime.RunEnv,
	nwClient *network.Client,
	latency time.Duration,
) error {

	if !runenv.TestSidecar {
		return nil
	}

	// Wait for the network to be initialized.
	if err := nwClient.WaitNetworkInitialized(ctx); err != nil {
		return err
	}

	cfg := &network.Config{
		Network:       "default",
		Enable:        true,
		RoutingPolicy: network.AllowAll,
		Default: network.LinkShape{
			Latency: latency,
		},
		CallbackState:  sync.State("network-configured"),
		CallbackTarget: runenv.TestInstanceCount,
	}

	return nwClient.ConfigureNetwork(ctx, cfg)
}

// If there's a latency specific to the node type, overwrite the default latency
func getLatency(
	runenv *runtime.RunEnv,
	nodetp NodeType,
	tpindex int,
	baseLatency time.Duration,
) (time.Duration, error) {
	if nodetp == Seed {
		return getTypeLatency(runenv, "seed_latency_ms", tpindex, baseLatency)
	} else if nodetp == Leech {
		return getTypeLatency(runenv, "leech_latency_ms", tpindex, baseLatency)
	}
	return baseLatency, nil
}

// If the parameter is a comma-separated list, each value in the list
// corresponds to the type index. For example:
// seed_latency_ms=100,200,400
// means that
// - the first seed has 100ms latency
// - the second seed has 200ms latency
// - the third seed has 400ms latency
// - any subsequent seeds have defaultLatency
func getTypeLatency(
	runenv *runtime.RunEnv,
	param string,
	tpindex int,
	baseLatency time.Duration,
) (time.Duration, error) {
	// No type specific latency set, just return the default
	if !runenv.IsParamSet(param) {
		return baseLatency, nil
	}

	// Not a comma-separated list, interpret the value as an int and apply
	// the same latency to all peers of this type
	if !strings.Contains(runenv.StringParam(param), ",") {
		return baseLatency + time.Duration(runenv.IntParam(param))*time.Millisecond, nil
	}

	// Comma separated list, the position in the list corresponds to the
	// type index
	latencies, err := ParseIntArray(runenv.StringParam(param))
	if err != nil {
		return 0, err
	}
	if tpindex < len(latencies) {
		return baseLatency + time.Duration(latencies[tpindex])*time.Millisecond, nil
	}

	// More peers of this type than entries in the list. Return the default
	// latency for peers not covered by list entries
	return baseLatency, nil
}

// ModeOpt describes what mode the dht should operate in
type ModeOpt = int

const (
	// ModeAuto utilizes EvtLocalReachabilityChanged events sent over the event bus to dynamically switch the DHT
	// between Client and Server modes based on network conditions
	ModeAuto ModeOpt = iota
	// ModeClient operates the DHT as a client only, it cannot respond to incoming queries
	ModeClient
	// ModeServer operates the DHT as a server, it can both send and respond to queries
	ModeServer
	// ModeAutoServer operates in the same way as ModeAuto, but acts as a server when reachability is unknown
	ModeAutoServer
)

func constructDHTRouting(
	ctx context.Context,
	host host.Host,
	dstore datastore.Batching,
	validator record.Validator,
	bootstrapPeers ...peer.AddrInfo,
) (routing.Routing, error) {
	// 0 resolves to ModeAuto
	var mode = 0
	return dual.New(
		ctx, host,
		dual.DHTOption(
			dht.Concurrency(10),
			dht.Mode(dht.ModeOpt(mode)),
			dht.Datastore(dstore),
			dht.Validator(validator)),
		dual.WanDHTOption(dht.BootstrapPeers(bootstrapPeers...)),
	)
}
