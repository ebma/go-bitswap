package test

import (
	"context"
	"fmt"
	"github.com/ipfs/go-cid"
	"github.com/ipfs/testground/plans/baseline-go-bitswap/test/utils"
	"strconv"
	"strings"
	"time"

	ipld "github.com/ipfs/go-ipld-format"

	"github.com/testground/sdk-go/runtime"
	"github.com/testground/sdk-go/sync"

	"github.com/libp2p/go-libp2p/core/host"
	"github.com/libp2p/go-libp2p/core/peer"

	"github.com/testground/sdk-go/network"
)

// TestVars testing variables
type TestVars struct {
	Dialer     string
	FileSize   int
	File       utils.TestFile
	Latency    time.Duration
	LeechCount int
	RunCount   int
	RunTimeout time.Duration
	SeedCount  int
	TCPEnabled bool
	Timeout    time.Duration
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
	if runenv.IsParamSet("run_count") {
		tv.RunCount = runenv.IntParam("run_count")
	}
	if runenv.IsParamSet("enable_tcp") {
		tv.TCPEnabled = runenv.BooleanParam("enable_tcp")
	}
	if runenv.IsParamSet("dialer") {
		tv.Dialer = runenv.StringParam("dialer")
	}
	if runenv.IsParamSet("latency_ms") {
		tv.Latency = time.Duration(runenv.IntParam("latency_ms")) * time.Millisecond
	}
	if runenv.IsParamSet("file_size") {
		tv.FileSize = runenv.IntParam("file_size")
		list, err := utils.GetFileList(runenv)
		if err != nil {
			return nil, err
		}
		tv.File = list[0]
	}
	tv.LeechCount = 1
	tv.SeedCount = 1

	return tv, nil
}

func (t *TestData) publishFile(
	ctx context.Context,
	fIndex string,
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

func (t *TestData) ReadFile(ctx context.Context, fIndex string, runenv *runtime.RunEnv, testvars *TestVars) (cid.Cid, error) {
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

type NetworkTestData struct {
	*TestData
	Node utils.Node
	Host *host.Host
}

func (t *NetworkTestData) AddPublishFile(ctx context.Context, fIndex string, f utils.TestFile, runenv *runtime.RunEnv) (cid.Cid, error) {
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

func (t *NetworkTestData) CleanupRun(runenv *runtime.RunEnv) error {
	for _, c := range t.Node.Host().Network().Conns() {
		err := c.Close()
		if err != nil {
			return fmt.Errorf("Error disconnecting: %w", err)
		}
	}
	runenv.RecordMessage("Closed Connections")

	// Reset all nodes here
	runenv.RecordMessage("Closing instance")
	err := t.Node.Instance().Close()
	if err != nil {
		return err
	}
	return nil
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
	} else {
		nodeType = utils.Passive
		typeIndex = int(seq) - (leechCount + seedCount) - 1
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

func getRootCidTopic(id string) *sync.Topic {
	return sync.NewTopic(fmt.Sprintf("root-cid-%v", id), &cid.Cid{})
}

func CreateMetaFromParams(
	runNum int,
	dialer string,
	eavesCount int,
	latency time.Duration,
	seq int64,
	fileSize int,
	nodeType utils.NodeType,
	typeIndex int,
) string {
	id := fmt.Sprintf(
		"exType:baseline/permutationIndex:0/run:%d/dialer:%s/eavesCount:%d/latencyMS:%d/seq:%d/fileSize:%d/nodeType:%s/nodeTypeIndex:%d",
		runNum,
		dialer,
		eavesCount,
		latency.Milliseconds(),
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
