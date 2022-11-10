package utils

import (
	"context"
	"encoding/base64"
	"fmt"
	bs "github.com/ipfs/go-bitswap"
	"github.com/ipfs/go-cid"
	"github.com/ipfs/go-datastore"
	dsync "github.com/ipfs/go-datastore/sync"
	files "github.com/ipfs/go-ipfs-files"
	ipld "github.com/ipfs/go-ipld-format"
	icore "github.com/ipfs/interface-go-ipfs-core"
	"github.com/ipfs/interface-go-ipfs-core/path"
	"github.com/ipfs/kubo/config"
	"github.com/ipfs/kubo/core"
	"github.com/ipfs/kubo/core/coreapi"
	"github.com/ipfs/kubo/core/node/libp2p"
	"github.com/ipfs/kubo/repo"
	"github.com/libp2p/go-libp2p/core/host"
	"github.com/testground/sdk-go/runtime"
	"golang.org/x/sync/errgroup"
)

// IPFSNode represents the node
type IPFSNode struct {
	Node   *core.IpfsNode
	API    icore.CoreAPI
	runenv *runtime.RunEnv
}

type NodeType int

const (
	// Seeds data
	Seed NodeType = iota
	// Fetches data from seeds
	Leech
	// Doesn't seed or fetch data
	Passive
)

func (nt NodeType) String() string {
	return [...]string{"Seed", "Leech", "Passive"}[nt]
}

func (n *IPFSNode) Instance() *IPFSNode {
	return n
}

// CreateIPFSNodeWithConfig constructs and returns an IpfsNode using the given cfg.
func CreateIPFSNodeWithConfig(ctx context.Context, nConfig *NodeConfig, runenv *runtime.RunEnv) (*IPFSNode, error) {
	// Create new Datastore
	d := datastore.NewMapDatastore()
	// Initialize config.
	cfg := &config.Config{}

	// Use defaultBootstrap
	cfg.Bootstrap = config.DefaultBootstrapAddresses

	//Allow the node to start in any available port. We do not use default ones.
	cfg.Addresses.Swarm = nConfig.Addrs

	cfg.Identity.PeerID = nConfig.AddrInfo.ID.String()
	cfg.Identity.PrivKey = base64.StdEncoding.EncodeToString(nConfig.PrivKey)

	cfg.Experimental.FilestoreEnabled = false
	cfg.Experimental.AcceleratedDHTClient = false
	cfg.Experimental.GraphsyncEnabled = false
	cfg.Experimental.StrategicProviding = false
	cfg.Experimental.UrlstoreEnabled = false

	// Repo structure that encapsulate the config and datastore for dependency injection.
	buildRepo := &repo.Mock{
		D: dsync.MutexWrap(d),
		C: *cfg,
	}

	bcfg := &core.BuildCfg{
		Host:    libp2p.DefaultHostOption,
		Online:  true,
		Routing: libp2p.DHTOption,
		Repo:    buildRepo,
		//NilRepo: true,
	}
	n, err := core.NewNode(ctx, bcfg)
	if err != nil {
		return nil, err
	}
	api, err := coreapi.NewCoreAPI(n)
	if err != nil {
		return nil, fmt.Errorf("Failed starting API: %s", err)

	}

	// Attach the Core API to the constructed node
	return &IPFSNode{n, api, runenv}, nil
}

// ClearDatastore removes a block from the datastore.
func (n *IPFSNode) ClearDatastore(ctx context.Context, rootCid cid.Cid) error {
	err := n.Node.DAG.Remove(ctx, rootCid)
	if err != nil {
		return err
	}

	//(*n.Node).Blocks.
	//return nil

	_, pinned, err := n.API.Pin().IsPinned(ctx, path.IpfsPath(rootCid))
	if err != nil {
		return err
	}
	if pinned {
		n.runenv.RecordMessage("Pinned, removing pin")
		err := n.API.Pin().Rm(ctx, path.IpfsPath(rootCid))
		if err != nil {
			return err
		}
	}
	ks, err := n.Node.Blockstore.AllKeysChan(ctx)
	if err != nil {
		return err
	}
	n.runenv.RecordMessage("Removing blocks")
	g := errgroup.Group{}
	for k := range ks {
		c := k
		n.runenv.RecordMessage("Removing block %s", c.String())
		g.Go(func() error {
			err := n.API.Block().Rm(ctx, path.IpfsPath(c))
			if err != nil {
				return err
			}
			return n.Node.Blockstore.DeleteBlock(ctx, c)
		})
	}
	return g.Wait()

	// this probably fails but try to find out with log statements
	//var ng ipld.NodeGetter = merkledag.NewSession(ctx, n.Node.DAG)
	//toDelete := cid.NewSet()
	//err = merkledag.Walk(ctx, merkledag.GetLinksDirect(n.Node.DAG), rootCid, toDelete.Visit, merkledag.Concurrent())
	//if err != nil {
	//	return err
	//}
	//return toDelete.ForEach(func(c cid.Cid) error {
	//	return n.API.Block().Rm(ctx, path.IpfsPath(c))
	//})
}

// EmitMetrics emits node's metrics for the run
func (n *IPFSNode) EmitMetrics(recorder MetricsRecorder) error {
	bsnode := n.Node.Exchange.(*bs.Bitswap)
	stats, err := bsnode.Stat()

	if err != nil {
		return fmt.Errorf("Error getting stats from Bitswap: %w", err)
	}

	recorder.Record("msgs_rcvd", float64(stats.MessagesReceived))
	recorder.Record("data_sent", float64(stats.DataSent))
	recorder.Record("data_rcvd", float64(stats.DataReceived))
	recorder.Record("dup_data_rcvd", float64(stats.DupDataReceived))
	recorder.Record("blks_sent", float64(stats.BlocksSent))
	recorder.Record("blks_rcvd", float64(stats.BlocksReceived))
	recorder.Record("dup_blks_rcvd", float64(stats.DupBlksReceived))

	return nil
}

func (n *IPFSNode) Add(ctx context.Context, tmpFile files.Node) (cid.Cid, error) {
	path, err := n.API.Unixfs().Add(ctx, tmpFile)
	if err != nil {
		return cid.Undef, err
	}
	return path.Cid(), nil
}

func (n *IPFSNode) Fetch(ctx context.Context, c cid.Cid, _ []PeerInfo) (files.Node, error) {
	fPath := path.IpfsPath(c)
	return n.API.Unixfs().Get(ctx, fPath)
}

func (n *IPFSNode) DAGService() ipld.DAGService {
	return n.Node.DAG
}

func (n *IPFSNode) Host() host.Host {
	return n.Node.PeerHost
}

func (n *IPFSNode) EmitKeepAlive(recorder MessageRecorder) error {
	recorder.RecordMessage("I am still alive! Total In: %d - TotalOut: %d",
		n.Node.Reporter.GetBandwidthTotals().TotalIn,
		n.Node.Reporter.GetBandwidthTotals().TotalOut)

	return nil
}

var _ Node = &IPFSNode{}
