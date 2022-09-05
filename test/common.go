package test

import (
	"context"
	"fmt"
	"github.com/ipfs/go-bitswap"
	"github.com/ipfs/testground/plans/trickle-bitswap/utils"
	"github.com/ipfs/testground/plans/trickle-bitswap/utils/dialer"
	"math"
	"net"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/ipfs/go-cid"
	ipld "github.com/ipfs/go-ipld-format"

	"github.com/testground/sdk-go/runtime"
	"github.com/testground/sdk-go/sync"

	"github.com/libp2p/go-libp2p-core/host"
	"github.com/libp2p/go-libp2p-core/peer"

	"github.com/testground/sdk-go/network"
)

type TestPermutation struct {
	File      utils.TestFile
	Bandwidth int
	Latency   time.Duration
	JitterPct int
}

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
	Permutations      []TestPermutation
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
	if runenv.IsParamSet("seed_count") {
		tv.PassiveCount = runenv.IntParam("seed_count")
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

	bandwidths, err := utils.ParseIntArray(runenv.StringParam("bandwidth_mb"))
	if err != nil {
		return nil, err
	}
	latencies, err := utils.ParseIntArray(runenv.StringParam("latency_ms"))
	if err != nil {
		return nil, err
	}
	jitters, err := utils.ParseIntArray(runenv.StringParam("jitter_pct"))
	if err != nil {
		return nil, err
	}
	testFiles, err := utils.GetFileList(runenv)
	if err != nil {
		return nil, err
	}
	runenv.RecordMessage("Got file list: %v", testFiles)

	for _, f := range testFiles {
		for _, b := range bandwidths {
			for _, l := range latencies {
				latency := time.Duration(l) * time.Millisecond
				for _, j := range jitters {
					tv.Permutations = append(tv.Permutations, TestPermutation{File: f, Bandwidth: int(b), Latency: latency, JitterPct: int(j)})
				}
			}
		}
	}

	return tv, nil
}

func InitializeTest(ctx context.Context, runenv *runtime.RunEnv, testvars *TestVars) (*TestData, error) {
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
		runenv.RecordMessage("Signaling %v", state)
		_, err := client.SignalAndWait(ctx, sync.State(state), runenv.TestInstanceCount)
		return err
	}

	return &TestData{client, nwClient,
		nConfig, infos, dialFn, signalAndWaitForAll,
		seq, grpseq, nodetp, tpindex, seedIndex}, nil
}

func (t *TestData) publishFile(ctx context.Context, fIndex int, cid *cid.Cid, runenv *runtime.RunEnv) error {
	// Create identifier for specific file size.
	rootCidTopic := getRootCidTopic(fIndex)

	runenv.RecordMessage("Published Added CID: %v", *cid)
	// Inform other nodes of the root CID
	if _, err := t.client.Publish(ctx, rootCidTopic, *cid); err != nil {
		return fmt.Errorf("Failed to get Redis Sync rootCidTopic %w", err)
	}
	return nil
}

func (t *TestData) readFile(ctx context.Context, fIndex int, runenv *runtime.RunEnv, testvars *TestVars) (cid.Cid, error) {
	// Create identifier for specific file size.
	rootCidTopic := getRootCidTopic(fIndex)
	// Get the root CID from a seed
	rootCidCh := make(chan cid.Cid, 1)
	// Not creating a new subcontext for the subscription seems to fix a bug of closed channels
	if _, err := t.client.Subscribe(ctx, rootCidTopic, rootCidCh); err != nil {
		return cid.Undef, fmt.Errorf("Failed to subscribe to rootCidTopic %w", err)
	}
	// Note: only need to get the root CID from one seed - it should be the
	// same on all seeds (seed data is generated from repeatable random
	// sequence or existing file)
	rootCid, ok := <-rootCidCh
	if !ok {
		return cid.Undef, fmt.Errorf("no root cid in %d seconds", testvars.Timeout/time.Second)
	}
	runenv.RecordMessage("Received rootCid: %v", rootCid)
	return rootCid, nil
}

func (t *TestData) runTCPServer(ctx context.Context, fIndex int, runNum int, f utils.TestFile, runenv *runtime.RunEnv, testvars *TestVars) error {
	// TCP variables
	tcpAddrTopic := getTCPAddrTopic(fIndex, runNum)
	runenv.RecordMessage("Starting TCP server in seed")

	// Start TCP server for file
	tcpServer, err := utils.SpawnTCPServer(ctx, t.nwClient.MustGetDataNetworkIP().String(), f)
	if err != nil {
		return fmt.Errorf("Failed to start tcpServer in seed %w", err)
	}
	// Inform other nodes of the TCPServerAddr
	runenv.RecordMessage("Publishing TCP address %v", tcpServer.Addr)
	if _, err = t.client.Publish(ctx, tcpAddrTopic, tcpServer.Addr); err != nil {
		return fmt.Errorf("Failed to get Redis Sync tcpAddr %w", err)
	}
	runenv.RecordMessage("Waiting to end finish TCP fetch")

	// Wait for all nodes to be done with TCP Fetch
	err = t.signalAndWaitForAll(fmt.Sprintf("tcp-fetch-%d-%d", fIndex, runNum))
	if err != nil {
		return err
	}

	// At this point TCP interactions are finished.
	runenv.RecordMessage("Closing TCP server")
	tcpServer.Close()
	return nil
}

func (t *TestData) runTCPFetch(ctx context.Context, fIndex int, runNum int, runenv *runtime.RunEnv, testvars *TestVars) (int64, error) {
	// TCP variables
	tcpAddrTopic := getTCPAddrTopic(fIndex, runNum)
	tcpAddrCh := make(chan *string, 1)
	if _, err := t.client.Subscribe(ctx, tcpAddrTopic, tcpAddrCh); err != nil {
		return 0, fmt.Errorf("Failed to subscribe to tcpServerTopic %w", err)
	}
	tcpAddrPtr, ok := <-tcpAddrCh

	runenv.RecordMessage("Received tcp server %v", tcpAddrPtr)
	if !ok {
		return 0, fmt.Errorf("no tcp server addr received in %d seconds", testvars.Timeout/time.Second)
	}
	runenv.RecordMessage("Start fetching a TCP file from seed")
	// open a connection
	connection, err := net.Dial("tcp", *tcpAddrPtr)
	if err != nil {
		runenv.RecordFailure(err)
		return 0, err
	}
	defer connection.Close()

	start := time.Now()
	utils.FetchFileTCP(connection, runenv)
	tcpFetch := time.Since(start).Nanoseconds()
	runenv.RecordMessage("Fetched TCP file after %d (ns)", tcpFetch)

	// Wait for all nodes to be done with TCP Fetch
	return tcpFetch, t.signalAndWaitForAll(fmt.Sprintf("tcp-fetch-%d-%d", fIndex, runNum))
}

type NodeTestData struct {
	*TestData
	node utils.Node
	host *host.Host
}

func (t *NodeTestData) stillAlive(runenv *runtime.RunEnv, v *TestVars) {
	// starting liveness process for long-lasting experiments.
	if v.LlEnabled {
		go func(n utils.Node, runenv *runtime.RunEnv) {
			for {
				n.EmitKeepAlive(runenv)
				time.Sleep(15 * time.Second)
			}
		}(t.node, runenv)
	}
}

func (t *NodeTestData) addPublishFile(ctx context.Context, fIndex int, f utils.TestFile, runenv *runtime.RunEnv, testvars *TestVars) (cid.Cid, error) {
	rate := float64(testvars.SeederRate) / 100
	seeders := runenv.TestInstanceCount - (testvars.LeechCount + testvars.PassiveCount)
	toSeed := int(math.Ceil(float64(seeders) * rate))

	// If this is the first run for this file size.
	// Only a rate of seeders add the file.
	if t.tpindex <= toSeed {
		// Generating and adding file to IPFS
		c, err := generateAndAdd(ctx, runenv, t.node, f)
		if err != nil {
			return cid.Undef, err
		}
		err = fractionalDAG(ctx, runenv, int(t.seedIndex), *c, t.node.DAGService())
		if err != nil {
			return cid.Undef, err
		}
		return *c, t.publishFile(ctx, fIndex, c, runenv)
	}
	return cid.Undef, nil
}
func (t *NodeTestData) cleanupRun(ctx context.Context, rootCid cid.Cid, runenv *runtime.RunEnv) error {
	// Disconnect peers
	for _, c := range t.node.Host().Network().Conns() {
		err := c.Close()
		if err != nil {
			return fmt.Errorf("Error disconnecting: %w", err)
		}
	}
	runenv.RecordMessage("Closed Connections")

	if t.nodetp == utils.Leech || t.nodetp == utils.Passive {
		// Clearing datastore
		// Also clean passive nodes so they don't store blocks from
		// previous runs.
		if err := t.node.ClearDatastore(ctx, rootCid); err != nil {
			return fmt.Errorf("Error clearing datastore: %w", err)
		}
	}
	return nil
}

func (t *NodeTestData) cleanupFile(ctx context.Context, rootCid cid.Cid) error {
	if t.nodetp == utils.Seed {
		// Between every file close the seed Node.
		// ipfsNode.Close()
		// runenv.RecordMessage("Closed Seed Node")
		if err := t.node.ClearDatastore(ctx, rootCid); err != nil {
			return fmt.Errorf("Error clearing datastore: %w", err)
		}
	}
	return nil
}

func (t *NodeTestData) close() error {
	if t.host == nil {
		return nil
	}
	return (*t.host).Close()
}

func (t *NodeTestData) emitMetrics(runenv *runtime.RunEnv, runNum int, transport string,
	permutation TestPermutation, timeToFetch time.Duration, tcpFetch int64, leechFails int64,
	maxConnectionRate int, pIndex int) error {

	recorder := newMetricsRecorder(runenv, runNum, t.seq, t.grpseq, transport, permutation.Latency, permutation.Bandwidth, int(permutation.File.Size()), t.nodetp, t.tpindex, maxConnectionRate, pIndex)
	if t.nodetp == utils.Leech {
		recorder.Record("time_to_fetch", float64(timeToFetch))
		recorder.Record("leech_fails", float64(leechFails))
		recorder.Record("tcp_fetch", float64(tcpFetch))
	}

	return t.node.EmitMetrics(recorder)
}

func (t *NodeTestData) emitMessageHistory(runenv *runtime.RunEnv, runNum int, transport string,
	permutation TestPermutation, maxConnectionRate int, pIndex int, host string) error {
	recorder := newMessageHistoryRecorder(runenv, runNum, t.seq, t.grpseq, transport, permutation.Latency, permutation.Bandwidth, int(permutation.File.Size()), t.nodetp, t.tpindex, maxConnectionRate, pIndex, host)

	return t.node.EmitMessageHistory(recorder)
}

func generateAndAdd(ctx context.Context, runenv *runtime.RunEnv, node utils.Node, f utils.TestFile) (*cid.Cid, error) {
	// Generate the file
	inputData := runenv.StringParam("input_data")
	runenv.RecordMessage("Starting to generate file for inputData: %s and file %v", inputData, f)
	tmpFile, err := f.GenerateFile()
	if err != nil {
		return nil, err
	}

	// Add file to the IPFS network
	start := time.Now()
	cid, err := node.Add(ctx, tmpFile)
	end := time.Since(start).Milliseconds()
	if err != nil {
		runenv.RecordMessage("Error adding file to node: %w", err)
	}
	runenv.RecordMessage("Added to node %v in %d (ms)", cid, end)
	return &cid, err
}

func parseType(ctx context.Context, runenv *runtime.RunEnv, client *sync.DefaultClient, addrInfo *peer.AddrInfo, seq int64) (int64, utils.NodeType, int, error) {
	leechCount := runenv.IntParam("leech_count")
	seedCount := runenv.IntParam("seed_count")
	eavesdropperCount := runenv.IntParam("eavesdropper_count")

	grpCountOverride := false
	if runenv.TestGroupID != "" {
		grpLchLabel := runenv.TestGroupID + "_leech_count"
		if runenv.IsParamSet(grpLchLabel) {
			leechCount = runenv.IntParam(grpLchLabel)
			grpCountOverride = true
		}
		grpSeedLabel := runenv.TestGroupID + "_seed_count"
		if runenv.IsParamSet(grpSeedLabel) {
			seedCount = runenv.IntParam(grpSeedLabel)
			grpCountOverride = true
		}
		grpEavsLabel := runenv.TestGroupID + "_eavesdropper_count"
		if runenv.IsParamSet(grpEavsLabel) {
			eavesdropperCount = runenv.IntParam(grpSeedLabel)
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
	case grpseq > int64(leechCount) && grpseq <= int64(leechCount+eavesdropperCount):
		nodetp = utils.Eavesdropper
		tpindex = int(grpseq) - 1 - (leechCount + eavesdropperCount)
	case grpseq > int64(leechCount+seedCount+eavesdropperCount):
		nodetp = utils.Passive
		tpindex = int(grpseq) - 1 - (leechCount + seedCount + eavesdropperCount)
	default:
		nodetp = utils.Seed
		tpindex = int(grpseq) - 1 - leechCount
	}

	runenv.RecordMessage("I am %s %d %s", grpPrefix+nodetp.String(), tpindex, seqstr)

	return grpseq, nodetp, tpindex, nil
}

func getNodeSetSeq(ctx context.Context, client *sync.DefaultClient, addrInfo *peer.AddrInfo, setID string) (int64, error) {
	topic := sync.NewTopic("nodes"+setID, &peer.AddrInfo{})

	return client.Publish(ctx, topic, addrInfo)
}

func fractionalDAG(ctx context.Context, runenv *runtime.RunEnv, seedIndex int, c cid.Cid, dserv ipld.DAGService) error {
	//TODO: Explore this seed_fraction parameter.
	if !runenv.IsParamSet("seed_fraction") {
		return nil
	}
	seedFrac := runenv.StringParam("seed_fraction")
	if seedFrac == "" {
		return nil
	}

	parts := strings.Split(seedFrac, "/")
	if len(parts) != 2 {
		return fmt.Errorf("Invalid seed fraction %s", seedFrac)
	}
	numerator, nerr := strconv.ParseInt(parts[0], 10, 64)
	denominator, derr := strconv.ParseInt(parts[1], 10, 64)
	if nerr != nil || derr != nil {
		return fmt.Errorf("Invalid seed fraction %s", seedFrac)
	}

	ipldNode, err := dserv.Get(ctx, c)
	if err != nil {
		return err
	}

	nodes, err := getLeafNodes(ctx, ipldNode, dserv)
	if err != nil {
		return err
	}
	var del []cid.Cid
	for i := 0; i < len(nodes); i++ {
		idx := i + seedIndex
		if idx%int(denominator) >= int(numerator) {
			del = append(del, nodes[i].Cid())
		}
	}
	if err := dserv.RemoveMany(ctx, del); err != nil {
		return err
	}

	runenv.RecordMessage("Retained %d / %d of blocks from seed, removed %d / %d blocks", numerator, denominator, len(del), len(nodes))
	return nil
}

func getLeafNodes(ctx context.Context, node ipld.Node, dserv ipld.DAGService) ([]ipld.Node, error) {
	if len(node.Links()) == 0 {
		return []ipld.Node{node}, nil
	}

	var leaves []ipld.Node
	for _, l := range node.Links() {
		child, err := l.GetNode(ctx, dserv)
		if err != nil {
			return nil, err
		}
		childLeaves, err := getLeafNodes(ctx, child, dserv)
		if err != nil {
			return nil, err
		}
		leaves = append(leaves, childLeaves...)
	}

	return leaves, nil
}

func getRootCidTopic(id int) *sync.Topic {
	return sync.NewTopic(fmt.Sprintf("root-cid-%d", id), &cid.Cid{})
}

func getTCPAddrTopic(id int, run int) *sync.Topic {
	return sync.NewTopic(fmt.Sprintf("tcp-addr-%d-%d", id, run), "")
}

func createRecorderIDFromParams(runenv *runtime.RunEnv, runNum int, seq int64, grpseq int64,
	transport string, latency time.Duration, bandwidthMB int, fileSize int, nodetp utils.NodeType, tpindex int,
	maxConnectionRate int, pIndex int) string {

	latencyMS := latency.Milliseconds()
	instance := runenv.TestInstanceCount
	leechCount := runenv.IntParam("leech_count")
	passiveCount := runenv.IntParam("seed_count")
	eavesdropperCount := runenv.IntParam("eavesdropper_count")

	id := fmt.Sprintf("topology:(%d-%d-%d-%d)/transport:%s/maxConnectionRate:%d/latencyMS:%d/bandwidthMB:%d/run:%d/seq:%d/groupName:%s/groupSeq:%d/fileSize:%d/nodeType:%s/nodeTypeIndex:%d/permutationIndex:%d",
		instance-leechCount-passiveCount-eavesdropperCount, leechCount, passiveCount, eavesdropperCount, transport, maxConnectionRate,
		latencyMS, bandwidthMB, runNum, seq, runenv.TestGroupID, grpseq, fileSize, nodetp, tpindex, pIndex)
	return id
}

type metricsRecorder struct {
	runenv *runtime.RunEnv
	id     string
}

func newMetricsRecorder(runenv *runtime.RunEnv, runNum int, seq int64, grpseq int64,
	transport string, latency time.Duration, bandwidthMB int, fileSize int, nodetp utils.NodeType, tpindex int,
	maxConnectionRate int, pIndex int) utils.MetricsRecorder {

	id := createRecorderIDFromParams(runenv, runNum, seq, grpseq, transport, latency, bandwidthMB, fileSize, nodetp, tpindex, maxConnectionRate, pIndex)

	return &metricsRecorder{runenv, id}
}

func (mr *metricsRecorder) Record(key string, value float64) {
	mr.runenv.R().RecordPoint(fmt.Sprintf("%s/name:%s", mr.id, key), value)
}

type messageHistoryRecorder struct {
	runenv *runtime.RunEnv
	file   *os.File
	id     string
	host   string
}

func (m messageHistoryRecorder) RecordMessageHistoryEntry(msg bitswap.MessageHistoryEntry) {
	// don't log non-want-have messages
	if len(msg.Message.Wantlist()) == 0 {
		return
	}
	wantlistString := ""
	for index, entry := range msg.Message.Wantlist() {
		if index > 0 {
			wantlistString = wantlistString + fmt.Sprintf(", \"%s\"", entry.Cid)
		} else {
			wantlistString = wantlistString + fmt.Sprintf("\"%s\"", entry.Cid)
		}

	}
	msgObjectString := fmt.Sprintf("\"wants\": [%s]", wantlistString)
	logString := fmt.Sprintf("{ \"name\": \"%s\", \"receiver\": \"%s\", \"ts\": \"%d\", \"sender\": \"%s\", \"message\": { %s } }", m.id, m.host, msg.Timestamp.UnixNano(), msg.Peer, msgObjectString)
	_, err := fmt.Fprintln(m.file, logString)
	if err != nil {
		m.runenv.RecordMessage("Error writing message history entry: %s", err)
		return
	}
}

func newMessageHistoryRecorder(runenv *runtime.RunEnv, runNum int, seq int64, grpseq int64,
	transport string, latency time.Duration, bandwidthMB int, fileSize int, nodetp utils.NodeType, tpindex int,
	maxConnectionRate int, pIndex int, host string) utils.MessageHistoryRecorder {

	id := createRecorderIDFromParams(runenv, runNum, seq, grpseq, transport, latency, bandwidthMB, fileSize, nodetp, tpindex, maxConnectionRate, pIndex)

	file, err := os.OpenFile(runenv.TestOutputsPath+"/messageHistory.out", os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0755)
	if err != nil {
		runenv.RecordMessage("Error creating message history file: %s", err)
		return nil
	}
	return &messageHistoryRecorder{runenv, file, id, host}

}

type globalInfoRecorder struct {
	runenv *runtime.RunEnv
	file   *os.File
	id     string
}

func (g globalInfoRecorder) RecordGlobalInfo(infoType string, info string) {
	msgString := fmt.Sprintf("{ \"id\": \"%s\", \"timestamp\": \"%d\", \"type\": \"%s\", \"info\": { %s } }", g.id, time.Now().UnixMicro(), infoType, info)
	_, err := fmt.Fprintln(g.file, msgString)
	if err != nil {
		g.runenv.RecordMessage("Error writing global info: %s", err)
		return
	}
}

func newGlobalInfoRecorder(runenv *runtime.RunEnv, seq int64) utils.GlobalInfoRecorder {
	file, err := os.OpenFile(runenv.TestOutputsPath+"/globalInfo.out", os.O_WRONLY|os.O_CREATE|os.O_APPEND, 0755)
	if err != nil {
		runenv.RecordMessage("Error creating global info file: %s", err)
		return nil
	}
	id := fmt.Sprintf("%d", seq)
	return &globalInfoRecorder{runenv, file, id}
}
