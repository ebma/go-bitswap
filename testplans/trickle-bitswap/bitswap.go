package main

import (
	"context"
	"fmt"
	"github.com/ipfs/testground/plans/trickle-bitswap/utils"
	"github.com/ipfs/testground/plans/trickle-bitswap/utils/dialer"
	"github.com/libp2p/go-libp2p"
	"github.com/libp2p/go-libp2p-core/crypto"
	"github.com/libp2p/go-libp2p-core/host"
	"github.com/libp2p/go-libp2p-core/peer"
	"github.com/testground/sdk-go/network"
	"time"

	"github.com/testground/sdk-go/run"
	"github.com/testground/sdk-go/runtime"
	"github.com/testground/sdk-go/sync"
)

// TestVars testing variables
type TestVars struct {
	ExchangeInterface string
	Timeout           time.Duration
	RunTimeout        time.Duration
	LeechCount        int
	PassiveCount      int
	RequestStagger    time.Duration
	RunCount          int
	MaxConnectionRate int
	TCPEnabled        bool
	SeederRate        int
	DHTEnabled        bool
	ProvidingEnabled  bool
	LlEnabled         bool
	Dialer            string
	NumWaves          int
	DiskStore         bool
}

type TestData struct {
	client              *sync.DefaultClient
	nwClient            *network.Client
	nConfig             *utils.NodeConfig
	peerInfos           []utils.PeerInfo
	dialFn              dialer.Dialer
	signalAndWaitForAll func(state string) error
	seq                 int64
	grpseq              int64
	nodetp              utils.NodeType
	tpindex             int
	seedIndex           int64
}

type NodeTestData struct {
	*TestData
	node utils.Node
	host *host.Host
}

// Launch bitswap nodes and connect them to each other.
func BitswapTransferTest(runenv *runtime.RunEnv, initCtx *run.InitContext) error {
	testvars, err := getEnvVars(runenv)
	if err != nil {
		return err
	}

	/// --- Set up
	ctx, cancel := context.WithTimeout(context.Background(), testvars.Timeout)
	defer cancel()
	baseT, err := initializeTest(ctx, runenv, testvars)
	if err != nil {
		return err
	}
	t, err := initializeBitswapTest(ctx, runenv, testvars, baseT)
	runenv.RecordMessage("created node %s with addrs", t.peerInfos)
	//transferNode := t.node
	//signalAndWaitForAll := t.signalAndWaitForAll
	//
	//// Start still alive process if enabled
	//t.stillAlive(runenv, testvars)

	return nil
}

func initializeTest(ctx context.Context, runenv *runtime.RunEnv, testvars *TestVars) (*TestData, error) {
	client := sync.MustBoundClient(ctx, runenv)
	nwClient := network.NewClient(client, runenv)

	nConfig, err := utils.GenerateAddrInfo(nwClient.MustGetDataNetworkIP().String())
	if err != nil {
		runenv.RecordMessage("Error generating node config")
		return nil, err
	}

	peers := sync.NewTopic("peers", &peer.AddrInfo{})

	// Get sequence number of this host
	seq, err := client.Publish(ctx, peers, *nConfig.AddrInfo)
	if err != nil {
		return nil, err
	}
	// Type of node and identifiers assigned.
	grpseq, nodetp, tpindex, err := parseType(ctx, runenv, client, nConfig.AddrInfo, seq)
	if err != nil {
		return nil, err
	}

	peerInfos := sync.NewTopic("peerInfos", &utils.PeerInfo{})
	// Publish peer info for dialing
	_, err = client.Publish(ctx, peerInfos, &utils.PeerInfo{Addr: *nConfig.AddrInfo, Nodetp: nodetp})
	if err != nil {
		return nil, err
	}

	var dialFn dialer.Dialer = dialer.DialOtherPeers
	if testvars.Dialer == "sparse" {
		dialFn = dialer.SparseDial
	}

	var seedIndex int64
	if nodetp == utils.Seed {
		if runenv.TestGroupID == "" {
			// If we're not running in group mode, calculate the seed index as
			// the sequence number minus the other types of node (leech / passive).
			// Note: sequence number starts from 1 (not 0)
			seedIndex = seq - int64(testvars.LeechCount+testvars.PassiveCount) - 1
		} else {
			// If we are in group mode, signal other seed nodes to work out the
			// seed index
			seedSeq, err := getNodeSetSeq(ctx, client, nConfig.AddrInfo, "seeds")
			if err != nil {
				return nil, err
			}
			// Sequence number starts from 1 (not 0)
			seedIndex = seedSeq - 1
		}
	}
	runenv.RecordMessage("Seed index %v for: %v", &nConfig.AddrInfo.ID, seedIndex)

	// Get addresses of all peers
	peerCh := make(chan *utils.PeerInfo)
	sctx, cancelSub := context.WithCancel(ctx)
	if _, err := client.Subscribe(sctx, peerInfos, peerCh); err != nil {
		cancelSub()
		return nil, err
	}
	infos, err := dialer.PeerInfosFromChan(peerCh, runenv.TestInstanceCount)
	if err != nil {
		cancelSub()
		return nil, fmt.Errorf("no addrs in %d seconds", testvars.Timeout/time.Second)
	}
	cancelSub()
	runenv.RecordMessage("Got all addresses from other peers and network setup")

	/// --- Warm up

	// Signal that this node is in the given state, and wait for all peers to
	// send the same signal
	signalAndWaitForAll := func(state string) error {
		_, err := client.SignalAndWait(ctx, sync.State(state), runenv.TestInstanceCount)
		return err
	}

	return &TestData{client, nwClient,
		nConfig, infos, dialFn, signalAndWaitForAll,
		seq, grpseq, nodetp, tpindex, seedIndex}, nil
}

func initializeBitswapTest(ctx context.Context, runenv *runtime.RunEnv, testvars *TestVars, baseT *TestData) (*NodeTestData, error) {
	h, err := makeHost(baseT)
	if err != nil {
		return nil, err
	}
	runenv.RecordMessage("I am %s with addrs: %v", h.ID(), h.Addrs())

	// Use the same blockstore on all runs for the seed node
	bstoreDelay := time.Duration(runenv.IntParam("bstore_delay_ms")) * time.Millisecond

	dStore, err := utils.CreateDatastore(testvars.DiskStore, bstoreDelay)
	if err != nil {
		return nil, err
	}
	runenv.RecordMessage("created data store %T with params disk_store=%b", dStore, testvars.DiskStore)
	bstore, err := utils.CreateBlockstore(ctx, dStore)
	if err != nil {
		return nil, err
	}
	// Create a new bitswap node from the blockstore
	bsnode, err := utils.CreateBitswapNode(ctx, h, bstore)
	if err != nil {
		return nil, err
	}

	return &NodeTestData{baseT, bsnode, &h}, nil
}

func getNodeSetSeq(ctx context.Context, client *sync.DefaultClient, addrInfo *peer.AddrInfo, setID string) (int64, error) {
	topic := sync.NewTopic("nodes"+setID, &peer.AddrInfo{})

	return client.Publish(ctx, topic, addrInfo)
}

func parseType(ctx context.Context, runenv *runtime.RunEnv, client *sync.DefaultClient, addrInfo *peer.AddrInfo, seq int64) (int64, utils.NodeType, int, error) {
	leechCount := runenv.IntParam("leech_count")
	passiveCount := runenv.IntParam("passive_count")

	grpCountOverride := false
	if runenv.TestGroupID != "" {
		grpLchLabel := runenv.TestGroupID + "_leech_count"
		if runenv.IsParamSet(grpLchLabel) {
			leechCount = runenv.IntParam(grpLchLabel)
			grpCountOverride = true
		}
		grpPsvLabel := runenv.TestGroupID + "_passive_count"
		if runenv.IsParamSet(grpPsvLabel) {
			passiveCount = runenv.IntParam(grpPsvLabel)
			grpCountOverride = true
		}
	}

	var nodetp utils.NodeType
	var tpindex int
	grpseq := seq
	seqstr := fmt.Sprintf("- seq %d / %d", seq, runenv.TestInstanceCount)
	grpPrefix := ""
	if grpCountOverride {
		grpPrefix = runenv.TestGroupID + " "

		var err error
		grpseq, err = getNodeSetSeq(ctx, client, addrInfo, runenv.TestGroupID)
		if err != nil {
			return grpseq, nodetp, tpindex, err
		}

		seqstr = fmt.Sprintf("%s (%d / %d of %s)", seqstr, grpseq, runenv.TestGroupInstanceCount, runenv.TestGroupID)
	}

	// Note: seq starts at 1 (not 0)
	switch {
	case grpseq <= int64(leechCount):
		nodetp = utils.Leech
		tpindex = int(grpseq) - 1
	case grpseq > int64(leechCount+passiveCount):
		nodetp = utils.Seed
		tpindex = int(grpseq) - 1 - (leechCount + passiveCount)
	default:
		nodetp = utils.Passive
		tpindex = int(grpseq) - 1 - leechCount
	}

	runenv.RecordMessage("I am %s %d %s", grpPrefix+nodetp.String(), tpindex, seqstr)

	return grpseq, nodetp, tpindex, nil
}

func getEnvVars(runenv *runtime.RunEnv) (*TestVars, error) {
	tv := &TestVars{}
	if runenv.IsParamSet("exchange_interface") {
		tv.ExchangeInterface = runenv.StringParam("exchange_interface")
	}
	if runenv.IsParamSet("timeout_secs") {
		tv.Timeout = time.Duration(runenv.IntParam("timeout_secs")) * time.Second
	}
	if runenv.IsParamSet("run_timeout_secs") {
		tv.RunTimeout = time.Duration(runenv.IntParam("run_timeout_secs")) * time.Second
	}
	if runenv.IsParamSet("leech_count") {
		tv.LeechCount = runenv.IntParam("leech_count")
	}
	if runenv.IsParamSet("passive_count") {
		tv.PassiveCount = runenv.IntParam("passive_count")
	}
	if runenv.IsParamSet("request_stagger") {
		tv.RequestStagger = time.Duration(runenv.IntParam("request_stagger")) * time.Millisecond
	}
	if runenv.IsParamSet("run_count") {
		tv.RunCount = runenv.IntParam("run_count")
	}
	if runenv.IsParamSet("max_connection_rate") {
		tv.MaxConnectionRate = runenv.IntParam("max_connection_rate")
	}
	if runenv.IsParamSet("enable_tcp") {
		tv.TCPEnabled = runenv.BooleanParam("enable_tcp")
	}
	if runenv.IsParamSet("seeder_rate") {
		tv.SeederRate = runenv.IntParam("seeder_rate")
	}
	if runenv.IsParamSet("enable_dht") {
		tv.DHTEnabled = runenv.BooleanParam("enable_dht")
	}
	if runenv.IsParamSet("long_lasting") {
		tv.LlEnabled = runenv.BooleanParam("long_lasting")
	}
	if runenv.IsParamSet("dialer") {
		tv.Dialer = runenv.StringParam("dialer")
	}
	if runenv.IsParamSet("number_waves") {
		tv.NumWaves = runenv.IntParam("number_waves")
	}
	if runenv.IsParamSet("enable_providing") {
		tv.ProvidingEnabled = runenv.BooleanParam("enable_providing")
	}
	if runenv.IsParamSet("disk_store") {
		tv.DiskStore = runenv.BooleanParam("disk_store")
	}

	//bandwidths, err := utils.ParseIntArray(runenv.StringParam("bandwidth_mb"))
	//if err != nil {
	//	return nil, err
	//}
	//latencies, err := utils.ParseIntArray(runenv.StringParam("latency_ms"))
	//if err != nil {
	//	return nil, err
	//}
	//jitters, err := utils.ParseIntArray(runenv.StringParam("jitter_pct"))
	//if err != nil {
	//	return nil, err
	//}
	//testFiles, err := utils.GetFileList(runenv)
	//if err != nil {
	//	return nil, err
	//}
	//runenv.RecordMessage("Got file list: %v", testFiles)
	//
	//for _, f := range testFiles {
	//	for _, b := range bandwidths {
	//		for _, l := range latencies {
	//			latency := time.Duration(l) * time.Millisecond
	//			for _, j := range jitters {
	//				tv.Permutations = append(tv.Permutations, TestPermutation{File: f, Bandwidth: int(b), Latency: latency, JitterPct: int(j)})
	//			}
	//		}
	//	}
	//}

	return tv, nil
}

func makeHost(baseT *TestData) (host.Host, error) {
	// Create libp2p node
	privKey, err := crypto.UnmarshalPrivateKey(baseT.nConfig.PrivKey)
	if err != nil {
		return nil, err
	}

	return libp2p.New(libp2p.Identity(privKey), libp2p.ListenAddrs(baseT.nConfig.AddrInfo.Addrs...))
}
