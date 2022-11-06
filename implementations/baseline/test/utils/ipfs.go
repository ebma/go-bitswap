package utils

import (
	"context"
	"fmt"
	bs "github.com/ipfs/go-bitswap"
	"github.com/ipfs/go-cid"
	files "github.com/ipfs/go-ipfs-files"
	ipld "github.com/ipfs/go-ipld-format"
	"github.com/ipfs/go-merkledag"
	"github.com/ipfs/interface-go-ipfs-core/path"
	"github.com/libp2p/go-libp2p/core/host"

	icore "github.com/ipfs/interface-go-ipfs-core"
	"github.com/ipfs/kubo/core"
	"github.com/ipfs/kubo/core/coreapi"
	//_ "github.com/ipfs/kubo/peering"
	//_ "github.com/multiformats/go-multiaddr"
	//_ "github.com/multiformats/go-multiaddr-dns"
	//_ "github.com/multiformats/go-multihash"
)

// IPFSNode represents the node
type IPFSNode struct {
	Node *core.IpfsNode
	API  icore.CoreAPI
}

func (n *IPFSNode) Instance() *bs.Bitswap {
	//TODO implement me
	panic("implement me")
}

// CreateIPFSNodeWithConfig constructs and returns an IpfsNode using the given cfg.
func CreateIPFSNodeWithConfig(ctx context.Context) (*IPFSNode, error) {
	cfg := core.BuildCfg{}
	n, err := core.NewNode(ctx, &cfg)
	if err != nil {
		return nil, err
	}
	api, err := coreapi.NewCoreAPI(n)
	if err != nil {
		return nil, fmt.Errorf("Failed starting API: %s", err)

	}

	// Attach the Core API to the constructed node
	return &IPFSNode{n, api}, nil
}

// ClearDatastore removes a block from the datastore.
// TODO: This function may be inefficient with large blockstore. Used the option above.
// This function may be cleaned in the future.
func (n *IPFSNode) ClearDatastore(ctx context.Context, rootCid cid.Cid) error {
	_, pinned, err := n.API.Pin().IsPinned(ctx, path.IpfsPath(rootCid))
	if err != nil {
		return err
	}
	if pinned {
		err := n.API.Pin().Rm(ctx, path.IpfsPath(rootCid))
		if err != nil {
			return err
		}
	}
	var ng ipld.NodeGetter = merkledag.NewSession(ctx, n.Node.DAG)
	toDelete := cid.NewSet()
	err = merkledag.Walk(ctx, merkledag.GetLinksDirect(ng), rootCid, toDelete.Visit, merkledag.Concurrent())
	if err != nil {
		return err
	}
	return toDelete.ForEach(func(c cid.Cid) error {
		return n.API.Block().Rm(ctx, path.IpfsPath(c))
	})
}

// EmitMetrics emits node's metrics for the run
func (n *IPFSNode) EmitMetrics(recorder MetricsRecorder) error {
	// TODO: We ned a way of generalizing this for any exchange type
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
