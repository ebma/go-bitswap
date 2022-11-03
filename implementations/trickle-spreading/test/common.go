package test

import (
	"context"
	"fmt"
	bsmsg "github.com/ipfs/go-bitswap/message"
	"github.com/ipfs/testground/plans/trickle-bitswap/test/utils"
	"net"
	"os"
	"strconv"
	"strings"
	"time"

	"github.com/ipfs/go-cid"
	ipld "github.com/ipfs/go-ipld-format"

	"github.com/testground/sdk-go/runtime"
	"github.com/testground/sdk-go/sync"

	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/peer"

	"github.com/testground/sdk-go/network"
)

type TestPermutation struct {
	File           utils.TestFile
	TricklingDelay time.Duration
}

// TestVars testing variables
type TestVars struct {
	Dialer            string
	EavesdropperCount int
	Latency           time.Duration
	LeechCount        int
	Permutations      []TestPermutation
	RunCount          int
	RunTimeout        time.Duration
	SeedCount         int
	TCPEnabled        bool
	Timeout           time.Duration
}

type BaseTestData struct {
	Client   *sync.DefaultClient
	NwClient *network.Client
	NConfig  *utils.NodeConfig
	Seq      int64
}

type TestData struct {
	*BaseTestData
	PeerInfos           []utils.PeerInfo
	SignalAndWaitForAll func(state string) error
	Seq                 int64
	NodeType            utils.NodeType
	TypeIndex           int
	SeedIndex           int64
}

func GetEnvVars(runenv *runtime.RunEnv) (*TestVars, error) {
	tv := &TestVars{}
	if runenv.IsParamSet("timeout_secs") {
		tv.Timeout = time.Duration(runenv.IntParam("timeout_secs")) * time.Second
	}
	if runenv.IsParamSet("run_timeout_secs") {
		tv.RunTimeout = time.Duration(runenv.IntParam("run_timeout_secs")) * time.Second
	}
	if runenv.IsParamSet("eavesdropper_count") {
		tv.EavesdropperCount = runenv.IntParam("eavesdropper_count")
	}
	if runenv.IsParamSet("enable_tcp") {
		tv.TCPEnabled = runenv.BooleanParam("enable_tcp")
	}
	if runenv.IsParamSet("dialer") {
		tv.Dialer = runenv.StringParam("dialer")
	}
	if runenv.IsParamSet("run_count") {
		tv.RunCount = runenv.IntParam("run_count")
	}
	if runenv.IsParamSet("latency_ms") {
		tv.Latency = time.Duration(runenv.IntParam("latency_ms")) * time.Millisecond
	}

	tv.LeechCount = 1
	tv.SeedCount = 1

	tricklingDelays, err := utils.ParseIntArray(runenv.StringParam("trickling_delay_ms"))
	if err != nil {
		return nil, err
	}
	testFiles, err := utils.GetFileList(runenv)
	if err != nil {
		return nil, err
	}
	runenv.RecordMessage("Got file list: %v", testFiles)

	for _, f := range testFiles {
		for _, td := range tricklingDelays {
			tv.Permutations = append(
				tv.Permutations,
				TestPermutation{
					File:           f,
					TricklingDelay: time.Duration(td) * time.Millisecond,
				},
			)
		}
	}

	return tv, nil
}

func (t *TestData) publishFile(
	ctx context.Context,
	fIndex int,
	cid *cid.Cid,
	runenv *runtime.RunEnv,
) error {
	// Create identifier for specific file size.
	rootCidTopic := getRootCidTopic(fIndex)

	runenv.RecordMessage("Published Added CID: %v", *cid)
	// Inform other nodes of the root CID
	if _, err := t.Client.Publish(ctx, rootCidTopic, *cid); err != nil {
		return fmt.Errorf("Failed to get Redis Sync rootCidTopic %w", err)
	}
	return nil
}

func (t *TestData) ReadFile(
	ctx context.Context,
	fIndex int,
	runenv *runtime.RunEnv,
	testvars *TestVars,
) (cid.Cid, error) {
	// Create identifier for specific file size.
	rootCidTopic := getRootCidTopic(fIndex)
	// Get the root CID from a seed
	rootCidCh := make(chan cid.Cid, 1)
	// Not creating a new subcontext for the subscription seems to fix a bug of closed channels
	if _, err := t.Client.Subscribe(ctx, rootCidTopic, rootCidCh); err != nil {
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

func (t *TestData) RunTCPServer(
	ctx context.Context,
	fIndex int,
	runNum int,
	f utils.TestFile,
	runenv *runtime.RunEnv,
	testvars *TestVars,
) error {
	// TCP variables
	tcpAddrTopic := getTCPAddrTopic(fIndex, runNum)
	runenv.RecordMessage("Starting TCP server in seed")

	// Start TCP server for file
	tcpServer, err := utils.SpawnTCPServer(ctx, t.NwClient.MustGetDataNetworkIP().String(), f)
	if err != nil {
		return fmt.Errorf("Failed to start tcpServer in seed %w", err)
	}
	// Inform other nodes of the TCPServerAddr
	runenv.RecordMessage("Publishing TCP address %v", tcpServer.Addr)
	if _, err = t.Client.Publish(ctx, tcpAddrTopic, tcpServer.Addr); err != nil {
		return fmt.Errorf("Failed to get Redis Sync tcpAddr %w", err)
	}
	runenv.RecordMessage("Waiting to end finish TCP fetch")

	// Wait for all nodes to be done with TCP Fetch
	err = t.SignalAndWaitForAll(fmt.Sprintf("tcp-fetch-%d-%d", fIndex, runNum))
	if err != nil {
		return err
	}

	// At this point TCP interactions are finished.
	runenv.RecordMessage("Closing TCP server")
	tcpServer.Close()
	return nil
}

func (t *TestData) RunTCPFetch(
	ctx context.Context,
	fIndex int,
	runNum int,
	runenv *runtime.RunEnv,
	testvars *TestVars,
) (int64, error) {
	// TCP variables
	tcpAddrTopic := getTCPAddrTopic(fIndex, runNum)
	tcpAddrCh := make(chan *string, 1)
	if _, err := t.Client.Subscribe(ctx, tcpAddrTopic, tcpAddrCh); err != nil {
		return 0, fmt.Errorf("Failed to subscribe to tcpServerTopic %w", err)
	}
	tcpAddrPtr, ok := <-tcpAddrCh

	runenv.RecordMessage("Received tcp server %v", tcpAddrPtr)
	if !ok {
		return 0, fmt.Errorf(
			"no tcp server addr received in %d seconds",
			testvars.Timeout/time.Second,
		)
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
	return tcpFetch, t.SignalAndWaitForAll(fmt.Sprintf("tcp-fetch-%d-%d", fIndex, runNum))
}

type NetworkTestData struct {
	*TestData
	Node utils.Node
	Host *host.Host
}

func (t *NetworkTestData) AddPublishFile(
	ctx context.Context,
	fIndex int,
	f utils.TestFile,
	runenv *runtime.RunEnv,
) (cid.Cid, error) {
	// If this is the first run for this file size.
	// Only a rate of seeders add the file.
	// Generating and adding file to IPFS
	c, err := generateAndAdd(ctx, runenv, t.Node, f)
	if err != nil {
		return cid.Undef, err
	}
	err = fractionalDAG(ctx, runenv, int(t.SeedIndex), *c, t.Node.DAGService())
	if err != nil {
		return cid.Undef, err
	}
	return *c, t.publishFile(ctx, fIndex, c, runenv)
}

func (t *NetworkTestData) CleanupRun(
	ctx context.Context,
	rootCid cid.Cid,
	runenv *runtime.RunEnv,
) error {
	// Disconnect peers
	for _, c := range t.Node.Host().Network().Conns() {
		err := c.Close()
		if err != nil {
			return fmt.Errorf("Error disconnecting: %w", err)
		}
	}
	runenv.RecordMessage("Closed Connections")

	if t.NodeType == utils.Leech || t.NodeType == utils.Passive ||
		t.NodeType == utils.Eavesdropper {
		// Clearing datastore
		// Also clean passive nodes so they don't store blocks from
		// previous runs.
		if err := t.Node.ClearDatastore(ctx, rootCid); err != nil {
			return fmt.Errorf("Error clearing datastore: %w", err)
		}
	}
	return nil
}

func (t *NetworkTestData) CleanupFile(ctx context.Context, rootCid cid.Cid) error {
	if t.NodeType == utils.Seed {
		// Between every file close the seed Node.
		// ipfsNode.Close()
		// runenv.RecordMessage("Closed Seed Node")
		if err := t.Node.ClearDatastore(ctx, rootCid); err != nil {
			return fmt.Errorf("Error clearing datastore: %w", err)
		}
	}
	return nil
}

func (t *NetworkTestData) close() error {
	if t.Host == nil {
		return nil
	}
	return (*t.Host).Close()
}

func (t *NetworkTestData) EmitMetrics(runenv *runtime.RunEnv, meta string,
	timeToFetch time.Duration, tcpFetch int64, leechFails int64) error {

	recorder := newMetricsRecorder(runenv, meta)
	if t.NodeType == utils.Leech {
		recorder.Record("time_to_fetch", float64(timeToFetch))
		recorder.Record("leech_fails", float64(leechFails))
		recorder.Record("tcp_fetch", float64(tcpFetch))
	}

	return t.Node.EmitMetrics(recorder)
}

func generateAndAdd(
	ctx context.Context,
	runenv *runtime.RunEnv,
	node utils.Node,
	f utils.TestFile,
) (*cid.Cid, error) {
	// Generate the file
	runenv.RecordMessage("Starting to generate file for %v", f)
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

func ParseType(
	runenv *runtime.RunEnv,
	seq int64,
	leechCount int,
	seedCount int,
	eavesdropperCount int,
) (int64, utils.NodeType, int, error) {
	var nodeType utils.NodeType
	var typeIndex int
	seqstr := fmt.Sprintf("- Seq %d / %d", seq, runenv.TestInstanceCount)

	// Note: Seq starts at 1 (not 0)
	if seq <= int64(leechCount) {
		nodeType = utils.Leech
		typeIndex = int(seq) - 1
	} else if seq <= int64(leechCount+seedCount) {
		nodeType = utils.Seed
		typeIndex = int(seq) - leechCount - 1
	} else if seq <= int64(leechCount+seedCount+eavesdropperCount) {
		nodeType = utils.Eavesdropper
		typeIndex = int(seq) - (leechCount + seedCount) - 1
	} else {
		nodeType = utils.Passive
		typeIndex = int(seq) - (leechCount + seedCount + eavesdropperCount) - 1
	}

	runenv.RecordMessage("I am %s %d %s", nodeType.String(), typeIndex, seqstr)

	return seq, nodeType, typeIndex, nil
}

func getNodeSetSeq(
	ctx context.Context,
	client *sync.DefaultClient,
	addrInfo *peer.AddrInfo,
	setID string,
) (int64, error) {
	topic := sync.NewTopic("nodes"+setID, &peer.AddrInfo{})

	return client.Publish(ctx, topic, addrInfo)
}

func fractionalDAG(
	ctx context.Context,
	runenv *runtime.RunEnv,
	seedIndex int,
	c cid.Cid,
	dserv ipld.DAGService,
) error {
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

	runenv.RecordMessage(
		"Retained %d / %d of blocks from seed, removed %d / %d blocks",
		numerator,
		denominator,
		len(del),
		len(nodes),
	)
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

func CreateTopologyString(
	totalInstances,
	leechCount int,
	seedCount int,
	eavesdropperCount int,
) string {
	// (seeder-count:leech-count:passive-count:eavesdropper-count)
	return fmt.Sprintf(
		"(%d-%d-%d-%d)",
		totalInstances-leechCount-seedCount-eavesdropperCount,
		leechCount,
		seedCount,
		eavesdropperCount,
	)
}

func CreateMetaFromParams(
	pIndex int,
	runNum int,
	dialer string,
	eavesCount int,
	latency time.Duration,
	tricklingDelay time.Duration,
	seq int64,
	fileSize int,
	nodeType utils.NodeType,
	typeIndex int,
) string {
	id := fmt.Sprintf(
		"exType:trickle/permutationIndex:%d/run:%d/dialer:%s/eavesCount:%d/latencyMS:%d/tricklingDelay:%d/seq:%d/fileSize:%d/nodeType:%s/nodeTypeIndex:%d",
		pIndex,
		runNum,
		dialer,
		eavesCount,
		latency.Milliseconds(),
		tricklingDelay.Milliseconds(),
		seq,
		fileSize,
		nodeType,
		typeIndex,
	)
	return id
}

type metricsRecorder struct {
	runenv *runtime.RunEnv
	meta   string
}

func newMetricsRecorder(runenv *runtime.RunEnv, meta string) utils.MetricsRecorder {
	return &metricsRecorder{runenv, meta}
}

func (mr *metricsRecorder) Record(key string, value float64) {
	mr.runenv.R().RecordPoint(fmt.Sprintf("%s/meta:%s", mr.meta, key), value)
}

type MessageHistoryRecorder struct {
	runenv    *runtime.RunEnv
	file      *os.File
	meta      string
	host      string
	shouldLog bool
}

func (m MessageHistoryRecorder) MessageReceived(pid peer.ID, msg bsmsg.BitSwapMessage) {
	if !m.shouldLog {
		// this somehow doesnt work
		return
	}
	timestamp := time.Now().UnixNano()
	// don't log non-want-have messages
	if len(msg.Wantlist()) == 0 {
		return
	}
	wantlistString := ""
	for index, entry := range msg.Wantlist() {
		if index > 0 {
			wantlistString = wantlistString + fmt.Sprintf(", \"%s\"", entry.Cid)
		} else {
			wantlistString = wantlistString + fmt.Sprintf("\"%s\"", entry.Cid)
		}
	}

	msgObjectString := fmt.Sprintf("\"wants\": [%s]", wantlistString)
	logString := fmt.Sprintf(
		"{ \"meta\": \"%s\", \"receiver\": \"%s\", \"ts\": \"%d\", \"sender\": \"%s\", \"message\": { %s } }",
		m.meta,
		m.host,
		timestamp,
		pid.String(),
		msgObjectString,
	)
	_, err := fmt.Fprintln(m.file, logString)
	if err != nil {
		m.runenv.RecordMessage("Error writing message history entry: %s", err)
		return
	}

	// Make sure to log only once
	m.shouldLog = false
}
func (m MessageHistoryRecorder) MessageSent(pid peer.ID, msg bsmsg.BitSwapMessage) {

}

func NewMessageHistoryRecorder(
	runenv *runtime.RunEnv,
	meta string,
	host string,
) *MessageHistoryRecorder {
	file, err := os.OpenFile(
		runenv.TestOutputsPath+"/messageHistory.out",
		os.O_WRONLY|os.O_CREATE|os.O_APPEND,
		0755,
	)
	if err != nil {
		runenv.RecordMessage("Error creating message history file: %s", err)
		return nil
	}
	return &MessageHistoryRecorder{runenv, file, meta, host, true}

}

type globalInfoRecorder struct {
	runenv *runtime.RunEnv
	file   *os.File
}

func (g globalInfoRecorder) RecordInfoWithMeta(meta string, info string) {
	infoType := "LeechInfo"
	msgString := fmt.Sprintf(
		"{ \"meta\": \"%s\", \"timestamp\": \"%d\", \"type\": \"%s\", %s }",
		meta,
		time.Now().UnixMicro(),
		infoType,
		info,
	)
	_, err := fmt.Fprintln(g.file, msgString)
	if err != nil {
		g.runenv.RecordMessage("Error writing global info: %s", err)
		return
	}
}

func (g globalInfoRecorder) RecordNodeInfo(info string) {
	infoType := "NodeInfo"
	msgString := fmt.Sprintf(
		"{ \"timestamp\": \"%d\", \"type\": \"%s\", %s }",
		time.Now().UnixMicro(),
		infoType,
		info,
	)
	_, err := fmt.Fprintln(g.file, msgString)
	if err != nil {
		g.runenv.RecordMessage("Error writing global info: %s", err)
		return
	}
}

func NewGlobalInfoRecorder(runenv *runtime.RunEnv) utils.GlobalInfoRecorder {
	file, err := os.OpenFile(
		runenv.TestOutputsPath+"/globalInfo.out",
		os.O_WRONLY|os.O_CREATE|os.O_APPEND,
		0755,
	)
	if err != nil {
		runenv.RecordMessage("Error creating global info file: %s", err)
		return nil
	}
	return &globalInfoRecorder{runenv, file}
}
